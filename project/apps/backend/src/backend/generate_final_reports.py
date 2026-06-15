from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Optional


def _to_plain(obj: Any) -> Any:
    """
    Recursively converts dataclasses / mappings / objects into JSON-serializable plain Python data.
    """
    if obj is None:
        return None

    if is_dataclass(obj):
        return asdict(obj)

    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()

    if isinstance(obj, Mapping):
        return {str(k): _to_plain(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_to_plain(x) for x in obj]

    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return {k: _to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")}

    return obj


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v:  # NaN
            return "nan"
        return f"{v:.{digits}f}"
    return str(v)


def _md_table(rows: list[tuple[str, str, str]]) -> str:
    out = ["| Field | Value | Notes |", "|---|---:|---|"]
    for field, value, notes in rows:
        out.append(f"| {field} | {value} | {notes} |")
    return "\n".join(out)


def _metric_direction(metric: dict[str, Any]) -> str:
    delta = metric.get("delta_b_minus_a")
    higher_is_better = bool(metric.get("higher_is_better", True))

    if delta is None:
        return "neutral"
    if isinstance(delta, float) and delta != delta:
        return "neutral"

    if higher_is_better:
        if delta > 0:
            return "better"
        if delta < 0:
            return "worse"
        return "neutral"
    else:
        if delta < 0:
            return "better"
        if delta > 0:
            return "worse"
        return "neutral"


def _guardrail_regressions(metrics: dict[str, dict[str, Any]]) -> list[str]:
    guardrail_names = [
        "steps_to_success",
        "actions_per_task",
        "actions_per_success",
        "invalid_action_rate",
        "no_state_change_rate",
        "backtrack_rate",
        "repeat_state_rate",
        "max_step_exhaustion_rate",
    ]
    out: list[str] = []
    for name in guardrail_names:
        m = metrics.get(name)
        if not m:
            continue
        if m.get("significant") and _metric_direction(m) == "worse":
            out.append(name)
    return out


def _primary_section(report: dict[str, Any]) -> str:
    primary = report.get("primary_metric", {}) or {}
    return "\n".join(
        [
            "## Primary metric",
            "",
            f"**Metric:** `{primary.get('name', 'success_rate')}`",
            f"**Test:** `{primary.get('test_name', '-')}`",
            "",
            "| Item | Value |",
            "|---|---:|",
            f"| A | {_fmt(primary.get('group_a_mean'))} |",
            f"| B | {_fmt(primary.get('group_b_mean'))} |",
            f"| Δ (B - A) | {_fmt(primary.get('delta_b_minus_a'))} |",
            f"| Relative uplift | {_fmt(primary.get('relative_uplift'))} |",
            f"| p-value | {_fmt(primary.get('p_value'))} |",
            f"| Bonferroni p-value | {_fmt(primary.get('p_value_adj'))} |",
            f"| 95% CI low | {_fmt(primary.get('ci_low'))} |",
            f"| 95% CI high | {_fmt(primary.get('ci_high'))} |",
            "",
            f"**Significant:** {'yes' if primary.get('significant') else 'no'}",
            "",
        ]
    )


def _metrics_table(report: dict[str, Any], only_guardrails: bool = False) -> str:
    metrics: dict[str, dict[str, Any]] = report.get("metrics", {}) or {}
    order = [
        "success_rate",
        "steps_to_success",
        "actions_per_task",
        "actions_per_success",
        "trajectory_efficiency",
        "invalid_action_rate",
        "no_state_change_rate",
        "backtrack_rate",
        "repeat_state_rate",
        "max_step_exhaustion_rate",
    ]
    if only_guardrails:
        order = [m for m in order if m != "success_rate"]

    rows = [
        "| Metric | A | B | Δ (B - A) | Test | p-value | p_adj | Significant | Direction |",
        "|---|---:|---:|---:|---|---:|---:|---:|---|",
    ]

    for name in order:
        m = metrics.get(name)
        if not m:
            continue

        rows.append(
            "| {name} | {a} | {b} | {delta} | {test} | {p} | {padj} | {sig} | {dir} |".format(
                name=name,
                a=_fmt(m.get("group_a_mean")),
                b=_fmt(m.get("group_b_mean")),
                delta=_fmt(m.get("delta_b_minus_a")),
                test=str(m.get("test_name", "-")),
                p=_fmt(m.get("p_value")),
                padj=_fmt(m.get("p_value_adj")),
                sig="yes" if m.get("significant") else "no",
                dir=_metric_direction(m),
            )
        )

    return "\n".join(rows)


def _data_quality_section(report: dict[str, Any]) -> str:
    dq = report.get("data_quality", {}) or {}
    rows: list[tuple[str, str, str]] = []
    for k, v in dq.items():
        if isinstance(v, (int, float, bool)) or v is None:
            rows.append((k, _fmt(v), ""))
        else:
            rows.append((k, str(v), ""))
    return _md_table(rows)


def _decision_section(report: dict[str, Any]) -> str:
    verdict = report.get("verdict", "inconclusive")
    statistical_winner = report.get("statistical_winner", None)
    practical_winner = report.get("practical_winner", None)
    primary = report.get("primary_metric", {}) or {}
    metrics = report.get("metrics", {}) or {}

    regressions = _guardrail_regressions(metrics)

    return "\n".join(
        [
            "## Decision",
            "",
            f"- Verdict: `{verdict}`",
            f"- Statistical winner: `{statistical_winner if statistical_winner is not None else 'none'}`",
            f"- Practical winner: `{practical_winner if practical_winner is not None else 'none'}`",
            f"- Primary metric significant: {'yes' if primary.get('significant') else 'no'}",
            f"- Guardrail regressions: {', '.join(regressions) if regressions else 'none'}",
            "",
        ]
    )


def _summary_section(report: dict[str, Any]) -> str:
    summary = report.get("summary", "")
    lines = [
        "## Summary",
        "",
        summary if summary else "-",
        "",
    ]
    return "\n".join(lines)


def _run_examples_section(run_examples: Optional[list[dict[str, Any]]]) -> str:
    if not run_examples:
        return ""

    lines = ["## Run examples", ""]
    for ex in run_examples:
        run_id = ex.get("run_id", "-")
        lines.extend(
            [
                f"### Run `{run_id}`",
                "",
                f"- Group: `{ex.get('group', '-')}`",
                f"- Result: `{ex.get('result', '-')}`",
                f"- Final state: `{ex.get('final_state', '-')}`",
                f"- Path summary: `{ex.get('path_summary', '-')}`",
            ]
        )
        evidence = ex.get("key_evidence", []) or []
        if evidence:
            lines.append("- Key evidence:")
            for item in evidence:
                lines.append(f"  - {item}")
        lines.append("")
    return "\n".join(lines)


def _trace_examples_md(run_examples: Optional[list[dict[str, Any]]]) -> str:
    if not run_examples:
        return "# Trace examples\n\nNo examples provided.\n"

    lines = ["# Trace examples", ""]
    for ex in run_examples:
        lines.extend(
            [
                f"## Run `{ex.get('run_id', '-')}`",
                "",
                f"- Group: `{ex.get('group', '-')}`",
                f"- Result: `{ex.get('result', '-')}`",
                f"- Final state: `{ex.get('final_state', '-')}`",
                f"- Path summary: `{ex.get('path_summary', '-')}`",
                "",
            ]
        )
        evidence = ex.get("key_evidence", []) or []
        if evidence:
            lines.append("### Key evidence")
            for item in evidence:
                lines.append(f"- {item}")
            lines.append("")
    return "\n".join(lines)


def _main_report_md(report: dict[str, Any], run_examples: Optional[list[dict[str, Any]]] = None) -> str:
    lines = [
        "# A/B Test Report",
        "",
        f"**Verdict:** `{report.get('verdict', 'inconclusive')}`",
        f"**Statistical winner:** `{report.get('statistical_winner', 'none')}`",
        f"**Practical winner:** `{report.get('practical_winner', 'none')}`",
        "",
    ]
    lines.append(_summary_section(report))
    lines.append("## Data quality")
    lines.append("")
    lines.append(_data_quality_section(report))
    lines.append("")
    lines.append(_decision_section(report))
    lines.append(_primary_section(report))
    lines.append("## All metrics")
    lines.append("")
    lines.append(_metrics_table(report, only_guardrails=False))
    lines.append("")

    run_block = _run_examples_section(run_examples)
    if run_block:
        lines.append(run_block)

    return "\n".join(lines)


def _primary_md(report: dict[str, Any]) -> str:
    primary = report.get("primary_metric", {}) or {}
    return "\n".join(
        [
            "# Primary metric statistics",
            "",
            _primary_section(report),
            "## Interpretation",
            "",
            f"- Main metric: `{primary.get('name', 'success_rate')}`",
            f"- Significant after Bonferroni: {'yes' if primary.get('significant') else 'no'}",
            f"- Decision impact: {'candidate winner' if primary.get('significant') else 'no winner on primary metric'}",
            "",
        ]
    )


def _guardrails_md(report: dict[str, Any]) -> str:
    metrics = report.get("metrics", {}) or {}
    return "\n".join(
        [
            "# Guardrail metrics statistics",
            "",
            _metrics_table(report, only_guardrails=True),
            "",
            "## Notes",
            "",
            "- Guardrails are used to block a win if they degrade significantly.",
            "- Metrics marked as `worse` should be treated as regressions.",
            "- Guardrails do not override the primary metric; they only prevent a release decision.",
            "",
            "## Guardrail regressions",
            "",
            ", ".join(_guardrail_regressions(metrics)) if _guardrail_regressions(metrics) else "none",
            "",
        ]
    )


def write_ab_analysis_report_files(
    report: Any,
    output_dir: str | Path,
    *,
    run_examples: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Path]:
    """
    Write QA-friendly artifacts for an ABAnalysisReport.

    Creates:
      - report.md
      - stats_primary.md
      - stats_guardrails.md
      - trace_examples.md (only if examples are provided)
      - report.json

    Parameters
    ----------
    report:
        ABAnalysisReport instance or dict-like object with:
          verdict, statistical_winner, practical_winner,
          primary_metric, metrics, data_quality, summary

    output_dir:
        Target directory for files.

    run_examples:
        Optional list of trace examples. Each example may contain:
          run_id, group, result, final_state, path_summary, key_evidence
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    report_dict = _to_plain(report)
    if not isinstance(report_dict, dict):
        raise TypeError("report must be ABAnalysisReport-like object or dict")

    written: dict[str, Path] = {}

    # Main QA report
    main_path = out / "report.md"
    main_path.write_text(_main_report_md(report_dict, run_examples), encoding="utf-8")
    written["report_md"] = main_path

    # Primary statistics
    primary_path = out / "stats_primary.md"
    primary_path.write_text(_primary_md(report_dict), encoding="utf-8")
    written["stats_primary_md"] = primary_path

    # Guardrails statistics
    guardrails_path = out / "stats_guardrails.md"
    guardrails_path.write_text(_guardrails_md(report_dict), encoding="utf-8")
    written["stats_guardrails_md"] = guardrails_path

    # Machine-readable export
    json_path = out / "report.json"
    json_path.write_text(json.dumps(report_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    written["report_json"] = json_path

    # Trace examples
    if run_examples is not None:
        traces_path = out / "trace_examples.md"
        traces_path.write_text(_trace_examples_md(run_examples), encoding="utf-8")
        written["trace_examples_md"] = traces_path

    return written


# -------------------------
# Example usage
# -------------------------
# from pathlib import Path
#
# report = calc.analyze(alpha=0.05)  # ABAnalysisReport
# files = write_ab_analysis_report_files(
#     report,
#     output_dir=Path("./ab_qa_report"),
#     run_examples=[
#         {
#             "run_id": "r001",
#             "group": "B",
#             "result": "success",
#             "final_state": "success_screen",
#             "path_summary": "search -> open_card -> add_to_cart -> checkout -> confirm",
#             "key_evidence": [
#                 "final page switched to confirmation screen",
#                 "no errors in trace",
#                 "no backtracking",
#             ],
#         },
#         {
#             "run_id": "r017",
#             "group": "A",
#             "result": "progress",
#             "final_state": "modal_block",
#             "path_summary": "search -> open_card -> add_to_cart -> checkout -> modal_block",
#             "key_evidence": [
#                 "run unfinished",
#                 "modal blocked the flow",
#                 "success cannot be confirmed from frontend state",
#             ],
#         },
#     ],
# )
# print(files)
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from math import sqrt
from typing import Any, Literal, Mapping, Optional

import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportions_ztest


@dataclass
class RunSummary:
    agent_id: str
    agent_group: str
    agent_type: str
    total_actions: int
    final_step: int
    max_steps: int
    terminate: Literal["error", "success", "progress"]
    success: bool
    completed: bool
    refresh_count: int
    backtrack_count: int
    no_state_change_count: int
    repeat_state_count: int
    state_visits: int
    error_actions: int
    exhausted: bool

    @property
    def invalid_action_rate(self) -> float:
        return self.error_actions / self.total_actions if self.total_actions else 0.0

    @property
    def no_state_change_rate(self) -> float:
        return self.no_state_change_count / self.total_actions if self.total_actions else 0.0

    @property
    def backtrack_rate(self) -> float:
        return self.backtrack_count / self.total_actions if self.total_actions else 0.0

    @property
    def repeat_state_rate(self) -> float:
        return self.repeat_state_count / self.state_visits if self.state_visits else 0.0

    @property
    def trajectory_efficiency(self) -> float:
        if not self.completed or self.max_steps <= 0:
            return 0.0
        return (1.0 - self.final_step / self.max_steps) if self.success else 0.0


@dataclass
class MetricResult:
    name: str
    metric_type: Literal["binary", "continuous"]
    higher_is_better: bool
    group_a_mean: float
    group_b_mean: float
    delta_b_minus_a: float
    relative_uplift: float
    test_name: str
    p_value: float
    p_value_adj: float
    ci_low: float
    ci_high: float
    significant: bool
    n_a: int
    n_b: int
    notes: str = ""


@dataclass
class ABAnalysisReport:
    verdict: Literal["winner_A", "winner_B", "no_winner", "inconclusive"]
    statistical_winner: Optional[str]
    practical_winner: Optional[str]
    primary_metric: MetricResult
    metrics: dict[str, MetricResult]
    data_quality: dict[str, Any]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "statistical_winner": self.statistical_winner,
            "practical_winner": self.practical_winner,
            "primary_metric": asdict(self.primary_metric),
            "metrics": {k: asdict(v) for k, v in self.metrics.items()},
            "data_quality": self.data_quality,
            "summary": self.summary,
        }


class ABMetricsCalculator:
    """
    Один agent_id = один прогон.
    Метрики считаются на уровне прогонов, а не сырых действий.
    """

    PRIMARY_METRIC = "success_rate"

    # Метрики, где "меньше" лучше
    LOWER_IS_BETTER = {
        "steps_to_success",
        "actions_per_task",
        "actions_per_success",
        "invalid_action_rate",
        "no_state_change_rate",
        "backtrack_rate",
        "repeat_state_rate",
        "max_step_exhaustion_rate",
    }

    # `progress` учитываем только в этих метриках
    PROGRESS_ALLOWED_IN = {
        "no_state_change_rate",
        "backtrack_rate",
        "repeat_state_rate",
    }

    METRIC_ORDER = [
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

    def __init__(self, data: Mapping[str, list[Any]]) -> None:
        self.ab_agents_data = self._validate_data(data)
        self._runs_cache: dict[str, list[RunSummary]] = {}

    def _validate_data(self, data: Mapping[str, list[Any]]) -> Mapping[str, list[Any]]:
        if not isinstance(data, Mapping):
            raise ValueError("Нужен dict-like объект с ключами 'A' и 'B'.")

        if "A" not in data or "B" not in data:
            raise ValueError("AB-данные должны содержать ключи 'A' и 'B'.")

        if not isinstance(data["A"], list) or not isinstance(data["B"], list):
            raise ValueError("Значения по ключам 'A' и 'B' должны быть списками событий.")

        return data

    def _build_run_summaries(self, events: list[Any]) -> list[RunSummary]:
        grouped: dict[str, list[Any]] = defaultdict(list)
        for ev in events:
            grouped[ev.agent_id].append(ev)

        runs: list[RunSummary] = []

        for agent_id, agent_events in grouped.items():
            if not agent_events:
                continue

            agent_events.sort(key=lambda x: x.step)
            first = agent_events[0]
            last = agent_events[-1]

            total_actions = len(agent_events)
            final_step = int(last.curr_step)
            max_steps = max(
                [int(e.max_steps) for e in agent_events if int(e.max_steps) > 0],
                default=0
            )

            refresh_count = max(int(getattr(e, "refresh_count", 0)) for e in agent_events)
            backtrack_count = sum(1 for e in agent_events if bool(getattr(e, "back", False)))
            no_state_change_count = sum(1 for e in agent_events if str(e.obs_hash_prev) == str(e.obs_hash_curr))
            error_actions = sum(1 for e in agent_events if e.terminate == "error")

            states = [str(first.obs_hash_prev)] + [str(e.obs_hash_curr) for e in agent_events]
            seen: set[str] = set()
            repeat_state_count = 0
            for state in states:
                if state in seen:
                    repeat_state_count += 1
                else:
                    seen.add(state)

            terminal = last.terminate
            success = terminal == "success"
            completed = terminal in ("success", "error")

            # progress — не завершённый прогон
            exhausted = bool(
                completed
                and max_steps > 0
                and final_step >= max_steps
            )

            runs.append(
                RunSummary(
                    agent_id=agent_id,
                    agent_group=str(getattr(first, "agent_group", "")),
                    agent_type=str(getattr(first, "agent_type", "")),
                    total_actions=total_actions,
                    final_step=final_step,
                    max_steps=max_steps,
                    terminate=terminal,
                    success=success,
                    completed=completed,
                    refresh_count=refresh_count,
                    backtrack_count=backtrack_count,
                    no_state_change_count=no_state_change_count,
                    repeat_state_count=repeat_state_count,
                    state_visits=len(states),
                    error_actions=error_actions,
                    exhausted=exhausted,
                )
            )

        return runs

    def _runs(self, group: str) -> list[RunSummary]:
        if group not in self._runs_cache:
            self._runs_cache[group] = self._build_run_summaries(list(self.ab_agents_data[group]))
        return self._runs_cache[group]

    @staticmethod
    def _safe_rel_uplift(a: float, b: float) -> float:
        if np.isnan(a) or a == 0.0:
            return float("nan")
        return float((b - a) / abs(a))

    @staticmethod
    def _ci_diff_continuous(a: np.ndarray, b: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
        n_a, n_b = len(a), len(b)
        mean_a, mean_b = a.mean(), b.mean()

        var_a = a.var(ddof=1) if n_a > 1 else 0.0
        var_b = b.var(ddof=1) if n_b > 1 else 0.0
        se = sqrt((var_a / n_a) + (var_b / n_b)) if n_a > 0 and n_b > 0 else float("nan")

        if n_a > 1 and n_b > 1 and se > 0:
            df_num = (var_a / n_a + var_b / n_b) ** 2
            df_den = (var_a**2) / (n_a**2 * (n_a - 1)) + (var_b**2) / (n_b**2 * (n_b - 1))
            df = df_num / df_den if df_den > 0 else min(n_a, n_b) - 1
            tcrit = stats.t.ppf(1 - alpha / 2, df)
        else:
            tcrit = stats.norm.ppf(1 - alpha / 2)

        diff = mean_b - mean_a
        return float(diff - tcrit * se), float(diff + tcrit * se)

    @staticmethod
    def _ci_diff_binary(p_a: float, p_b: float, n_a: int, n_b: int, alpha: float = 0.05) -> tuple[float, float]:
        se = sqrt((p_a * (1 - p_a) / n_a) + (p_b * (1 - p_b) / n_b))
        z = stats.norm.ppf(1 - alpha / 2)
        diff = p_b - p_a
        return float(diff - z * se), float(diff + z * se)

    def _series(self, metric: str, runs: list[RunSummary]) -> list[float]:
        if metric == "success_rate":
            # `progress` тут идёт как неуспех, потому что прогон не завершён
            return [1.0 if r.success else 0.0 for r in runs]

        if metric == "steps_to_success":
            return [float(r.final_step) for r in runs if r.success]

        if metric == "actions_per_task":
            return [float(r.total_actions) for r in runs if r.completed]

        if metric == "actions_per_success":
            return [float(r.total_actions) for r in runs if r.success]

        if metric == "trajectory_efficiency":
            return [float(r.trajectory_efficiency) for r in runs if r.completed]

        if metric == "invalid_action_rate":
            return [float(r.invalid_action_rate) for r in runs if r.completed]

        if metric == "no_state_change_rate":
            return [float(r.no_state_change_rate) for r in runs]

        if metric == "backtrack_rate":
            return [float(r.backtrack_rate) for r in runs]

        if metric == "repeat_state_rate":
            return [float(r.repeat_state_rate) for r in runs]

        if metric == "max_step_exhaustion_rate":
            return [1.0 if r.exhausted else 0.0 for r in runs if r.completed]

        raise KeyError(f"Unknown metric: {metric}")

    def _compare_binary(self, metric: str, a: list[float], b: list[float]) -> MetricResult:
        a_arr = np.asarray(a, dtype=int)
        b_arr = np.asarray(b, dtype=int)
        n_a, n_b = len(a_arr), len(b_arr)

        if n_a == 0 or n_b == 0:
            return MetricResult(
                name=metric,
                metric_type="binary",
                higher_is_better=(metric not in self.LOWER_IS_BETTER),
                group_a_mean=float("nan"),
                group_b_mean=float("nan"),
                delta_b_minus_a=float("nan"),
                relative_uplift=float("nan"),
                test_name="insufficient_data",
                p_value=float("nan"),
                p_value_adj=float("nan"),
                ci_low=float("nan"),
                ci_high=float("nan"),
                significant=False,
                n_a=n_a,
                n_b=n_b,
                notes="Недостаточно данных.",
            )

        success_a = int(a_arr.sum())
        success_b = int(b_arr.sum())
        p_a = success_a / n_a
        p_b = success_b / n_b

        # Для маленьких частот безопаснее Fisher
        use_fisher = min(success_a, n_a - success_a, success_b, n_b - success_b) < 5
        if use_fisher:
            _, p_value = stats.fisher_exact(
                [[success_a, n_a - success_a], [success_b, n_b - success_b]],
                alternative="two-sided",
            )
            test_name = "fisher_exact"
        else:
            _, p_value = proportions_ztest([success_a, success_b], [n_a, n_b])
            test_name = "two_proportion_z_test"

        ci_low, ci_high = self._ci_diff_binary(p_a, p_b, n_a, n_b)

        return MetricResult(
            name=metric,
            metric_type="binary",
            higher_is_better=(metric not in self.LOWER_IS_BETTER),
            group_a_mean=float(p_a),
            group_b_mean=float(p_b),
            delta_b_minus_a=float(p_b - p_a),
            relative_uplift=float(self._safe_rel_uplift(p_a, p_b)),
            test_name=test_name,
            p_value=float(p_value),
            p_value_adj=float("nan"),
            ci_low=ci_low,
            ci_high=ci_high,
            significant=False,
            n_a=n_a,
            n_b=n_b,
        )

    def _compare_continuous(self, metric: str, a: list[float], b: list[float]) -> MetricResult:
        a_arr = np.asarray([x for x in a if not np.isnan(x)], dtype=float)
        b_arr = np.asarray([x for x in b if not np.isnan(x)], dtype=float)
        n_a, n_b = len(a_arr), len(b_arr)

        if n_a < 2 or n_b < 2:
            return MetricResult(
                name=metric,
                metric_type="continuous",
                higher_is_better=(metric not in self.LOWER_IS_BETTER),
                group_a_mean=float("nan"),
                group_b_mean=float("nan"),
                delta_b_minus_a=float("nan"),
                relative_uplift=float("nan"),
                test_name="insufficient_data",
                p_value=float("nan"),
                p_value_adj=float("nan"),
                ci_low=float("nan"),
                ci_high=float("nan"),
                significant=False,
                n_a=n_a,
                n_b=n_b,
                notes="Нужно минимум 2 наблюдения в каждой группе.",
            )

        mean_a = float(a_arr.mean())
        mean_b = float(b_arr.mean())
        t_stat, p_value = stats.ttest_ind(a_arr, b_arr, equal_var=False, nan_policy="omit")
        ci_low, ci_high = self._ci_diff_continuous(a_arr, b_arr)

        return MetricResult(
            name=metric,
            metric_type="continuous",
            higher_is_better=(metric not in self.LOWER_IS_BETTER),
            group_a_mean=mean_a,
            group_b_mean=mean_b,
            delta_b_minus_a=float(mean_b - mean_a),
            relative_uplift=float(self._safe_rel_uplift(mean_a, mean_b)),
            test_name="welch_t_test",
            p_value=float(p_value),
            p_value_adj=float("nan"),
            ci_low=ci_low,
            ci_high=ci_high,
            significant=False,
            n_a=n_a,
            n_b=n_b,
            notes=f"t={float(t_stat):.4f}",
        )

    def _compare_metric(self, metric: str, runs_a: list[RunSummary], runs_b: list[RunSummary]) -> MetricResult:
        series_a = self._series(metric, runs_a)
        series_b = self._series(metric, runs_b)

        if metric in {"success_rate", "max_step_exhaustion_rate"}:
            return self._compare_binary(metric, series_a, series_b)
        return self._compare_continuous(metric, series_a, series_b)

    @staticmethod
    def _is_deterioration(metric: MetricResult) -> bool:
        if np.isnan(metric.delta_b_minus_a):
            return False
        return metric.delta_b_minus_a < 0 if metric.higher_is_better else metric.delta_b_minus_a > 0

    @staticmethod
    def _is_improvement(metric: MetricResult) -> bool:
        if np.isnan(metric.delta_b_minus_a):
            return False
        return metric.delta_b_minus_a > 0 if metric.higher_is_better else metric.delta_b_minus_a < 0

    @staticmethod
    def _weighted_practical_score(results: dict[str, MetricResult]) -> float:
        weights = {
            "success_rate": 4.0,
            "trajectory_efficiency": 2.0,
            "steps_to_success": 1.5,
            "actions_per_task": 1.0,
            "actions_per_success": 1.0,
            "invalid_action_rate": 2.0,
            "no_state_change_rate": 1.0,
            "backtrack_rate": 1.0,
            "repeat_state_rate": 1.0,
            "max_step_exhaustion_rate": 2.0,
        }

        score = 0.0
        for name, weight in weights.items():
            r = results.get(name)
            if r is None or np.isnan(r.delta_b_minus_a):
                continue
            direction = 1.0 if r.higher_is_better else -1.0
            score += weight * direction * r.delta_b_minus_a
        return score

    def analyze(self, alpha: float = 0.05) -> ABAnalysisReport:
        runs_a = self._runs("A")
        runs_b = self._runs("B")

        if not runs_a or not runs_b:
            raise ValueError("В одной из групп нет прогонов.")

        raw_results: list[MetricResult] = []
        for metric in self.METRIC_ORDER:
            raw_results.append(self._compare_metric(metric, runs_a, runs_b))

        # Bonferroni correction
        valid_idx = [i for i, r in enumerate(raw_results) if not np.isnan(r.p_value)]
        pvals = [raw_results[i].p_value for i in valid_idx]

        if pvals:
            _, pvals_adj, _, _ = multipletests(pvals, alpha=alpha, method="bonferroni")
            for idx, adj in zip(valid_idx, pvals_adj):
                raw_results[idx].p_value_adj = float(adj)
                raw_results[idx].significant = adj < alpha

        metrics = {r.name: r for r in raw_results}
        primary = metrics[self.PRIMARY_METRIC]

        primary_significant = not np.isnan(primary.p_value_adj) and primary.p_value_adj < alpha
        primary_improves = self._is_improvement(primary)

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

        guardrail_regressions = [
            name for name in guardrail_names
            if name in metrics and metrics[name].significant and self._is_deterioration(metrics[name])
        ]

        statistical_winner: Optional[str]
        verdict: Literal["winner_A", "winner_B", "no_winner", "inconclusive"]

        if primary_significant and primary_improves and not guardrail_regressions:
            statistical_winner = "B"
            verdict = "winner_B"
        elif primary_significant and (not primary_improves) and not guardrail_regressions:
            statistical_winner = "A"
            verdict = "winner_A"
        else:
            statistical_winner = None
            verdict = "no_winner"

        practical_score = self._weighted_practical_score(metrics)
        practical_winner: Optional[str]
        if practical_score > 0:
            practical_winner = "B"
        elif practical_score < 0:
            practical_winner = "A"
        else:
            practical_winner = None

        unfinished_rate_a = sum(1 for r in runs_a if r.terminate == "progress") / len(runs_a)
        unfinished_rate_b = sum(1 for r in runs_b if r.terminate == "progress") / len(runs_b)

        summary = (
            f"verdict={verdict}; "
            f"primary={primary.name}: A={primary.group_a_mean:.4g}, B={primary.group_b_mean:.4g}, "
            f"delta={primary.delta_b_minus_a:.4g}, p={primary.p_value:.4g}, p_adj={primary.p_value_adj:.4g}; "
            f"unfinished_rate: A={unfinished_rate_a:.4g}, B={unfinished_rate_b:.4g}; "
            f"guardrail_regressions={guardrail_regressions or 'none'}"
        )

        data_quality = {
            "runs_A": len(runs_a),
            "runs_B": len(runs_b),
            "unique_agents_A": len({r.agent_id for r in runs_a}),
            "unique_agents_B": len({r.agent_id for r in runs_b}),
            "successes_A": sum(1 for r in runs_a if r.success),
            "successes_B": sum(1 for r in runs_b if r.success),
            "unfinished_A": sum(1 for r in runs_a if r.terminate == "progress"),
            "unfinished_B": sum(1 for r in runs_b if r.terminate == "progress"),
            "primary_metric": self.PRIMARY_METRIC,
            "primary_significant": primary_significant,
            "practical_score": practical_score,
        }

        return ABAnalysisReport(
            verdict=verdict,
            statistical_winner=statistical_winner,
            practical_winner=practical_winner,
            primary_metric=primary,
            metrics=metrics,
            data_quality=data_quality,
            summary=summary,
        )
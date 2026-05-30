from typing import Any

import schemathesis
from api_agent.schemas import ProcessIssue, Report, Step, TraceStep
from api_agent.services.utils import (
    CheckValidationError,
    resolve_json_path,
    validate_check,
)
from hypothesis import HealthCheck, Verbosity, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import DataObject
from schemathesis.generation import GenerationMode
from schemathesis.generation.case import Case
from schemathesis.specs.openapi.schemas import OpenApiSchema


def _run_http_step(
    step: Step,
    api_schema: OpenApiSchema,
    context: dict[str, Any],
    bundles: dict[str, Any],
    data: DataObject,
    trace: list,
    report: Report,
):
    method = step.method
    path = step.path

    assert method is not None and path is not None

    if path[-1] != "}":
        path += "/"

    operation = api_schema[path][method]

    case: Case = data.draw(
        operation.as_strategy(generation_mode=GenerationMode.POSITIVE),
        label=f"case:{step.id}",
    )

    if getattr(case, "path_parameters", None) is None:
        case.path_parameters = {}

    bundle_values = {}
    for arg_name, bundle_name in step.bundle_args.items():
        value = bundles[bundle_name]
        bundle_values[arg_name] = value
        case.path_parameters[arg_name] = value
        context[arg_name] = value

    assert case._meta is not None
    case._meta.generation.mode = GenerationMode.POSITIVE

    response = case.call()
    curl = case.as_curl_command()
    report.steps += 1
    trace.append(
        TraceStep(
            name=step.name,
            curl=curl,
            status_code=response.status_code,
            response_text=(response.text or "")[:300],
        )
    )

    assert step.checks is not None
    found_issue = False
    # TODO: нахуя context??
    for check in step.checks:
        issues = validate_check(
            response,
            check,
            external_step=context.get('external_state'),
            context=context,
        )

        if issues:
            found_issue = True

        for i in issues:
            report.issues.add(
                ProcessIssue(
                    kind=i.kind or "",
                    step=step.name,
                    message=i.message,
                    type="process",
                    trace=trace.copy(),
                )
            )

    if step.target_bundle:
        extracted = None
        if step.extract:
            extracted = resolve_json_path(response.json(), step.extract)
        else:
            report.issues.add(
                ProcessIssue(
                    kind="EXTRACT_FAILED",
                    step=step.name,
                    message="Stupid extract path",
                    trace=trace.copy(),
                )
            )
            found_issue = True

        if extracted is None:
            report.issues.add(
                ProcessIssue(
                    kind="TARGET_EXTRACTION_MISSING",
                    step=step.name,
                    message="No value extracted for target bundle",
                    trace=trace.copy(),
                )
            )
            extracted = f"missing-{step.name}"
            found_issue = True

        bundles[step.target_bundle] = extracted

    return not found_issue


def _run_external_step(
    step: Step, context: dict[str, Any], data: DataObject, trace: list
):
    states = step.allowed_external_states or []
    random_state = data.draw(st.sampled_from(states), label=f"external_step:{step.id}")

    context["external_state"] = random_state

    trace.append(
        TraceStep(
            name=step.name,
            curl="<external step imitation>",
            status_code=200,
            response_text=random_state,
        )
    )


def run_path(
    schema: OpenApiSchema, steps: list[Step], data: DataObject, report: Report
):
    context, bundles, trace = {}, {}, []

    for step in steps:
        match step.kind:
            case "http":
                _run_http_step(step, schema, context, bundles, data, trace, report)
            case "external":
                _run_external_step(step, context, data, trace)
            case _:
                assert False, "Unsupported step kind"

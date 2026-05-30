from api_agent.schemas import CoPState, GenerateChecksResult, IRPrompt, IR, Step, Report, BusinessError
from api_agent.services.test_runner import run_path
from hypothesis import HealthCheck, Verbosity, given, settings
from hypothesis import strategies as st
from schemathesis.specs.openapi.schemas import OpenApiSchema



def _build_ir(checks: GenerateChecksResult, ir: IRPrompt) -> IR:
    steps = []
    all_checks = checks.process
    checks_lookup = {item.model_dump().get("step_id"): item for item in all_checks}

    for step in ir.steps:
        step_id = step.id
        step_checks = checks_lookup.get(step_id)

        steps.append(
            Step(
                step_id=step_id,
                id=step_id,
                parent_id=step.parent_id,
                name=step.name,
                kind=step.kind,
                method=step.method,
                path=step.path,
                operation_key=step.operation_key,
                target_bundle=step.target_bundle,
                extract=step.extract,
                bundle_args=step.bundle_args,
                allowed_external_states=step.allowed_external_states,
                checks=step_checks.checks if step_checks is not None else None,
            )
        )

    return IR(machine_name=ir.machine_name, bundles=ir.bundles, steps=steps)

def _run_test(ir: IR, schema: OpenApiSchema, report: Report):
    @settings(
        database=None,
        # max_examples=1,
        # stateful_step_count=1,
        report_multiple_bugs=True,
        verbosity=Verbosity.quiet,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(data=st.data())
    def test(data):
        run_path(schema, ir.steps, data, report)
    return test

def process_test_node(state: CoPState) -> dict:
    assert state.generated_checks is not None
    assert state.generated_graph is not None

    generated_ir = _build_ir(state.generated_checks, state.generated_graph)

    report = Report()

    assert state.schema_parser.schema is not None
    runner = _run_test(generated_ir, state.schema_parser.schema, report)
    runner()

    for i in report.issues:
        if i.type == "process":
            b = BusinessError(issue=i)
            print(b, end="\n+++++++++++++++++++++++++++++++++++\n")

    return {}
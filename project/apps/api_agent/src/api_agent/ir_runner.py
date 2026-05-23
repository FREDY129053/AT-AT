import json
import warnings

import schemathesis
from hypothesis import HealthCheck, Verbosity, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import DataObject
from schemathesis.generation import GenerationMode
from schemathesis.generation.case import Case
from schemathesis.specs.openapi.schemas import OpenApiSchema

from .checks_validator import validate_check, JsonPathResolutionError
from .schemas.ir import (
    IR,
    GenerateChecksResult,
    IRPrompt,
    Step,
)

warnings.filterwarnings("ignore", message="Overriding standard format")

def build_test(ir_data, data: DataObject):
    final_ir = IR.model_validate(ir_data)

    get_step = final_ir.steps[2]

    schema = schemathesis.openapi.from_url("http://127.0.0.1:8000/openapi.json")
    for step in final_ir.steps:
        if step.kind == 'external':
            continue
        
        get_step = step
        method = get_step.method
        path = get_step.path
        assert method is not None and path is not None
        if path[-1] != "}":
            path += "/"
        operation = schema[path][method]  # type: ignore
        case: Case = data.draw(
            operation.as_strategy(generation_mode=GenerationMode.POSITIVE),
            label=f"case:{get_step.id}",
        )
        response = case.call()
        assert get_step.checks is not None
        for check in get_step.checks:
            try:
                validate_check(response, check.check, context={}, external_step='approved')
            except JsonPathResolutionError:
                continue

def main():
    with open("./src/.temp/final_ir.json", "r") as file:
        ir_data = json.load(file)

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
        build_test(ir_data, data)
    return test

if __name__ == "__main__":
    t = main()
    t()
from __future__ import annotations

from api_agent.services.test_runner import run_schemathesis
from api_agent.schemas import ApiTesterState

def functional_test_node(state: ApiTesterState) -> dict:
    return {}

result = run_schemathesis(
    "http://127.0.0.1:8000/openapi.json",
    seed=9820850968612215253547488999690991193,
    max_examples=100,
    phases=["fuzzing", "examples", "coverage"],
)

print(f"Seed: {result.seed}")
print("total_cases:", result.statistic.total_cases)
print("cases_with_failures:", result.statistic.cases_with_failures)
print("unique_failures:", result.unique_failure_count)

for label, groups in result.statistic.failures.items():
    if label == "Stateful tests":
        continue
    print("\n==", label)
    for case_id, group in groups.items():
        print(case_id, [f.title for f in group.failures])

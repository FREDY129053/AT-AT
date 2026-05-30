from __future__ import annotations

import secrets
from typing import Iterable

from api_agent.schemas import Result
from schemathesis.cli.commands.run.context import ExecutionContext
from schemathesis.cli.commands.run.handlers.output import OutputHandler
from schemathesis.cli.executor import execute_event_loop
from schemathesis.cli.loaders import into_event_stream
from schemathesis.config import HealthCheck, ProjectConfig, SchemathesisConfig
from schemathesis.generation import GenerationMode
from schemathesis.generation.metrics import response_time
from schemathesis.engine import events, from_schema

ALL_PHASES = ("examples", "coverage", "fuzzing", "stateful")

def run_schemathesis(
    schema_url: str,
    *,
    seed: int | None = None,
    max_examples: int = 100,
    phases: Iterable[str] | None = None,
) -> Result:
    actual_seed = seed if seed is not None else secrets.randbits(64)

    config: SchemathesisConfig = SchemathesisConfig()
    config.update(
        suppress_health_check=[HealthCheck.too_slow],
        seed=actual_seed,
        wait_for_schema=None,
        max_failures=None,
    )
    config.projects.override.update(
        continue_on_failure=True,
        request_timeout=None,
    )
    filter_set = {
        "include_path": (),
        "include_method": (),
        "include_name": (),
        "include_tag": (),
        "include_operation_id": (),
        "include_path_regex": None,
        "include_method_regex": None,
        "include_name_regex": None,
        "include_tag_regex": None,
        "include_operation_id_regex": None,
        "exclude_path": (),
        "exclude_method": (),
        "exclude_name": (),
        "exclude_tag": (),
        "exclude_operation_id": (),
        "exclude_path_regex": None,
        "exclude_method_regex": None,
        "exclude_name_regex": None,
        "exclude_tag_regex": None,
        "exclude_operation_id_regex": None,
        "include_by": None,
        "exclude_by": None,
        "exclude_deprecated": False,
    }
    config.projects.override.phases.update(phases=list(phases or ALL_PHASES))
    config.projects.override.generation.update(
        modes=[GenerationMode.POSITIVE, GenerationMode.NEGATIVE],
        no_shrink=False,
        deterministic=True,
        database=None,
        unique_inputs=True,
        allow_x00=False,
        max_examples=max_examples,
    )

    result = Result(seed=actual_seed)

    stream = into_event_stream(
        location=schema_url,
        config=config.projects.get_default(),
        engine_callback=lambda schema: from_schema(schema).execute(),
        filter_set=filter_set,  # no filters: test everything
    )


    for event in stream:
        result.events.append(event)

        if isinstance(event, events.StatefulPhasePayload):
            continue

        if isinstance(event, events.ScenarioFinished):
            result.scenario_finished.append(event)
            result.statistic.on_scenario_finished(event.recorder)

        elif isinstance(event, events.PhaseFinished):
            result.phase_finished.append(event)

        elif isinstance(event, events.NonFatalError):
            result.non_fatal_errors.append(event)

        elif isinstance(event, events.FatalError):
            result.fatal_errors.append(event)

        elif isinstance(event, events.EngineFinished):
            result.engine_finished = event

    return result

from __future__ import annotations

import secrets

from typing import Iterable

from schemathesis.cli.loaders import into_event_stream
from schemathesis.config import ProjectConfig
from schemathesis.engine import events, from_schema

from api_agent.schemas import Result

ALL_PHASES = ("examples", "coverage", "fuzzing", "stateful")

# TODO: как-то выключить stateful фазу
def run_schemathesis(
    schema_url: str,
    *,
    seed: int | None = None,
    max_examples: int = 100,
    phases: Iterable[str] | None = None,
) -> Result:
    actual_seed = seed if seed is not None else secrets.randbits(64)

    config = ProjectConfig()

    config.seed = actual_seed
    config.continue_on_failure = True

    config.phases.update(phases=list(phases or ALL_PHASES))

    config.generation.mode = "all"
    config.generation.max_examples = max_examples

    result = Result(seed=actual_seed)

    stream = into_event_stream(
        location=schema_url,
        # config=config.projects.get_default(),
        config=config,
        engine_callback=lambda schema: from_schema(schema).execute(),
        filter_set={
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
        },  # no filters: test everything
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
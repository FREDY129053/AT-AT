from __future__ import annotations

from dataclasses import dataclass, field
from schemathesis.engine.statistic import Statistic
from schemathesis.engine import events

@dataclass
class Result:
    seed: int
    events: list[events.EngineEvent] = field(default_factory=list)
    scenario_finished: list[events.ScenarioFinished] = field(default_factory=list)
    phase_finished: list[events.PhaseFinished] = field(default_factory=list)
    non_fatal_errors: list[events.NonFatalError] = field(default_factory=list)
    fatal_errors: list[events.FatalError] = field(default_factory=list)
    engine_finished: events.EngineFinished | None = None
    statistic: Statistic = field(default_factory=Statistic)

    @property
    def unique_failure_count(self) -> int:
        return len(self.statistic.unique_failures_map)

    @property
    def failure_count(self) -> int:
        return self.statistic.cases_with_failures

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class TraceStep:
    name: str
    curl: str
    status_code: int
    response_text: str

@dataclass()
class ProcessIssue:
    kind: str
    step: str
    message: str
    type: Literal["runtime", "process"] = "runtime"
    trace: list[TraceStep] = field(default_factory=list)

    def __hash__(self):
        return hash(
            (
                self.kind,
                # self.step,
                self.message,
                self.type,
                # tuple(self.trace)
            )
        )

    def __eq__(self, other):
        return (
            (self.kind == other.kind)
            # and (self.step == other.step)
            and (self.message == other.message)
            and (self.type == other.type)
            # and (self.trace == other.trace)
        )


@dataclass
class Report:
    steps: int = 0
    warnings: set[dict[str, Any]] = field(default_factory=set)
    issues: set[ProcessIssue] = field(default_factory=set)

@dataclass
class BusinessError(AssertionError):
    issue: ProcessIssue

    def __str__(self) -> str:
        out = [f"===== {self.issue.kind}: {self.issue.message} ====="]
        for i, step in enumerate(self.issue.trace, start=1):
            out.append(f"{i}. {step.name} -> {step.status_code}")
            out.append(f"\t{step.curl}")

            if step.response_text:
                out.append(f"\t{step.response_text}")

        return "\n".join(out)
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Finding:
    rule_id: str
    severity: str
    message: str
    suggestion: str | None = None
    points: int = 0


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    @property
    def risk_score(self) -> int:
        return min(100, sum(item.points for item in self.findings))

    @property
    def passed(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "risk_score": self.risk_score,
            "findings": [item.__dict__ for item in self.findings],
        }

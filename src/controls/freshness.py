"""C3.1 Source freshness validation (Control Matrix, Risk R3).

Compares the filing date of a source document against today's date. Fails
when the document is older than ``max_age_days`` (default 120, read from the
control matrix).
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class FreshnessResult:
    control_id: str = "C3.1"
    source_date: date | None = None
    source_age_days: int = 0
    max_age_days: int = 120
    freshness_pass: bool = False
    passed: bool = False

    def as_evidence(self) -> dict:
        return {
            "control_id": self.control_id,
            "kind": "check",
            "source_date": self.source_date.isoformat() if self.source_date else None,
            "source_age_days": self.source_age_days,
            "max_age_days": self.max_age_days,
            "freshness_pass": self.freshness_pass,
            "passed": self.passed,
        }


def check_freshness(
    filing_date: date, *, max_age_days: int = 120, today: date | None = None
) -> FreshnessResult:
    today = today or date.today()
    age = (today - filing_date).days
    ok = 0 <= age <= max_age_days
    return FreshnessResult(
        source_date=filing_date,
        source_age_days=age,
        max_age_days=max_age_days,
        freshness_pass=ok,
        passed=ok,
    )

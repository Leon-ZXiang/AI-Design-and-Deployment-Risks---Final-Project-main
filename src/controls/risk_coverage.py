"""C2.1 Risk-factor coverage check (Control Matrix, Risk R2).

Checks that the generated draft names at least one keyword from each required
risk category (e.g., litigation, liquidity, margin pressure, forward guidance,
regulatory). A category is considered covered if any keyword from its list
appears in the draft, case-insensitive.

Deterministic baseline so treatment is transparent to reviewers. The
categories themselves come from control_matrix.yaml, but keyword lexicons
are kept here because they are the implementation detail of the check.
"""
from dataclasses import dataclass, field


CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "litigation": [
        "litigation", "lawsuit", "patent", "defendant", "plaintiff",
        "claim", "court", "sued", "settlement",
    ],
    "liquidity": [
        "liquidity", "cash", "credit facility", "revolving", "working capital",
        "debt", "leverage",
    ],
    "margin_pressure": [
        "margin", "gross margin", "operating margin", "cost", "pricing",
    ],
    "forward_guidance": [
        "guidance", "outlook", "forecast", "expect", "projected", "estimate",
    ],
    "regulatory": [
        "regulatory", "regulation", "export control", "compliance",
        "sanction", "tariff",
    ],
}


@dataclass
class RiskCoverageResult:
    control_id: str = "C2.1"
    coverage_map: dict[str, bool] = field(default_factory=dict)
    missing_categories: list[str] = field(default_factory=list)
    passed: bool = False

    def as_evidence(self) -> dict:
        return {
            "control_id": self.control_id,
            "kind": "check",
            "coverage_map": self.coverage_map,
            "missing_categories": self.missing_categories,
            "passed": self.passed,
        }


def check_risk_coverage(
    draft: str, required_categories: list[str]
) -> RiskCoverageResult:
    draft_lc = draft.lower()
    coverage: dict[str, bool] = {}
    for cat in required_categories:
        keywords = CATEGORY_KEYWORDS.get(cat, [cat])
        coverage[cat] = any(kw.lower() in draft_lc for kw in keywords)
    missing = [c for c, ok in coverage.items() if not ok]
    return RiskCoverageResult(
        coverage_map=coverage,
        missing_categories=missing,
        passed=not missing,
    )

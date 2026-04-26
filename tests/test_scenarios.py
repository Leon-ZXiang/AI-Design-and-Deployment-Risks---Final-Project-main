"""Pure-Python test suite for the frozen NovaVest sample cases.

Runs the three frozen sample cases plus a REJECT smoke test (proves the
hard-fail path remains functional even though it is not part of the
sample case set sent to Leon).

    python -m tests.test_scenarios

Exits non-zero on any assertion failure.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.workflow import run  # noqa: E402


SOURCES = PROJECT_ROOT / "data" / "sources"


def _by_id(result: dict, cid: str) -> dict | None:
    for c in result.get("control_results", []):
        if c.get("control_id") == cid:
            return c
    return None


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def case_microsoft() -> None:
    r = run(
        SOURCES / "microsoft_10q_excerpt.md",
        analyst_signoff="jsmith",
        senior_reviewer_signoff="kpatel",
    )
    _assert(
        r["final_status"] == "APPROVED",
        f"expected APPROVED, got {r['final_status']}",
    )
    checks = [c for c in r["control_results"] if c.get("kind") == "check"]
    _assert(
        all(c["passed"] for c in checks),
        f"automated checks failed: {[c for c in checks if not c['passed']]}",
    )
    humans = [c for c in r["control_results"] if c.get("kind") == "human"]
    _assert(all(c["passed"] for c in humans), "missing human sign-off")


def case_apple() -> None:
    r = run(SOURCES / "apple_10q_excerpt.md")
    _assert(
        r["final_status"] == "REVISE",
        f"expected REVISE, got {r['final_status']}",
    )
    c21 = _by_id(r, "C2.1")
    _assert(
        c21 is not None and len(c21.get("missing_categories") or []) == 1,
        f"expected exactly 1 missing category, got "
        f"{c21 and c21.get('missing_categories')}",
    )
    c61 = _by_id(r, "C6.1")
    _assert(
        c61 is not None and c61.get("revise") is True,
        "C6.1 should mark revise=True for REVISE outcome",
    )


def case_nvidia() -> None:
    r = run(SOURCES / "nvidia_10q_excerpt.md")
    _assert(
        r["final_status"] == "ESCALATED",
        f"expected ESCALATED, got {r['final_status']}",
    )
    c21 = _by_id(r, "C2.1")
    _assert(
        c21 is not None and len(c21.get("missing_categories") or []) >= 2,
        f"expected ≥2 missing categories, got "
        f"{c21 and c21.get('missing_categories')}",
    )
    c61 = _by_id(r, "C6.1")
    _assert(
        c61 is not None and c61.get("escalated") is True,
        "C6.1 routing should fire on multi-missing",
    )
    _assert(
        c61.get("escalation_target") == "senior_research_reviewer",
        f"unexpected target: {c61.get('escalation_target')}",
    )


def case_reject_smoke() -> None:
    """REJECT path is documented in the decision logic but not part of the
    frozen sample case set. Smoke-test it via a tempfile with an old date."""
    body = textwrap.dedent("""\
        # Stale Tech Corp — Form 10-K Excerpt (synthetic sample)

        Filing date: 2023-03-15
        Period ended: 2022-12-31
        Source: synthetic stale sample for the REJECT smoke test.

        ## Results of operations
        Full-year revenue was $12.4 billion, up 6% year over year. Gross margin
        was 38.5%, essentially flat compared with the prior year.

        ## Risk factors
        Patent litigation continues across multiple jurisdictions. Regulatory
        exposure includes pending antitrust reviews. Margin pressure from
        component pricing remains. Forward guidance is unchanged.
    """)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(body)
        path = Path(f.name)
    try:
        r = run(path)
    finally:
        path.unlink(missing_ok=True)
    _assert(
        r["final_status"] == "REJECTED",
        f"expected REJECTED, got {r['final_status']}",
    )
    c31 = _by_id(r, "C3.1")
    _assert(
        c31 is not None and c31["passed"] is False,
        "C3.1 freshness should have failed",
    )


CASES = [
    ("Case 1 Microsoft -> APPROVED",  case_microsoft),
    ("Case 2 Apple     -> REVISE",    case_apple),
    ("Case 3 Nvidia    -> ESCALATED", case_nvidia),
    ("smoke stale      -> REJECTED",  case_reject_smoke),
]


def main() -> int:
    passed = 0
    failed = 0
    for name, fn in CASES:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}  -- {e}")
        except Exception:
            failed += 1
            print(f"ERROR {name}")
            traceback.print_exc()
        else:
            passed += 1
            print(f"PASS  {name}")
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

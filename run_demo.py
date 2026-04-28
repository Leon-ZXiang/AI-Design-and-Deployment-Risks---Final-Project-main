"""End-to-end demo for NovaVest Research Summary Assistant v1.

Runs the three frozen sample cases through the full governance pipeline:

    Case 1 — Microsoft — APPROVED  (clean source, all controls pass, both sign-offs)
    Case 2 — Apple    — REVISE    (one important risk category missing)
    Case 3 — Nvidia   — ESCALATED (multiple material risk categories missing)

Regenerate the dashboard after running:
    python -m src.dashboard
"""
from pathlib import Path

from src.workflow import run


DATA = Path(__file__).parent / "data" / "sources"

SCENARIOS = [
    {
        "name": "Case 1 — Microsoft",
        "source": DATA / "microsoft_10q_excerpt.md",
        "analyst": "jsmith",
        "senior": "kpatel",
        "reviewer_notes": None,
    },
    {
        "name": "Case 2 — Apple",
        "source": DATA / "apple_10q_excerpt.md",
        "analyst": None,
        "senior": None,
        "reviewer_notes": (
            "Draft is mostly grounded but does not cover regulatory exposure. "
            "Add the missing category before approval."
        ),
    },
    {
        "name": "Case 3 — Nvidia",
        "source": DATA / "nvidia_10q_excerpt.md",
        "analyst": None,
        "senior": None,
        "reviewer_notes": (
            "Source omits multiple material risk categories. Issue cannot be "
            "cleared in the normal review path — escalate to senior research review."
        ),
    },
]


def _format_line(ctrl: dict) -> str | None:
    cid = ctrl.get("control_id", "?")
    kind = ctrl.get("kind", "check")

    if kind == "check":
        passed = ctrl.get("passed")
        bits = [f"passed={passed}"]
        if "grounding_score" in ctrl:
            bits.append(f"score={ctrl['grounding_score']}")
        if "missing_categories" in ctrl and ctrl["missing_categories"]:
            bits.append(f"missing={ctrl['missing_categories']}")
        if "source_age_days" in ctrl:
            bits.append(f"age={ctrl['source_age_days']}d")
        return f"  {cid} [check]    " + "  ".join(bits)

    if kind == "human":
        status = ctrl.get("status", "PENDING")
        signer = ctrl.get("signed_by") or "—"
        owner = ctrl.get("owner", "?")
        return f"  {cid} [human]    owner={owner}  status={status}  signed_by={signer}"

    if kind == "routing":
        reasons = ctrl.get("escalation_reasons") or ctrl.get("revise_reasons") or []
        target = ctrl.get("escalation_target") or "—"
        marker = (
            "ESCALATED" if ctrl.get("escalated")
            else "REVISE" if ctrl.get("revise")
            else "OK"
        )
        return (f"  {cid} [routing]  status={marker}  target={target}  "
                f"reasons={reasons}")

    if kind == "housekeeping":
        detail = ctrl.get("note") or ""
        return f"  {cid} [meta]     {detail}"

    return f"  {cid} [{kind}]"


def _print_result(name: str, result: dict) -> None:
    print(f"=== {name} ===")
    print(f"Run ID       : {result['run_id']}")
    print(f"Final status : {result['final_status']}")
    print(f"Evidence     : {result['evidence_path']}")
    for ctrl in result["control_results"]:
        line = _format_line(ctrl)
        if line:
            print(line)
    print()


def main(generation_mode: str = "stub") -> None:
    import time
    for i, s in enumerate(SCENARIOS):
        if i > 0 and generation_mode == "openrouter":
            print("Waiting 10s for OpenRouter rate-limit window...")
            time.sleep(10)
        result = run(
            s["source"],
            generation_mode=generation_mode,
            analyst_signoff=s["analyst"],
            senior_reviewer_signoff=s["senior"],
            reviewer_notes=s["reviewer_notes"],
        )
        _print_result(s["name"], result)


if __name__ == "__main__":
    #main(generation_mode="stub")  
    main(generation_mode="openrouter")

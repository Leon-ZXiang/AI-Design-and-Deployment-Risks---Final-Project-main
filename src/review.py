"""Release decision and escalation routing (Control Matrix, Risks R4 and R6).

Implements C6.1 escalation logic and the ``release_gates`` rules from the
control matrix. Given a list of control results and an optional analyst
sign-off, produces one of five final statuses:

    APPROVED                all hard gates pass + both sign-offs complete
    REVISE                  mostly usable, single soft-control gap that the
                            reviewer can correct in-line (frozen spec §6.2)
    REJECTED                any hard gate failed
    ESCALATED               serious unresolved issue — multiple soft-fails,
                            grounding below threshold, or unsupported claims
    PENDING_HUMAN_REVIEW    clean run, waiting for sign-off

The soft-gate triggers are read from control C6.1's ``escalation_triggers``
in the matrix so thresholds stay configurable without code changes.
"""
from dataclasses import dataclass


ESCALATION_TARGET = "senior_research_reviewer"


@dataclass
class ReleaseDecision:
    final_status: str
    hard_fails: list[str]
    soft_fails: list[str]
    escalation_reasons: list[str]
    revise_reasons: list[str]
    escalation_target: str | None
    analyst_id: str | None

    def as_evidence(self) -> dict:
        return {
            "control_id": "C6.1",
            "kind": "routing",
            "escalated": self.final_status == "ESCALATED",
            "revise": self.final_status == "REVISE",
            "escalation_reasons": self.escalation_reasons,
            "revise_reasons": self.revise_reasons,
            "escalation_target": self.escalation_target,
            "passed": True,
        }


def _gate_map(matrix: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for risk in matrix["risks"]:
        for ctrl in risk.get("controls", []):
            out[ctrl["id"]] = ctrl.get("gate", "hard")
    return out


def _escalation_triggers(matrix: dict) -> list[dict]:
    for risk in matrix["risks"]:
        for ctrl in risk.get("controls", []):
            if ctrl["id"] == "C6.1":
                return ctrl.get("escalation_triggers", [])
    return []


def _evaluate_triggers(control_results: list[dict], triggers: list[dict]) -> list[str]:
    reasons: list[str] = []
    by_id = {r.get("control_id"): r for r in control_results}
    for t in triggers:
        if "grounding_score_below" in t:
            thresh = t["grounding_score_below"]
            g = by_id.get("C1.1")
            if g and g.get("grounding_score", 1.0) < thresh:
                reasons.append(f"grounding_score<{thresh}")
        if "unsupported_claim_count_above" in t:
            thresh = t["unsupported_claim_count_above"]
            g = by_id.get("C1.1")
            if g:
                n = len(g.get("unsupported_sentences", []))
                if n > thresh:
                    reasons.append(f"unsupported_claim_count>{thresh}")
    return reasons


def _missing_category_count(control_results: list[dict]) -> int:
    for r in control_results:
        if r.get("control_id") == "C2.1":
            return len(r.get("missing_categories") or [])
    return 0


def decide_release(
    control_results: list[dict],
    matrix: dict,
    *,
    analyst_signoff: str | None = None,
    senior_reviewer_signoff: str | None = None,
) -> ReleaseDecision:
    """Apply release-gate logic. Frozen spec §6 outcomes:

    - REJECT  : any hard gate failed
    - ESCALATE: 2+ missing categories OR any C6.1 trigger fired
                (low grounding, unsupported claims) — material/unresolved
    - REVISE  : exactly 1 missing risk category, nothing else wrong
    - APPROVE : all clean + both sign-offs
    - PENDING : clean run waiting for sign-off
    """
    gates = _gate_map(matrix)

    hard_fails: list[str] = []
    soft_fails: list[str] = []
    for r in control_results:
        if r.get("kind", "check") != "check":
            continue
        cid = r.get("control_id")
        if cid is None or r.get("passed", False):
            continue
        if gates.get(cid, "hard") == "hard":
            hard_fails.append(cid)
        else:
            soft_fails.append(cid)

    escalation_reasons = _evaluate_triggers(
        control_results, _escalation_triggers(matrix)
    )
    missing_n = _missing_category_count(control_results)
    both_signed = bool(analyst_signoff) and bool(senior_reviewer_signoff)

    revise_reasons: list[str] = []
    if missing_n == 1:
        revise_reasons.append("missing_one_required_category")

    if hard_fails:
        status = "REJECTED"
        target = None
    elif escalation_reasons or missing_n >= 2:
        status = "ESCALATED"
        target = ESCALATION_TARGET
        if missing_n >= 2:
            escalation_reasons.append(f"missing_required_categories>={missing_n}")
    elif soft_fails or revise_reasons:
        status = "REVISE"
        target = None
    elif both_signed:
        status = "APPROVED"
        target = None
    else:
        status = "PENDING_HUMAN_REVIEW"
        target = None

    return ReleaseDecision(
        final_status=status,
        hard_fails=hard_fails,
        soft_fails=soft_fails,
        escalation_reasons=escalation_reasons,
        revise_reasons=revise_reasons,
        escalation_target=target,
        analyst_id=analyst_signoff if status == "APPROVED" else None,
    )

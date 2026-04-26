"""Release-review workflow orchestrator.

Implements the frozen NovaVest pipeline:

    ingest  ->  freshness (C3.1)  ->  generate  ->
    grounding (C1.1)  ->  risk coverage (C2.1)  ->
    decide (C1.2 senior + C4.2 analyst sign-off + C6.1 routing)  ->
    evidence pack (C5.1)

Each control result carries a ``kind`` field so downstream display and
dashboard logic can distinguish automated checks from human controls,
routing, and housekeeping entries. Generated drafts are still prefixed with
the ``DRAFT — not approved for release`` label as response-text hygiene,
even though draft labeling is no longer a separate control in the frozen
7-control set.
"""
from pathlib import Path

from .config import load_control_matrix, find_control
from .ingest import load_source
from .generate import generate_draft
from .controls.grounding import check_grounding
from .controls.risk_coverage import check_risk_coverage
from .controls.freshness import check_freshness
from .review import decide_release
from .evidence import new_run_id, write_evidence_pack


def _human_entry(
    control_id: str, owner: str, signed_by: str | None, pending_status: str
) -> dict:
    return {
        "control_id": control_id,
        "kind": "human",
        "owner": owner,
        "signed_by": signed_by,
        "status": "COMPLETED" if signed_by else pending_status,
        "passed": bool(signed_by),
    }


def run(
    source_path: str | Path,
    *,
    generation_mode: str = "stub",
    analyst_signoff: str | None = None,
    senior_reviewer_signoff: str | None = None,
    reviewer_notes: str | None = None,
) -> dict:
    matrix = load_control_matrix()
    source = load_source(source_path)
    run_id = new_run_id()

    c31 = find_control(matrix, "C3.1") or {}
    freshness = check_freshness(
        source.filing_date,
        max_age_days=c31.get("max_age_days", 120),
    )

    gen = generate_draft(source.text, mode=generation_mode)

    c11 = find_control(matrix, "C1.1") or {}
    grounding = check_grounding(
        gen.response,
        source.text,
        pass_threshold=c11.get("pass_threshold", 0.90),
    )

    c21 = find_control(matrix, "C2.1") or {}
    coverage = check_risk_coverage(gen.response, c21.get("required_categories", []))

    control_results: list[dict] = [
        freshness.as_evidence(),
        grounding.as_evidence(),
        coverage.as_evidence(),
        _human_entry("C1.2", "senior_reviewer", senior_reviewer_signoff,
                     "PENDING_SENIOR_REVIEW"),
        _human_entry("C4.2", "analyst", analyst_signoff,
                     "PENDING_ANALYST_REVIEW"),
    ]

    decision = decide_release(
        control_results,
        matrix,
        analyst_signoff=analyst_signoff,
        senior_reviewer_signoff=senior_reviewer_signoff,
    )
    control_results.append(decision.as_evidence())
    control_results.append({
        "control_id": "C5.1",
        "kind": "housekeeping",
        "evidence_written": True,
        "note": f"evidence pack written for {run_id}",
        "passed": True,
    })

    reviewer_decision_label = {
        "APPROVED": "APPROVED",
        "REVISE": "REVISE",
        "ESCALATED": "ESCALATE",
        "REJECTED": "REJECT",
    }.get(decision.final_status)

    escalation = None
    if decision.final_status == "ESCALATED":
        escalation = {
            "target": decision.escalation_target,
            "reasons": decision.escalation_reasons,
            "soft_fails": decision.soft_fails,
        }

    evidence_path = write_evidence_pack(
        run_id=run_id,
        source={
            "path": str(source.path),
            "company": source.company,
            "ticker": source.ticker,
            "document_type": source.document_type,
            "filing_date": source.filing_date,
        },
        prompt=gen.prompt,
        response=gen.labeled_response(),
        control_results=control_results,
        final_status=decision.final_status,
        reviewer_id=decision.analyst_id or analyst_signoff,
        reviewer_decision=reviewer_decision_label,
        reviewer_notes=reviewer_notes,
        escalation=escalation,
    )

    return {
        "run_id": run_id,
        "final_status": decision.final_status,
        "evidence_path": str(evidence_path),
        "control_results": control_results,
        "draft": gen.labeled_response(),
        "decision": decision,
    }

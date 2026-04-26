"""C5.1 Evidence pack capture (Control Matrix, Risk R5).

Writes one JSON file per workflow run into evidence/. The schema matches the
evidence_fields declared for C5.1 in artifacts/control_matrix.yaml so the
audit trail is explicit and defensible.
"""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import json

from .config import EVIDENCE_DIR


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{stamp}-{uuid4().hex[:6]}"


def write_evidence_pack(
    run_id: str,
    source: dict,
    prompt: str,
    response: str,
    control_results: list[dict],
    final_status: str,
    reviewer_id: str | None = None,
    reviewer_decision: str | None = None,
    reviewer_notes: str | None = None,
    escalation: dict | None = None,
) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    pack = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_documents": [source],
        "prompt": prompt,
        "response": response,
        "control_results": control_results,
        "reviewer_id": reviewer_id,
        "reviewer_decision": reviewer_decision,
        "reviewer_notes": reviewer_notes,
        "escalation": escalation,
        "final_status": final_status,
    }
    out_path = EVIDENCE_DIR / f"{run_id}.json"
    out_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
    return out_path

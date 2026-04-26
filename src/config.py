"""Load the control matrix artifact and expose it to the workflow."""
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = PROJECT_ROOT / "artifacts" / "control_matrix.yaml"
EVIDENCE_DIR = PROJECT_ROOT / "evidence"


def load_control_matrix(path: Path = MATRIX_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_control(matrix: dict, control_id: str) -> dict | None:
    for risk in matrix["risks"]:
        for ctrl in risk.get("controls", []):
            if ctrl["id"] == control_id:
                return {"risk_id": risk["id"], **ctrl}
    return None

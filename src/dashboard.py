"""Governance dashboard.

Reads every evidence pack JSON from ``evidence/`` and renders a single,
self-contained HTML page at ``artifacts/dashboard.html``. No external JS or
CSS dependencies. Re-run after each batch of workflow runs:

    python -m src.dashboard
"""
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import json

from .config import EVIDENCE_DIR, load_control_matrix, PROJECT_ROOT


DASHBOARD_PATH = PROJECT_ROOT / "artifacts" / "dashboard.html"
LOD_DIR = PROJECT_ROOT / "artifacts" / "lod"

FROZEN_SYSTEM_DEFINITION = (
    "NovaVest Research Summary Assistant v1 is a governed AI-assisted "
    "financial research summary workflow for internal analysts. It uses "
    "public company disclosures to generate first-draft summaries, and "
    "every output must pass control checks, review, and release decisions "
    "before it can be used beyond draft support."
)

STATUS_CLASS = {
    "APPROVED": "status-approved",
    "REVISE": "status-revise",
    "REJECTED": "status-rejected",
    "ESCALATED": "status-escalated",
    "PENDING_HUMAN_REVIEW": "status-pending",
}


def _load_all_evidence() -> list[dict]:
    if not EVIDENCE_DIR.exists():
        return []
    packs = []
    for path in sorted(EVIDENCE_DIR.glob("run-*.json"), reverse=True):
        try:
            packs.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return packs


def _by_control(packs: list[dict], *, kinds: set[str]) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for p in packs:
        for ctrl in p.get("control_results", []):
            cid = ctrl.get("control_id")
            if not cid or ctrl.get("kind", "check") not in kinds:
                continue
            s = stats.setdefault(cid, {"runs": 0, "pass": 0, "fail": 0})
            s["runs"] += 1
            if ctrl.get("passed"):
                s["pass"] += 1
            else:
                s["fail"] += 1
    return stats


def _control_name_map(matrix: dict) -> dict[str, str]:
    names: dict[str, str] = {}
    for risk in matrix["risks"]:
        for ctrl in risk.get("controls", []):
            names[ctrl["id"]] = f"{ctrl['id']} — {ctrl.get('name', '')}"
    return names


def _row_for_pack(pack: dict) -> dict[str, str]:
    src = (pack.get("source_documents") or [{}])[0]
    by_id = {c.get("control_id"): c for c in pack.get("control_results", [])}
    grounding = by_id.get("C1.1", {})
    coverage = by_id.get("C2.1", {})
    freshness = by_id.get("C3.1", {})
    routing = by_id.get("C6.1", {})

    missing = coverage.get("missing_categories") or []
    reasons = (
        routing.get("escalation_reasons")
        or routing.get("revise_reasons")
        or []
    )

    return {
        "run_id": pack.get("run_id", ""),
        "company": src.get("company", ""),
        "filing_date": str(src.get("filing_date") or ""),
        "final_status": pack.get("final_status", ""),
        "grounding": f"{grounding.get('grounding_score', '—')}",
        "age_days": f"{freshness.get('source_age_days', '—')}",
        "missing": ", ".join(missing) if missing else "—",
        "reviewer": pack.get("reviewer_id") or "—",
        "reasons": ", ".join(reasons) if reasons else "—",
        "notes": pack.get("reviewer_notes") or "—",
    }


def _lod_links() -> str:
    if not LOD_DIR.exists():
        return "<p class='empty'>No LoD artifacts yet.</p>"
    files = sorted(LOD_DIR.iterdir())
    if not files:
        return "<p class='empty'>No LoD artifacts yet.</p>"
    items = []
    for f in files:
        rel = f.relative_to(PROJECT_ROOT).as_posix()
        items.append(
            f"<li><a href='../{escape(rel)}'><code>{escape(f.name)}</code></a></li>"
        )
    return "<ul class='lod-list'>" + "".join(items) + "</ul>"


def render_html(packs: list[dict], matrix: dict) -> str:
    status_counts = Counter(p.get("final_status", "UNKNOWN") for p in packs)
    check_stats = _by_control(packs, kinds={"check"})
    human_stats = _by_control(packs, kinds={"human"})
    ctrl_names = _control_name_map(matrix)
    rows = [_row_for_pack(p) for p in packs]

    total = len(packs)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    tiles_html = "".join(
        f"""<div class="tile {STATUS_CLASS.get(status, 'status-unknown')}">
              <div class="tile-n">{count}</div>
              <div class="tile-label">{escape(status)}</div>
            </div>"""
        for status, count in sorted(status_counts.items())
    )

    check_rows_html = "".join(
        f"""<tr>
              <td>{escape(ctrl_names.get(cid, cid))}</td>
              <td class="num">{s['runs']}</td>
              <td class="num pass">{s['pass']}</td>
              <td class="num fail">{s['fail']}</td>
              <td class="num">{(s['pass']/s['runs']*100):.0f}%</td>
            </tr>"""
        for cid, s in sorted(check_stats.items())
    ) or "<tr><td colspan='5' class='empty'>No automated checks yet.</td></tr>"

    human_rows_html = "".join(
        f"""<tr>
              <td>{escape(ctrl_names.get(cid, cid))}</td>
              <td class="num">{s['runs']}</td>
              <td class="num pass">{s['pass']}</td>
              <td class="num fail">{s['runs'] - s['pass']}</td>
              <td class="num">{(s['pass']/s['runs']*100):.0f}%</td>
            </tr>"""
        for cid, s in sorted(human_stats.items())
    ) or "<tr><td colspan='5' class='empty'>No human reviews yet.</td></tr>"

    run_rows_html = "".join(
        f"""<tr>
              <td><code>{escape(r['run_id'])}</code></td>
              <td>{escape(r['company'])}</td>
              <td>{escape(r['filing_date'])}</td>
              <td><span class="pill {STATUS_CLASS.get(r['final_status'], 'status-unknown')}">{escape(r['final_status'])}</span></td>
              <td class="num">{escape(r['grounding'])}</td>
              <td class="num">{escape(r['age_days'])}</td>
              <td>{escape(r['missing'])}</td>
              <td>{escape(r['reasons'])}</td>
              <td>{escape(r['reviewer'])}</td>
              <td class="notes">{escape(r['notes'])}</td>
            </tr>"""
        for r in rows
    ) or "<tr><td colspan='10' class='empty'>No evidence packs found. Run <code>python run_demo.py</code> first.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NovaVest Research Summary Assistant v1 — Governance Dashboard</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", sans-serif; margin: 0; background: #f5f6f8; color: #1f2933; }}
  header {{ background: #1f2933; color: white; padding: 24px 32px; }}
  header h1 {{ margin: 0; font-size: 22px; font-weight: 600; }}
  header .sub {{ opacity: 0.7; font-size: 13px; margin-top: 4px; }}
  header .definition {{ margin-top: 14px; max-width: 980px; font-size: 13px; line-height: 1.55; opacity: 0.92; border-left: 3px solid #64748b; padding-left: 12px; }}
  main {{ padding: 24px 32px; max-width: 1400px; }}
  section {{ background: white; border-radius: 8px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  section h2 {{ margin: 0 0 16px; font-size: 16px; font-weight: 600; color: #334155; }}
  .tiles {{ display: flex; gap: 12px; flex-wrap: wrap; }}
  .tile {{ flex: 1; min-width: 140px; padding: 16px; border-radius: 8px; background: #f8fafc; border-left: 4px solid #94a3b8; }}
  .tile-n {{ font-size: 28px; font-weight: 600; }}
  .tile-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.7; margin-top: 4px; }}
  .status-approved  {{ border-left-color: #16a34a; }}
  .status-revise    {{ border-left-color: #f59e0b; }}
  .status-rejected  {{ border-left-color: #dc2626; }}
  .status-escalated {{ border-left-color: #d97706; }}
  .status-pending   {{ border-left-color: #2563eb; }}
  .pill {{ display: inline-block; padding: 2px 10px; border-radius: 99px; font-size: 11px; font-weight: 600; letter-spacing: 0.3px; background: #e2e8f0; color: #334155; }}
  .pill.status-approved  {{ background: #dcfce7; color: #15803d; }}
  .pill.status-revise    {{ background: #fef9c3; color: #a16207; }}
  .pill.status-rejected  {{ background: #fee2e2; color: #b91c1c; }}
  .pill.status-escalated {{ background: #fed7aa; color: #c2410c; }}
  .pill.status-pending   {{ background: #dbeafe; color: #1d4ed8; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
  th {{ background: #f8fafc; font-weight: 600; color: #475569; font-size: 12px; text-transform: uppercase; letter-spacing: 0.3px; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.pass {{ color: #15803d; font-weight: 600; }}
  td.fail {{ color: #b91c1c; font-weight: 600; }}
  td.notes {{ max-width: 320px; font-size: 12px; color: #475569; }}
  code {{ font-family: ui-monospace, "Cascadia Code", monospace; font-size: 12px; color: #475569; }}
  .empty {{ text-align: center; padding: 32px; color: #94a3b8; }}
  .lod-list {{ list-style: none; padding: 0; margin: 0; columns: 2; column-gap: 32px; }}
  .lod-list li {{ padding: 6px 0; break-inside: avoid; }}
  .lod-list a {{ color: #2563eb; text-decoration: none; }}
  .lod-list a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<header>
  <h1>NovaVest Research Summary Assistant v1 — Governance Dashboard</h1>
  <div class="sub">Generated {escape(generated)} · {total} runs</div>
  <div class="definition">{escape(FROZEN_SYSTEM_DEFINITION)}</div>
</header>
<main>
  <section>
    <h2>Release outcomes</h2>
    <div class="tiles">{tiles_html or '<div class="tile"><div class="tile-n">0</div><div class="tile-label">No runs</div></div>'}</div>
  </section>

  <section>
    <h2>Automated checks</h2>
    <table>
      <thead><tr><th>Control</th><th class="num">Runs</th><th class="num">Pass</th><th class="num">Fail</th><th class="num">Pass rate</th></tr></thead>
      <tbody>{check_rows_html}</tbody>
    </table>
  </section>

  <section>
    <h2>Human sign-offs</h2>
    <table>
      <thead><tr><th>Control</th><th class="num">Runs</th><th class="num">Signed</th><th class="num">Pending</th><th class="num">Sign-off rate</th></tr></thead>
      <tbody>{human_rows_html}</tbody>
    </table>
  </section>

  <section>
    <h2>Recent runs</h2>
    <table>
      <thead><tr><th>Run</th><th>Company</th><th>Filing date</th><th>Status</th><th class="num">Grounding</th><th class="num">Age (d)</th><th>Missing categories</th><th>Routing reasons</th><th>Reviewer</th><th>Reviewer notes</th></tr></thead>
      <tbody>{run_rows_html}</tbody>
    </table>
  </section>

  <section>
    <h2>Lab-based governance artifacts (LoD1 / LoD2 / LoD3)</h2>
    {_lod_links()}
  </section>
</main>
</body>
</html>
"""


def build_dashboard() -> Path:
    packs = _load_all_evidence()
    matrix = load_control_matrix()
    html = render_html(packs, matrix)
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")
    return DASHBOARD_PATH


def main() -> None:
    out = build_dashboard()
    print(f"Dashboard written: {out}")


if __name__ == "__main__":
    main()

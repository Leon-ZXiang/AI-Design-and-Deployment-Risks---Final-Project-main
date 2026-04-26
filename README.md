# NovaVest Research Summary Assistant v1

> NovaVest Research Summary Assistant v1 is a governed AI-assisted financial
> research summary workflow for internal analysts. It uses public company
> disclosures to generate first-draft summaries, and every output must pass
> control checks, review, and release decisions before it can be used beyond
> draft support.

Implementation of the frozen NovaVest spec — controls, sample cases, decision
logic, evidence packs, dashboard, and the lab-based governance artifacts
(LoD1 / LoD2 / LoD3).

## How to run the demo

```bash
pip install -r requirements.txt
python run_demo.py            # exercises the 3 frozen cases, writes evidence/*.json
python -m src.dashboard       # regenerates artifacts/dashboard.html
```

Open `artifacts/dashboard.html` in a browser to see the governance view.

## Frozen sample cases

| Case | Source | Final status | Why |
| --- | --- | --- | --- |
| 1 — Microsoft | `data/sources/microsoft_10q_excerpt.md` | APPROVED  | grounded summary, current source, all major risks covered, both sign-offs complete |
| 2 — Apple     | `data/sources/apple_10q_excerpt.md`     | REVISE    | mostly grounded, one important risk category missing — needs correction before approval |
| 3 — Nvidia    | `data/sources/nvidia_10q_excerpt.md`    | ESCALATED | multiple material risk categories missing — not safe to clear in normal path, requires higher review |

Sources are synthetic excerpts created for the prototype. They imitate
public-disclosure structure but are not real SEC filings.

## Frozen decision logic

| Outcome    | Trigger |
| ---------- | --- |
| APPROVED   | current source + grounded summary + all major risk categories covered + reviewer & analyst sign-off complete |
| REVISE     | mostly usable but missing exactly one important risk category |
| REJECT     | stale source or any other hard-control failure |
| ESCALATE   | unresolved serious issue — multiple missing categories, grounding below threshold, or unsupported material claim |

## Frozen control set

| Control | Name | Type | Module |
| --- | --- | --- | --- |
| C1.1 | Source-grounding check          | Hard gate     | `src/controls/grounding.py` |
| C1.2 | Reviewer claim verification     | Hard gate     | (human, senior reviewer) |
| C2.1 | Risk-factor coverage check      | Soft gate     | `src/controls/risk_coverage.py` |
| C3.1 | Source freshness validation     | Hard gate     | `src/controls/freshness.py` |
| C4.2 | Analyst sign-off before release | Hard gate     | (human, analyst) |
| C5.1 | Evidence-pack capture           | Required      | `src/evidence.py` |
| C6.1 | Escalation routing              | Soft gate     | `src/review.py` |

The earlier `C4.1 Draft labeling` control is no longer part of the frozen
control set. The `DRAFT — not approved for release` prefix is still applied
to every generated draft as response-text hygiene.

## Lab-based governance artifacts

Stored under `artifacts/lod/`:

| Lab artifact | File |
| --- | --- |
| LoD1 — Owner registration                  | `artifacts/lod/lab1_novavest_research_summary_assistant_v1.json` |
| LoD2 — MRM tiering decision (JSON)         | `artifacts/lod/384cca19-7811-426c-9254-430029e73c6f_risk_tiering.json` |
| LoD2 — Required controls checklist (JSON)  | `artifacts/lod/384cca19-7811-426c-9254-430029e73c6f_required_controls_checklist.json` |
| LoD2 — Executive summary (Markdown)        | `artifacts/lod/384cca19-7811-426c-9254-430029e73c6f_executive_summary.md` |
| LoD3 — Audit findings report (Markdown)    | `artifacts/lod/audit_findings_report.md` |
| LoD3 — Audit findings (JSON)               | `artifacts/lod/audit_findings.json` |

The three-line story the lab artifacts encode:

- **1L (owner)** — Tier 2, score 15
- **2L (MRM)** — independent challenge, Tier 1, score 28
- **3L (audit)** — documentation complete, score 28 reproduced, 5 of 6 Tier 1 controls still in progress

## Validation

Two ways to run the scenario assertions — both exercise the stub workflow,
neither requires an API key.

**Pure-Python (no extra install):**

```bash
python -m tests.test_scenarios
```

Expected:

```
PASS  Case 1 Microsoft -> APPROVED
PASS  Case 2 Apple     -> REVISE
PASS  Case 3 Nvidia    -> ESCALATED
PASS  smoke stale      -> REJECTED

4 passed, 0 failed
```

**Promptfoo (optional):**

```bash
npm install -g promptfoo
promptfoo eval -c tests/promptfooconfig.yaml
```

## Live LLM mode (OpenRouter)

The default `mode="stub"` uses a deterministic extractive draft so the
control pipeline works offline. To run real LLM drafts, install the optional
deps and put an OpenRouter key + model in `API.txt` at the project root:

```bash
pip install -r requirements-openai.txt
# API.txt:
#   key: sk-or-v1-...
#   model: google/gemma-4-26b-a4b-it:free
python -c "from src.workflow import run; print(run('data/sources/microsoft_10q_excerpt.md', generation_mode='openrouter', analyst_signoff='jsmith', senior_reviewer_signoff='kpatel')['final_status'])"
```

`API.txt` is in `.gitignore` and must never be committed.

## Repo map

| Frozen-spec piece           | File(s) |
| --- | --- |
| System definition           | top of this README + `src/dashboard.py` |
| Sample cases                | `data/sources/*.md`, `run_demo.py` |
| Decision logic              | `src/review.py` |
| Control set                 | `artifacts/control_matrix.yaml` |
| Evidence-pack template      | `src/evidence.py`, `evidence/run-*.json` |
| Dashboard                   | `src/dashboard.py`, `artifacts/dashboard.html` |
| Lab artifacts (LoD1/2/3)    | `artifacts/lod/` |
| Validation                  | `tests/test_scenarios.py`, `tests/promptfooconfig.yaml` |

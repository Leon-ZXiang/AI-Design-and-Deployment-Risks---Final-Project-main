"""Promptfoo Python-script provider for the release-review workflow.

Promptfoo (https://promptfoo.dev) is an LLM evaluation framework. Normally
it calls an LLM; here we wire it to our *stub* workflow instead, so the full
governance pipeline (§8.2) gets exercised by every promptfoo test case
without needing an API key or network access.

Promptfoo loads this file via ``providers: [file://promptfoo_provider.py]``
in ``promptfooconfig.yaml``. For each test case it calls ``call_api`` with
the vars dict; we invoke the workflow and return its result as a JSON
string so promptfoo assertions can parse it.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

# Make ``src`` importable when promptfoo runs this script from the tests dir.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.workflow import run  # noqa: E402


def _make_json_safe(obj):
    if is_dataclass(obj):
        return _make_json_safe(asdict(obj))
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def call_api(prompt, options=None, context=None):
    """Promptfoo provider entry point.

    ``prompt`` is unused — the real "inputs" live in ``context['vars']``
    since our workflow is source-file driven, not prompt driven.
    """
    vars_ = (context or {}).get("vars", {}) or {}

    source = vars_.get("source")
    if not source:
        return {"error": "missing required var 'source'"}

    source_path = (PROJECT_ROOT / source).resolve()
    if not source_path.exists():
        return {"error": f"source file not found: {source_path}"}

    try:
        result = run(
            source_path,
            generation_mode=vars_.get("generation_mode", "stub"),
            analyst_signoff=vars_.get("analyst") or None,
            senior_reviewer_signoff=vars_.get("senior") or None,
            reviewer_notes=vars_.get("reviewer_notes") or None,
        )
    except Exception as e:  # surface workflow errors to promptfoo
        return {"error": f"workflow failed: {e!r}"}

    safe = _make_json_safe(result)
    return {"output": json.dumps(safe)}

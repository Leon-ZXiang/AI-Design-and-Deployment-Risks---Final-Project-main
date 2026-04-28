"""Summary generation.

Two modes:

* ``mode="stub"`` (default) — returns an extractive draft derived from the
  source text so the pipeline can be exercised end-to-end without any
  network call. The stub mirrors the shape of a real LLM response (one
  paragraph per section) so downstream controls catch the same failure
  modes they would with a real model.

* ``mode="openrouter"`` — calls the OpenRouter chat-completions endpoint
  (OpenAI-compatible API) using the key + model in ``API.txt`` at the
  project root, or the matching ``OPENROUTER_*`` environment variables.
  Requires ``pip install requests`` (included in requirements.txt).

Generated drafts are always prefixed with the ``DRAFT — not approved for
release`` label as response-text hygiene (the workflow strips this off
its own copy of the response when needed).

``make_openrouter_judge()`` returns an LLM-as-judge callable for C1.1:
given a sentence and source text it returns True when the sentence is a
faithful paraphrase of something stated in the source.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import os
import re


SYSTEM_PROMPT = (
    "You are an AI research assistant for NovaVest Research. "
    "Summarize the attached public filing excerpt. Cover: key financial "
    "developments, material risk factors, management guidance, and notable "
    "business changes. Cite the source section for every claim. Do not "
    "speculate beyond the source text."
)


DRAFT_LABEL = "DRAFT — not approved for release"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "google/gemma-4-26b-a4b-it:free"
API_FILE = Path(__file__).resolve().parent.parent / "API.txt"


@dataclass
class GenerationResult:
    prompt: str
    response: str
    model: str
    output_label: str = DRAFT_LABEL

    def labeled_response(self) -> str:
        return f"[{self.output_label}]\n\n{self.response}"


def generate_draft(source_text: str, *, mode: str = "stub") -> GenerationResult:
    if mode == "stub":
        return _stub_response(source_text)
    if mode == "openrouter":
        return _openrouter_response(source_text)
    raise ValueError(f"unknown generation mode: {mode!r}")


_SECTION_SPLIT = re.compile(r"^##\s+", re.MULTILINE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _stub_response(source_text: str) -> GenerationResult:
    body = re.sub(r"^#\s+.*?\n", "", source_text, count=1, flags=re.MULTILINE)
    sections = _SECTION_SPLIT.split(body)
    summary_parts: list[str] = []
    for sec in sections[1:]:
        lines = sec.strip().split("\n", 1)
        if len(lines) < 2:
            continue
        section_body = lines[1].strip()
        sentences = [s for s in _SENTENCE_SPLIT.split(section_body) if s.strip()]
        if sentences:
            summary_parts.append(" ".join(sentences[:4]))
    response = "\n\n".join(summary_parts) or "No summarizable content found."
    prompt = f"{SYSTEM_PROMPT}\n\n---\nSOURCE:\n{source_text}"
    return GenerationResult(prompt=prompt, response=response, model="stub-extractive-v1")


def _read_api_file() -> dict[str, str]:
    if not API_FILE.exists():
        return {}
    out: dict[str, str] = {}
    for line in API_FILE.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip().lower()] = v.strip()
    return out


def _openrouter_response(source_text: str, *, max_retries: int = 5, base_delay: float = 5.0) -> GenerationResult:
    try:
        import requests  # type: ignore
        import time
    except ImportError as e:
        raise RuntimeError("openrouter mode requires `pip install requests`") from e

    creds = _read_api_file()
    api_key = os.environ.get("OPENROUTER_API_KEY") or creds.get("key")
    model = os.environ.get("OPENROUTER_MODEL") or creds.get("model") or DEFAULT_OPENROUTER_MODEL
    if not api_key:
        raise RuntimeError(
            "no OpenRouter API key found in API.txt or OPENROUTER_API_KEY env"
        )

    prompt = f"{SYSTEM_PROMPT}\n\n---\nSOURCE:\n{source_text}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"SOURCE:\n{source_text}"},
        ],
        "temperature": 0.2,
    }

    for attempt in range(max_retries):
        resp = requests.post(
            url=f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        if resp.status_code == 429:
            wait = base_delay * (2 ** attempt)
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                wait = max(wait, float(retry_after))
            print(f"[openrouter] rate limited, retrying in {wait:.0f}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        response = (resp.json()["choices"][0]["message"]["content"] or "").strip()
        return GenerationResult(prompt=prompt, response=response, model=model)

    raise RuntimeError(f"OpenRouter rate limit exceeded after {max_retries} retries")


_JUDGE_PROMPT = (
    "Answer only YES or NO — no other text.\n\n"
    "Is the following sentence a faithful paraphrase of, or directly supported "
    "by, something explicitly stated in the source text? "
    "Do not infer or extrapolate — only answer YES if the meaning is clearly "
    "present in the source.\n\n"
    "SOURCE:\n{source}\n\n"
    "SENTENCE:\n{sentence}"
)


def make_openrouter_judge(*, max_retries: int = 5, base_delay: float = 5.0) -> Callable[[str, str], bool]:
    """Return an LLM-as-judge callable for C1.1 semantic grounding.

    The returned function accepts (sentence, source_text) and returns True
    when the LLM judges the sentence to be grounded in the source.
    Uses the same OpenRouter credentials as generate_draft.
    """
    try:
        import requests  # type: ignore
        import time
    except ImportError as e:
        raise RuntimeError("openrouter mode requires `pip install requests`") from e

    creds = _read_api_file()
    api_key = os.environ.get("OPENROUTER_API_KEY") or creds.get("key")
    model = os.environ.get("OPENROUTER_MODEL") or creds.get("model") or DEFAULT_OPENROUTER_MODEL
    if not api_key:
        raise RuntimeError(
            "no OpenRouter API key found in API.txt or OPENROUTER_API_KEY env"
        )

    def judge(sentence: str, source_text: str) -> bool:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": _JUDGE_PROMPT.format(
                        source=source_text, sentence=sentence
                    ),
                }
            ],
            "temperature": 0.0,
            "max_tokens": 5,
        }
        for attempt in range(max_retries):
            resp = requests.post(
                url=f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            if resp.status_code == 429:
                wait = base_delay * (2 ** attempt)
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    wait = max(wait, float(retry_after))
                print(f"[openrouter judge] rate limited, retrying in {wait:.0f}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            answer = (resp.json()["choices"][0]["message"]["content"] or "").strip().upper()
            return answer.startswith("YES")
        # exhausted retries — treat as unsupported to be conservative
        print("[openrouter judge] rate limit exceeded, marking sentence as unsupported")
        return False

    return judge

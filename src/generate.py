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
  Requires ``pip install -r requirements-openai.txt``.

Generated drafts are always prefixed with the ``DRAFT — not approved for
release`` label as response-text hygiene (the workflow strips this off
its own copy of the response when needed).
"""
from dataclasses import dataclass
from pathlib import Path
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


def _openrouter_response(source_text: str) -> GenerationResult:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "openrouter mode requires `pip install -r requirements-openai.txt`"
        ) from e

    creds = _read_api_file()
    api_key = os.environ.get("OPENROUTER_API_KEY") or creds.get("key")
    model = os.environ.get("OPENROUTER_MODEL") or creds.get("model") or DEFAULT_OPENROUTER_MODEL
    if not api_key:
        raise RuntimeError(
            "no OpenRouter API key found in API.txt or OPENROUTER_API_KEY env"
        )

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)
    prompt = f"{SYSTEM_PROMPT}\n\n---\nSOURCE:\n{source_text}"
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"SOURCE:\n{source_text}"},
        ],
        temperature=0.2,
    )
    response = (completion.choices[0].message.content or "").strip()
    return GenerationResult(prompt=prompt, response=response, model=model)

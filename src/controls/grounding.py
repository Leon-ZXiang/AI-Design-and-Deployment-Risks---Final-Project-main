"""C1.1 Source-grounding check (Control Matrix, Risk R1).

Baseline, deterministic implementation: split the draft into sentences, extract
content tokens (numbers, capitalized multi-word phrases, dollar amounts), and
check that each token appears in the source text. Sentences whose content
tokens are all present in the source are considered grounded.

This is a stand-in for the LLM-as-judge grounding check that will be added
once the OpenAI client is wired up in Section 7.
"""
from dataclasses import dataclass, field
import re


_NUMBER = re.compile(r"\$?\d+(?:\.\d+)?(?:[–-]\$?\d+(?:\.\d+)?)?%?")
_PROPER = re.compile(r"(?:[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class GroundingResult:
    control_id: str = "C1.1"
    grounding_score: float = 0.0
    unsupported_sentences: list[str] = field(default_factory=list)
    total_sentences: int = 0
    passed: bool = False

    def as_evidence(self) -> dict:
        return {
            "control_id": self.control_id,
            "kind": "check",
            "grounding_score": round(self.grounding_score, 3),
            "unsupported_sentences": self.unsupported_sentences,
            "total_sentences": self.total_sentences,
            "passed": self.passed,
        }


def check_grounding(
    draft: str, source_text: str, *, pass_threshold: float = 0.90
) -> GroundingResult:
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(draft) if s.strip()]
    source_norm = source_text.lower()

    unsupported: list[str] = []
    supported_count = 0

    for sent in sentences:
        tokens = _extract_content_tokens(sent)
        if not tokens:
            supported_count += 1
            continue
        missing = [t for t in tokens if t.lower() not in source_norm]
        if missing:
            unsupported.append(sent)
        else:
            supported_count += 1

    total = len(sentences) or 1
    score = supported_count / total
    return GroundingResult(
        grounding_score=score,
        unsupported_sentences=unsupported,
        total_sentences=total,
        passed=score >= pass_threshold and not unsupported,
    )


def _extract_content_tokens(sentence: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(_NUMBER.findall(sentence))
    tokens.extend(_PROPER.findall(sentence))
    seen = set()
    deduped = []
    for t in tokens:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    return deduped

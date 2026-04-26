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
# split on sentence boundaries OR any newline so bullet lists/headings become individual chunks
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_MD_HEADING = re.compile(r"^#+\s*.*$", re.MULTILINE)
# match both **Label:** (colon inside bold) and **Label**: (colon outside bold)
_MD_BOLD_LABEL = re.compile(r"\*{1,2}[^*\n]+:\s*\*{1,2}|\*{1,2}[^*\n]+\*{1,2}\s*:")
_MD_BOLD = re.compile(r"\*{1,2}([^*\n]+)\*{1,2}")
_MD_TABLE_ROW = re.compile(r"^\|[^\n]+", re.MULTILINE)
_MD_HR = re.compile(r"^[-]{3,}$", re.MULTILINE)
_MD_LIST = re.compile(r"^[-*]\s+", re.MULTILINE)
_MD_SOURCE_TAG = re.compile(
    r"\(Source:[^)]*\)|\[Source:[^\]]*\]|\*Source:[^*]*\*|Source:\s*[^\n,;.]+",
    re.IGNORECASE,
)
# sentences that note the ABSENCE of a section are meta-commentary, not factual claims
_ABSENCE_NOTICE = re.compile(
    r"[—\-]\s*(?:no|not)\b|not (?:present|included|provided)\b|limited to\b",
    re.IGNORECASE,
)


def _strip_markdown(text: str) -> str:
    text = _MD_SOURCE_TAG.sub("", text)
    text = _MD_HEADING.sub("", text)
    text = _MD_BOLD_LABEL.sub("", text)
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_TABLE_ROW.sub("", text)
    text = _MD_HR.sub("", text)
    text = _MD_LIST.sub("", text)
    return text.strip()


def _token_in_source(token: str, source_norm: str) -> bool:
    t = token.lower()
    if t in source_norm:
        return True
    # "41%" matches source text "41 to 42 percent" via bare number
    if t.endswith("%") and t[:-1] in source_norm:
        return True
    return False


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
        clean = _strip_markdown(sent)
        if not clean:          # pure decoration (heading, hr, empty line)
            supported_count += 1
            continue
        tokens = _extract_content_tokens(clean)
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

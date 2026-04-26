"""Load a source document and attach the metadata the controls need."""
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re


@dataclass
class SourceDocument:
    path: Path
    company: str
    ticker: str
    document_type: str
    filing_date: date
    text: str


_META_PATTERNS = {
    "filing_date": re.compile(r"Filing date:\s*(\d{4}-\d{2}-\d{2})"),
    "company": re.compile(r"^#\s+(.+?)\s+—", re.MULTILINE),
}


def load_source(path: str | Path) -> SourceDocument:
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    company_match = _META_PATTERNS["company"].search(text)
    company = company_match.group(1).strip() if company_match else path.stem

    date_match = _META_PATTERNS["filing_date"].search(text)
    filing_date = (
        datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
        if date_match
        else date.today()
    )

    return SourceDocument(
        path=path,
        company=company,
        ticker=company.split()[0].upper()[:4],
        document_type="10-Q" if "10-Q" in text else "filing",
        filing_date=filing_date,
        text=text,
    )

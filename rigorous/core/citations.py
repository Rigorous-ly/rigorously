"""Citation verification against CrossRef API.

Parses .bib files and verifies each entry's DOI, title, authors, and journal
against the CrossRef database. Flags fabricated or erroneous entries.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal


@dataclass
class CitationEntry:
    """A parsed bibliography entry."""

    key: str
    entry_type: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    doi: str = ""
    journal: str = ""
    year: str = ""
    raw: str = ""


@dataclass
class CitationFinding:
    """Result of verifying a single citation."""

    key: str
    severity: Literal["critical", "warning", "info"]
    issue: str
    details: str = ""
    doi: str = ""


def _parse_bib_field(entry_text: str, field_name: str) -> str:
    """Extract a field value from a bibtex entry."""
    # Match field = {value} or field = "value" or field = value
    pattern = rf"{field_name}\s*=\s*(?:\{{([^}}]*)\}}|\"([^\"]*)\"|(\S+))"
    m = re.search(pattern, entry_text, re.IGNORECASE | re.DOTALL)
    if m:
        return (m.group(1) or m.group(2) or m.group(3) or "").strip()
    return ""


def _parse_authors(author_str: str) -> list[str]:
    """Parse bibtex author string into list of author names."""
    if not author_str:
        return []
    # Split on " and "
    authors = re.split(r"\s+and\s+", author_str, flags=re.IGNORECASE)
    result = []
    for a in authors:
        a = a.strip().strip("{}")
        # Remove LaTeX commands
        a = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", a)
        a = re.sub(r"[{}]", "", a)
        if a:
            result.append(a.strip())
    return result


def parse_bib_file(filepath: str | Path) -> list[CitationEntry]:
    """Parse a .bib file into CitationEntry objects.

    Args:
        filepath: Path to a .bib file.

    Returns:
        List of parsed citation entries.
    """
    filepath = Path(filepath)
    text = filepath.read_text(encoding="utf-8", errors="replace")

    entries: list[CitationEntry] = []

    # Match @type{key, ... }
    # We need to handle nested braces, so we do a manual parse
    entry_starts = list(re.finditer(r"@(\w+)\s*\{(\s*[^,\s]+)\s*,", text))

    for idx, match in enumerate(entry_starts):
        entry_type = match.group(1).lower()
        key = match.group(2).strip()

        # Find the end of this entry (matching closing brace)
        start = match.start()
        brace_start = text.index("{", start)
        depth = 1
        pos = brace_start + 1
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        entry_text = text[brace_start:pos]

        # Skip non-citation types
        if entry_type in ("string", "preamble", "comment"):
            continue

        entry = CitationEntry(
            key=key,
            entry_type=entry_type,
            title=_parse_bib_field(entry_text, "title"),
            authors=_parse_authors(_parse_bib_field(entry_text, "author")),
            doi=_parse_bib_field(entry_text, "doi"),
            journal=_parse_bib_field(entry_text, "journal"),
            year=_parse_bib_field(entry_text, "year"),
            raw=entry_text,
        )
        entries.append(entry)

    return entries


def _normalize(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    text = re.sub(r"[{}\\]", "", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    # Remove common LaTeX artifacts
    text = re.sub(r"\\[a-z]+", "", text)
    return text


def _title_similarity(a: str, b: str) -> float:
    """Compute title similarity ratio."""
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _author_overlap(bib_authors: list[str], crossref_authors: list[dict]) -> float:
    """Compute author overlap ratio."""
    if not bib_authors or not crossref_authors:
        return 0.0

    # Extract family names from CrossRef
    cr_names = []
    for a in crossref_authors:
        family = a.get("family", "")
        if family:
            cr_names.append(_normalize(family))

    if not cr_names:
        return 0.0

    # Extract last names from bib authors
    bib_names = []
    for a in bib_authors:
        # Handle "Last, First" and "First Last" formats
        parts = a.split(",")
        if len(parts) >= 2:
            bib_names.append(_normalize(parts[0]))
        else:
            parts = a.strip().split()
            if parts:
                bib_names.append(_normalize(parts[-1]))

    if not bib_names:
        return 0.0

    # Count matches
    matches = 0
    for bn in bib_names:
        for cn in cr_names:
            if bn in cn or cn in bn or SequenceMatcher(None, bn, cn).ratio() > 0.8:
                matches += 1
                break

    return matches / max(len(bib_names), len(cr_names))


async def verify_doi(doi: str, client: Any = None) -> dict:
    """Verify a single DOI against CrossRef.

    Args:
        doi: The DOI string.
        client: Optional httpx.AsyncClient (will create one if not provided).

    Returns:
        Dict with CrossRef metadata or error information.
    """
    import httpx

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=30.0)
        close_client = True

    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {
            "User-Agent": "Rigorous/0.1.0 (https://github.com/rigorous; mailto:research@rigorous.dev)",
        }
        response = await client.get(url, headers=headers, follow_redirects=True)

        if response.status_code == 200:
            data = response.json()
            return {"status": "found", "data": data.get("message", {})}
        elif response.status_code == 404:
            return {"status": "not_found", "error": f"DOI not found: {doi}"}
        else:
            return {"status": "error", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if close_client:
            await client.aclose()


async def verify_citations(
    entries: list[CitationEntry],
    rate_limit: float = 1.0,
) -> list[CitationFinding]:
    """Verify a list of citation entries against CrossRef.

    Args:
        entries: Parsed citation entries.
        rate_limit: Minimum seconds between API requests (CrossRef polite pool).

    Returns:
        List of findings about problematic citations.
    """
    import httpx

    findings: list[CitationFinding] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        last_request_time = 0.0

        for entry in entries:
            # Rate limiting
            now = time.monotonic()
            elapsed = now - last_request_time
            if elapsed < rate_limit:
                await asyncio.sleep(rate_limit - elapsed)

            # If no DOI, flag it
            if not entry.doi:
                findings.append(
                    CitationFinding(
                        key=entry.key,
                        severity="info",
                        issue="no_doi",
                        details=f"Entry '{entry.key}' has no DOI. Cannot verify against CrossRef.",
                    )
                )
                continue

            # Clean DOI
            doi = entry.doi.strip()
            doi = re.sub(r"^https?://doi\.org/", "", doi)
            doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)

            last_request_time = time.monotonic()
            result = await verify_doi(doi, client)

            if result["status"] == "not_found":
                findings.append(
                    CitationFinding(
                        key=entry.key,
                        severity="critical",
                        issue="doi_not_found",
                        details=f"DOI '{doi}' does not resolve. This citation may be fabricated.",
                        doi=doi,
                    )
                )
                continue

            if result["status"] == "error":
                findings.append(
                    CitationFinding(
                        key=entry.key,
                        severity="info",
                        issue="api_error",
                        details=f"Could not verify DOI '{doi}': {result['error']}",
                        doi=doi,
                    )
                )
                continue

            # DOI found -- verify metadata
            cr_data = result["data"]
            cr_title_list = cr_data.get("title", [])
            cr_title = cr_title_list[0] if cr_title_list else ""
            cr_authors = cr_data.get("author", [])
            cr_journal = ""
            container = cr_data.get("container-title", [])
            if container:
                cr_journal = container[0]

            # Check title match
            if entry.title and cr_title:
                sim = _title_similarity(entry.title, cr_title)
                if sim < 0.6:
                    findings.append(
                        CitationFinding(
                            key=entry.key,
                            severity="critical",
                            issue="title_mismatch",
                            details=(
                                f"Title mismatch (similarity={sim:.2f}). "
                                f"Bib: '{entry.title[:80]}...' vs "
                                f"CrossRef: '{cr_title[:80]}...'"
                            ),
                            doi=doi,
                        )
                    )
                elif sim < 0.85:
                    findings.append(
                        CitationFinding(
                            key=entry.key,
                            severity="warning",
                            issue="title_partial_mismatch",
                            details=(
                                f"Title partially matches (similarity={sim:.2f}). "
                                f"Bib: '{entry.title[:80]}' vs "
                                f"CrossRef: '{cr_title[:80]}'"
                            ),
                            doi=doi,
                        )
                    )

            # Check author overlap
            if entry.authors and cr_authors:
                overlap = _author_overlap(entry.authors, cr_authors)
                if overlap < 0.3:
                    findings.append(
                        CitationFinding(
                            key=entry.key,
                            severity="critical",
                            issue="author_mismatch",
                            details=(
                                f"Author mismatch (overlap={overlap:.2f}). "
                                f"Bib authors: {entry.authors[:3]} vs "
                                f"CrossRef authors: {[a.get('family', '?') for a in cr_authors[:3]]}"
                            ),
                            doi=doi,
                        )
                    )
                elif overlap < 0.6:
                    findings.append(
                        CitationFinding(
                            key=entry.key,
                            severity="warning",
                            issue="author_partial_mismatch",
                            details=f"Author partial mismatch (overlap={overlap:.2f}).",
                            doi=doi,
                        )
                    )

            # Check journal match
            if entry.journal and cr_journal:
                j_sim = SequenceMatcher(
                    None, _normalize(entry.journal), _normalize(cr_journal)
                ).ratio()
                if j_sim < 0.5:
                    findings.append(
                        CitationFinding(
                            key=entry.key,
                            severity="warning",
                            issue="journal_mismatch",
                            details=(
                                f"Journal mismatch. "
                                f"Bib: '{entry.journal}' vs CrossRef: '{cr_journal}'"
                            ),
                            doi=doi,
                        )
                    )

    return findings


def verify_bib_file(filepath: str | Path, rate_limit: float = 1.0) -> list[CitationFinding]:
    """Synchronous wrapper: parse and verify a .bib file.

    Args:
        filepath: Path to .bib file.
        rate_limit: Seconds between CrossRef API requests.

    Returns:
        List of citation findings.
    """
    entries = parse_bib_file(filepath)
    return asyncio.run(verify_citations(entries, rate_limit=rate_limit))

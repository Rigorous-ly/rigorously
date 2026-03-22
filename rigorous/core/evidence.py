"""Evidence mapping — trace paper claims to supporting code.

Extracts quantitative claims from Results/Discussion sections and attempts
to find supporting evidence in code files (Python scripts). Flags claims
with no traceable computational evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class Claim:
    """A quantitative claim extracted from the manuscript."""

    text: str
    line: int
    section: str
    numbers: list[str]  # Specific numbers in the claim


@dataclass
class EvidenceFinding:
    """A finding about evidence traceability."""

    file: str
    line: int
    severity: Literal["critical", "warning", "info"]
    issue: str
    claim_text: str
    details: str


# Number extraction pattern
NUMBER_RE = re.compile(
    r"(?:\d+\.?\d*(?:e[+-]?\d+)?)\s*(?:%|\\%|fold|x\b|days?|hours?|ms|seconds?|Hz|mg|mL|kg|mmol|nmol|nM|mM|uM|\u03bcM)?",
    re.IGNORECASE,
)


def _detect_section_tex(lines: list[str]) -> list[tuple[int, int, str]]:
    """Detect section boundaries in a LaTeX file.

    Returns:
        List of (start_line, end_line, section_name).
    """
    sections: list[tuple[int, str]] = []
    section_re = re.compile(r"\\(?:section|subsection)\*?\{([^}]+)\}")

    for i, line in enumerate(lines):
        m = section_re.search(line)
        if m:
            sections.append((i, m.group(1).strip().lower()))

    if not sections:
        return [(0, len(lines), "body")]

    result: list[tuple[int, int, str]] = []
    for idx in range(len(sections)):
        start = sections[idx][0]
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(lines)
        result.append((start, end, sections[idx][1]))

    return result


def _is_results_or_discussion(section_name: str) -> bool:
    """Check if a section name is Results or Discussion."""
    keywords = ["result", "discussion", "finding", "outcome", "analysis", "evaluation"]
    return any(kw in section_name for kw in keywords)


def _extract_claims(lines: list[str], filepath: str) -> list[Claim]:
    """Extract quantitative claims from results/discussion sections."""
    ext = Path(filepath).suffix.lower()
    claims: list[Claim] = []

    if ext == ".tex":
        sections = _detect_section_tex(lines)
        for start, end, section_name in sections:
            if not _is_results_or_discussion(section_name):
                continue
            for i in range(start, end):
                line = lines[i]
                numbers = NUMBER_RE.findall(line)
                if numbers and len(numbers) >= 1:
                    # This line makes a quantitative claim
                    claims.append(
                        Claim(
                            text=line.strip(),
                            line=i + 1,
                            section=section_name,
                            numbers=[n.strip() for n in numbers],
                        )
                    )
    elif ext == ".md":
        in_relevant = False
        current_section = "body"
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if stripped.startswith("#"):
                current_section = stripped.lstrip("#").strip()
                in_relevant = _is_results_or_discussion(current_section)
                continue
            if in_relevant:
                numbers = NUMBER_RE.findall(line)
                if numbers and len(numbers) >= 1:
                    claims.append(
                        Claim(
                            text=line.strip(),
                            line=i + 1,
                            section=current_section,
                            numbers=[n.strip() for n in numbers],
                        )
                    )

    return claims


def _search_code_for_number(
    number_str: str,
    code_files: list[Path],
) -> list[tuple[Path, int, str]]:
    """Search code files for a specific number.

    Returns:
        List of (file, line, context) where the number appears.
    """
    # Clean the number string
    clean = re.sub(r"[%\\fold x]", "", number_str, flags=re.IGNORECASE).strip()
    if not clean:
        return []

    matches: list[tuple[Path, int, str]] = []

    for code_file in code_files:
        try:
            code_text = code_file.read_text(encoding="utf-8", errors="replace")
            code_lines = code_text.splitlines()
        except Exception:
            continue

        for i, line in enumerate(code_lines, start=1):
            if clean in line:
                matches.append((code_file, i, line.strip()[:120]))

    return matches


def check_evidence(
    tex_filepath: str | Path,
    code_directory: str | Path | None = None,
) -> list[EvidenceFinding]:
    """Map claims to supporting code evidence.

    Args:
        tex_filepath: Path to .tex or .md manuscript.
        code_directory: Directory containing Python code to search.
            If None, searches parent directory of the tex file.

    Returns:
        List of EvidenceFinding objects.
    """
    tex_filepath = Path(tex_filepath)
    if not tex_filepath.exists():
        raise FileNotFoundError(f"File not found: {tex_filepath}")

    if code_directory is None:
        code_directory = tex_filepath.parent
    code_directory = Path(code_directory)

    text = tex_filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    claims = _extract_claims(lines, str(tex_filepath))
    findings: list[EvidenceFinding] = []

    if not claims:
        findings.append(
            EvidenceFinding(
                file=str(tex_filepath),
                line=0,
                severity="info",
                issue="no_claims_found",
                claim_text="",
                details="No quantitative claims found in Results/Discussion sections.",
            )
        )
        return findings

    # Collect code files
    code_files = list(code_directory.rglob("*.py"))
    if not code_files:
        findings.append(
            EvidenceFinding(
                file=str(tex_filepath),
                line=0,
                severity="info",
                issue="no_code_files",
                claim_text="",
                details=f"No Python files found in {code_directory}.",
            )
        )
        return findings

    # For each claim, search for supporting code evidence
    for claim in claims:
        has_evidence = False
        for number in claim.numbers:
            code_matches = _search_code_for_number(number, code_files)
            if code_matches:
                has_evidence = True
                break

        if not has_evidence:
            findings.append(
                EvidenceFinding(
                    file=str(tex_filepath),
                    line=claim.line,
                    severity="warning",
                    issue="claim_no_code_evidence",
                    claim_text=claim.text[:120],
                    details=(
                        f"Claim in '{claim.section}' (line {claim.line}) contains "
                        f"numbers {claim.numbers} but no matching values found in "
                        f"Python code under {code_directory}."
                    ),
                )
            )

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 9), f.line))

    return findings

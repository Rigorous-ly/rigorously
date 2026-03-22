"""Overclaim detection for research manuscripts.

Scans .tex and .md files for language patterns that overstate results,
returning structured findings with severity levels and suggested alternatives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class OverclaimFinding:
    """A single overclaim detection result."""

    file: str
    line: int
    matched_text: str
    pattern_name: str
    severity: Literal["critical", "warning", "info"]
    suggestion: str
    context: str = ""  # surrounding line text


# Each pattern: (compiled regex, pattern_name, severity, suggestion)
# Regexes use word boundaries and negative lookbehinds/lookaheads where needed.
OVERCLAIM_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    # --- Critical ---
    (
        re.compile(
            r"\bproven\b|\bproves\b|\bproof\s+that\b",
            re.IGNORECASE,
        ),
        "proof_language",
        "critical",
        "Models provide evidence, not proof. Use 'supports,' 'is consistent with,' or 'provides evidence that.'",
    ),
    (
        re.compile(
            r"(?<!not\s)(?<!qualitatively\s)\bvalidated\b",
            re.IGNORECASE,
        ),
        "validated",
        "critical",
        "'Validated' implies ground-truth comparison. Use 'calibrated,' 'consistent with observations,' or 'qualitatively validated' if appropriate.",
    ),
    (
        re.compile(
            r"\bimpossible\b",
            re.IGNORECASE,
        ),
        "impossible",
        "critical",
        "'Impossible' is almost never defensible. Use 'infeasible,' 'not observed,' or 'unlikely under these conditions.'",
    ),
    (
        re.compile(
            r"\bmachine[\s-]precision\b",
            re.IGNORECASE,
        ),
        "machine_precision",
        "critical",
        "Machine-precision agreement is suspicious for biological/stochastic models. Specify the actual tolerance achieved.",
    ),
    (
        re.compile(
            r"\bstatistically\s+indistinguishable\b",
            re.IGNORECASE,
        ),
        "statistically_indistinguishable",
        "critical",
        "Non-significance does not mean equivalence. Use equivalence testing (TOST) or report effect sizes with confidence intervals.",
    ),
    # --- Warning ---
    (
        re.compile(
            r"\bconfirms\b|\bdemonstrates\s+that\b",
            re.IGNORECASE,
        ),
        "confirms_demonstrates",
        "warning",
        "Models predict or suggest; they do not confirm or demonstrate. Use 'predicts,' 'suggests,' or 'indicates.'",
    ),
    (
        re.compile(
            r"\bfirst[\s-]ever\b|\bfirst\s+of\s+its\s+kind\b|\bunprecedented\b",
            re.IGNORECASE,
        ),
        "priority_claim",
        "warning",
        "Priority claims invite challenge. Verify exhaustively or soften to 'to our knowledge, the first.'",
    ),
    (
        re.compile(
            r"\bdefinitively\b|\bconclusively\b|\bunequivocally\b",
            re.IGNORECASE,
        ),
        "definitive_language",
        "warning",
        "Definitive/conclusive language overstates the strength of evidence. Use 'strongly suggests' or 'provides robust evidence.'",
    ),
    (
        re.compile(
            r"\bground[\s-]?breaking\b|\brevolutionary\b|\bparadigm[\s-]?shift\b",
            re.IGNORECASE,
        ),
        "hyperbole",
        "warning",
        "Hyperbolic language weakens credibility. Let the results speak for themselves.",
    ),
    (
        re.compile(
            r"\balways\b(?!\s+(?:positive|negative|true|false|zero|one))",
            re.IGNORECASE,
        ),
        "always",
        "warning",
        "'Always' is a universal claim. Use 'consistently,' 'in all tested conditions,' or 'across all simulations.'",
    ),
    (
        re.compile(
            r"\bnever\b(?!\s+(?:negative|positive|zero|exceed))",
            re.IGNORECASE,
        ),
        "never",
        "warning",
        "'Never' is a universal claim. Use 'was not observed,' 'did not occur in any trial,' or specify conditions.",
    ),
    # --- Info ---
    (
        re.compile(
            r"\bsignificant\b(?!\s*(?:at|p\s*[<=<]))",
            re.IGNORECASE,
        ),
        "significant_ambiguous",
        "info",
        "'Significant' without statistical context is ambiguous. Specify 'statistically significant (p < X)' or use 'substantial'/'notable.'",
    ),
    (
        re.compile(
            r"\bclearly\b|\bobviously\b|\bundoubtedly\b",
            re.IGNORECASE,
        ),
        "clearly_obviously",
        "info",
        "If it were obvious, you wouldn't need to say so. Remove or replace with specific evidence.",
    ),
    (
        re.compile(
            r"\binterestingly\b|\bsurprisingly\b|\bremarkably\b|\bstrikingly\b",
            re.IGNORECASE,
        ),
        "editorial_adverb",
        "info",
        "Editorial adverbs add no information. State the finding and let the reader judge its significance.",
    ),
]


def _is_in_comment(line: str, match_start: int, file_ext: str) -> bool:
    """Check if a match position is inside a comment for the given file type."""
    if file_ext == ".tex":
        # In LaTeX, % starts a comment (unless escaped with \%)
        for i in range(match_start):
            if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
                return True
    elif file_ext == ".md":
        # In Markdown, HTML comments <!-- ... -->
        stripped = line[:match_start]
        if "<!--" in stripped and "-->" not in stripped:
            return True
    return False


def _check_novel_in_abstract(lines: list[str], filepath: str) -> list[OverclaimFinding]:
    """Special check: 'novel' in abstract is a red flag."""
    findings: list[OverclaimFinding] = []
    in_abstract = False
    novel_re = re.compile(r"\bnovel\b", re.IGNORECASE)
    ext = Path(filepath).suffix.lower()

    for i, line in enumerate(lines, start=1):
        # Detect abstract boundaries
        if ext == ".tex":
            if r"\begin{abstract}" in line:
                in_abstract = True
                continue
            if r"\end{abstract}" in line:
                in_abstract = False
                continue
        elif ext == ".md":
            lower = line.strip().lower()
            if lower.startswith("## abstract") or lower.startswith("# abstract"):
                in_abstract = True
                continue
            if in_abstract and line.strip().startswith("#"):
                in_abstract = False
                continue

        if in_abstract:
            for m in novel_re.finditer(line):
                if not _is_in_comment(line, m.start(), ext):
                    findings.append(
                        OverclaimFinding(
                            file=filepath,
                            line=i,
                            matched_text=m.group(),
                            pattern_name="novel_in_abstract",
                            severity="warning",
                            suggestion="'Novel' in abstracts invites reviewers to search for prior art. "
                            "Use specific language: 'We introduce X, which differs from Y by Z.'",
                            context=line.rstrip(),
                        )
                    )
    return findings


def check_overclaims(filepath: str | Path) -> list[OverclaimFinding]:
    """Scan a single file for overclaim patterns.

    Args:
        filepath: Path to a .tex or .md file.

    Returns:
        List of OverclaimFinding objects, sorted by (severity, line).
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = filepath.suffix.lower()
    if ext not in (".tex", ".md", ".txt", ".rst"):
        raise ValueError(f"Unsupported file type: {ext}. Supported: .tex, .md, .txt, .rst")

    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    findings: list[OverclaimFinding] = []

    for line_num, line in enumerate(lines, start=1):
        for pattern, name, severity, suggestion in OVERCLAIM_PATTERNS:
            for match in pattern.finditer(line):
                if not _is_in_comment(line, match.start(), ext):
                    findings.append(
                        OverclaimFinding(
                            file=str(filepath),
                            line=line_num,
                            matched_text=match.group(),
                            pattern_name=name,
                            severity=severity,
                            suggestion=suggestion,
                            context=line.rstrip(),
                        )
                    )

    # Special check for "novel" in abstract
    findings.extend(_check_novel_in_abstract(lines, str(filepath)))

    # Sort: critical first, then warning, then info; within severity by line number
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 9), f.line))

    return findings


def check_overclaims_in_directory(directory: str | Path, extensions: tuple[str, ...] = (".tex", ".md")) -> list[OverclaimFinding]:
    """Scan all matching files in a directory tree.

    Args:
        directory: Root directory to scan.
        extensions: File extensions to check.

    Returns:
        Combined list of findings from all files.
    """
    directory = Path(directory)
    findings: list[OverclaimFinding] = []
    for ext in extensions:
        for fp in directory.rglob(f"*{ext}"):
            try:
                findings.extend(check_overclaims(fp))
            except (ValueError, FileNotFoundError):
                continue
    return findings

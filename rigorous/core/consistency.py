"""Number consistency checking across a manuscript.

Extracts all specific numbers (percentages, fold-changes, p-values, days,
sample sizes) from .tex files and checks that each number appears
consistently across abstract, body, tables, and captions.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class NumberInstance:
    """A specific number found in the manuscript."""

    value: str  # The raw matched string, e.g., "3.7%", "p < 0.05"
    normalized: float | None  # Parsed numeric value, if possible
    line: int
    section: str  # "abstract", "body", "table", "caption", "title"
    context: str  # Surrounding text


@dataclass
class ConsistencyFinding:
    """A contradiction or inconsistency in reported numbers."""

    severity: Literal["critical", "warning", "info"]
    issue: str
    instances: list[NumberInstance]
    details: str


# Patterns for extracting numbers with context
NUMBER_PATTERNS = [
    # Percentages: 42.3%, 42.3 %, 42.3 percent
    (r"(\d+\.?\d*)\s*(?:%|\\%|percent)", "percentage"),
    # P-values: p < 0.05, p = 0.001, p-value = 0.05
    (r"p[\s-]*(?:value)?\s*[<=>\u2264\u2265]\s*(\d+\.?\d*(?:e[+-]?\d+)?)", "p_value"),
    # Fold changes: 2.5-fold, 2.5x
    (r"(\d+\.?\d*)\s*[-\u2013]?\s*fold|(\d+\.?\d*)\s*[xX](?:\s|,|\.)", "fold_change"),
    # Sample sizes: n = 42, N = 100, n=42
    (r"[nN]\s*=\s*(\d+)", "sample_size"),
    # Days/hours/minutes/weeks
    (r"(\d+\.?\d*)\s*(?:days?|hours?|hrs?|minutes?|mins?|weeks?|months?|years?)", "time_value"),
    # Specific numeric claims: numbers with units
    (r"(\d+\.?\d*)\s*(?:mg|mL|kg|mmol|nmol|pmol|ng|pg|mM|nM|\u03bcM|uM|Hz|kHz|MHz)", "measurement"),
    # Standalone decimal numbers in scientific context (2+ digits or has decimal)
    (r"(?<![.\d])(\d+\.\d+)(?![.\d])", "decimal"),
]


def _detect_section(line: str, current_section: str, file_ext: str) -> str:
    """Determine which section a line belongs to (LaTeX or Markdown)."""
    if file_ext == ".tex":
        if r"\begin{abstract}" in line:
            return "abstract"
        if r"\end{abstract}" in line:
            return "body"
        if r"\begin{table" in line:
            return "table"
        if r"\end{table" in line:
            return "body"
        if r"\caption" in line:
            return "caption"
        if r"\begin{figure" in line:
            return "caption"
        if r"\end{figure" in line:
            return "body"
        if re.search(r"\\(?:section|subsection|subsubsection|chapter)\b", line):
            return "body"
        if r"\title" in line:
            return "title"
    elif file_ext == ".md":
        stripped = line.strip().lower()
        if stripped.startswith("# ") or stripped.startswith("## "):
            if "abstract" in stripped:
                return "abstract"
            return "body"
    return current_section


def extract_numbers(filepath: str | Path) -> list[NumberInstance]:
    """Extract all specific numbers from a manuscript file.

    Args:
        filepath: Path to .tex or .md file.

    Returns:
        List of NumberInstance objects.
    """
    filepath = Path(filepath)
    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    ext = filepath.suffix.lower()

    instances: list[NumberInstance] = []
    current_section = "body"

    for line_num, line in enumerate(lines, start=1):
        current_section = _detect_section(line, current_section, ext)

        for pattern_str, num_type in NUMBER_PATTERNS:
            for m in re.finditer(pattern_str, line, re.IGNORECASE):
                # Get the first non-None group as the value
                raw_match = m.group(0)
                value_str = None
                for g in m.groups():
                    if g is not None:
                        value_str = g
                        break
                if value_str is None:
                    value_str = raw_match

                # Try to parse as float
                try:
                    normalized = float(value_str)
                except (ValueError, TypeError):
                    normalized = None

                # Get context (surrounding text, truncated)
                start = max(0, m.start() - 40)
                end = min(len(line), m.end() + 40)
                context = line[start:end].strip()

                instances.append(
                    NumberInstance(
                        value=raw_match.strip(),
                        normalized=normalized,
                        line=line_num,
                        section=current_section,
                        context=context,
                    )
                )

    return instances


def check_consistency(filepath: str | Path) -> list[ConsistencyFinding]:
    """Check number consistency across sections of a manuscript.

    Finds numbers that appear in the abstract or tables but differ
    from corresponding numbers in the body text.

    Args:
        filepath: Path to .tex or .md file.

    Returns:
        List of consistency findings.
    """
    filepath = Path(filepath)
    instances = extract_numbers(filepath)
    findings: list[ConsistencyFinding] = []

    if not instances:
        return findings

    # Group by normalized value (rounded to handle floating point)
    # We look for numbers that appear in abstract but not in body, or vice versa
    abstract_numbers: dict[str, list[NumberInstance]] = defaultdict(list)
    body_numbers: dict[str, list[NumberInstance]] = defaultdict(list)
    table_numbers: dict[str, list[NumberInstance]] = defaultdict(list)
    caption_numbers: dict[str, list[NumberInstance]] = defaultdict(list)

    section_maps = {
        "abstract": abstract_numbers,
        "body": body_numbers,
        "table": table_numbers,
        "caption": caption_numbers,
    }

    for inst in instances:
        target = section_maps.get(inst.section)
        if target is not None:
            target[inst.value].append(inst)

    # Check 1: Numbers in abstract should appear somewhere in body/tables
    for value, abstract_insts in abstract_numbers.items():
        found_in_body = value in body_numbers or value in table_numbers
        if not found_in_body:
            # Check if a close match exists (within 5% for numerical values)
            close_match = False
            for inst in abstract_insts:
                if inst.normalized is not None:
                    for bv, binsts in body_numbers.items():
                        for bi in binsts:
                            if bi.normalized is not None and inst.normalized != 0:
                                rel_diff = abs(bi.normalized - inst.normalized) / abs(inst.normalized)
                                if 0 < rel_diff <= 0.05:
                                    findings.append(
                                        ConsistencyFinding(
                                            severity="warning",
                                            issue="number_close_mismatch",
                                            instances=[inst, bi],
                                            details=(
                                                f"Abstract says '{inst.value}' (line {inst.line}) "
                                                f"but body has '{bi.value}' (line {bi.line}). "
                                                f"Relative difference: {rel_diff:.2%}."
                                            ),
                                        )
                                    )
                                    close_match = True

            if not close_match:
                findings.append(
                    ConsistencyFinding(
                        severity="info",
                        issue="abstract_number_not_in_body",
                        instances=abstract_insts,
                        details=(
                            f"Number '{value}' appears in abstract (line {abstract_insts[0].line}) "
                            f"but not found in body or tables."
                        ),
                    )
                )

    # Check 2: Numbers in tables should be consistent with captions
    for value, table_insts in table_numbers.items():
        for cv, caption_insts in caption_numbers.items():
            for ti in table_insts:
                for ci in caption_insts:
                    if (
                        ti.normalized is not None
                        and ci.normalized is not None
                        and ti.normalized != 0
                        and ci.normalized != 0
                    ):
                        rel_diff = abs(ti.normalized - ci.normalized) / abs(ti.normalized)
                        if 0 < rel_diff <= 0.1 and ti.value != ci.value:
                            findings.append(
                                ConsistencyFinding(
                                    severity="warning",
                                    issue="table_caption_mismatch",
                                    instances=[ti, ci],
                                    details=(
                                        f"Table value '{ti.value}' (line {ti.line}) "
                                        f"differs from caption value '{ci.value}' (line {ci.line}). "
                                        f"Relative difference: {rel_diff:.2%}."
                                    ),
                                )
                            )

    # Check 3: Duplicate numbers that contradict each other
    # Group all instances by approximate value and context
    all_numbers_by_context: dict[str, list[NumberInstance]] = defaultdict(list)
    for inst in instances:
        if inst.normalized is not None:
            # Create a context key from surrounding words
            words = re.findall(r"[a-zA-Z]{3,}", inst.context)
            ctx_key = " ".join(sorted(set(w.lower() for w in words[:5])))
            if ctx_key:
                all_numbers_by_context[ctx_key].append(inst)

    for ctx_key, ctx_instances in all_numbers_by_context.items():
        if len(ctx_instances) < 2:
            continue
        # Check if the values are consistent
        values = set()
        for inst in ctx_instances:
            if inst.normalized is not None:
                values.add(round(inst.normalized, 6))
        if len(values) > 1:
            findings.append(
                ConsistencyFinding(
                    severity="warning",
                    issue="context_number_conflict",
                    instances=ctx_instances,
                    details=(
                        f"Numbers in similar context ('{ctx_key[:50]}') have different values: "
                        f"{sorted(values)}. Lines: {[i.line for i in ctx_instances]}."
                    ),
                )
            )

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: severity_order.get(f.severity, 9))

    return findings

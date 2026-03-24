"""Code-paper number verification — explicit .tex + .py cross-reference.

Given a .tex file and a Python script that produces the paper's results:
1. Extract all numbers from LaTeX tables (tabular environments).
2. Run the Python script and capture stdout.
3. Cross-reference: for each table number, find the closest match.
4. Flag discrepancies >5% as warnings, >20% as critical.

This is the check that would have caught Table 1's 13.8 nM (paper) vs
12.8 nM (code) discrepancy (7.2% difference).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .reproducibility import ReproducibilityFinding, OUTPUT_NUMBER_RE


# ====================================================================
# LaTeX table number extraction
# ====================================================================

# Regex for extracting numbers from LaTeX tabular environments
_TABULAR_RE = re.compile(
    r"\\begin\{tabular[*x]?\}.*?\\end\{tabular[*x]?\}",
    re.DOTALL,
)

# Also match longtable, booktabs-style tabulars
_LONGTABLE_RE = re.compile(
    r"\\begin\{longtable\}.*?\\end\{longtable\}",
    re.DOTALL,
)

# Number in LaTeX table cell (handles negative, scientific notation,
# numbers with units like "13.8 nM" or "18.5 d")
_TABLE_NUMBER_RE = re.compile(
    r"(?<![a-zA-Z\d.])"  # not preceded by letter/digit/dot
    r"([-+]?\d+\.?\d*(?:\s*[\\times]*\s*10\s*\^\s*\{?\s*[+-]?\d+\s*\}?)?)"
    r"(?:\s*(?:\\?\s*(?:nM|uM|mM|mg|ng|pg|Hz|kHz|days?|hrs?|min|sec|%|\\%))?)"
    r"(?![.\d])",  # not followed by digit/dot
    re.IGNORECASE,
)

# LaTeX scientific notation: $1.5 \times 10^{-3}$
_LATEX_SCI_RE = re.compile(
    r"(\d+\.?\d*)\s*\\times\s*10\s*\^\s*\{?\s*([+-]?\d+)\s*\}?",
)


@dataclass
class TableNumber:
    """A number extracted from a LaTeX table."""

    value: float
    raw: str
    line: int  # Approximate line in the .tex file
    table_index: int  # Which table (0-based)
    context: str  # Surrounding cell text


@dataclass
class ScriptNumber:
    """A number extracted from script output."""

    value: float
    raw: str
    line_in_output: int
    context: str  # The full output line


# ====================================================================
# Extraction helpers
# ====================================================================

def _extract_table_numbers(tex_text: str) -> list[TableNumber]:
    """Extract all numbers from LaTeX tabular environments.

    Returns list of TableNumber with parsed float values.
    """
    results: list[TableNumber] = []

    # Find all tabular environments
    tables: list[tuple[int, str]] = []
    for pattern in [_TABULAR_RE, _LONGTABLE_RE]:
        for m in pattern.finditer(tex_text):
            line = tex_text[:m.start()].count("\n") + 1
            tables.append((line, m.group(0)))

    for table_idx, (base_line, table_text) in enumerate(tables):
        rows = re.split(
            r"\\\\|\\hline|\\midrule|\\toprule|\\bottomrule", table_text
        )

        row_offset = 0
        for row in rows:
            row_offset += row.count("\n")
            cells = row.split("&")

            for cell in cells:
                cell_stripped = cell.strip()
                if not cell_stripped:
                    continue

                # Check for LaTeX scientific notation first
                for sm in _LATEX_SCI_RE.finditer(cell_stripped):
                    mantissa = float(sm.group(1))
                    exponent = int(sm.group(2))
                    value = mantissa * (10 ** exponent)
                    results.append(TableNumber(
                        value=value,
                        raw=sm.group(0),
                        line=base_line + row_offset,
                        table_index=table_idx,
                        context=cell_stripped[:80],
                    ))

                # Then regular numbers
                for nm in _TABLE_NUMBER_RE.finditer(cell_stripped):
                    raw = nm.group(1).strip()
                    if _LATEX_SCI_RE.search(raw):
                        continue
                    try:
                        value = float(raw)
                    except ValueError:
                        continue
                    results.append(TableNumber(
                        value=value,
                        raw=raw,
                        line=base_line + row_offset,
                        table_index=table_idx,
                        context=cell_stripped[:80],
                    ))

    return results


def _extract_script_numbers(stdout: str) -> list[ScriptNumber]:
    """Extract all numbers from script stdout, preserving line context."""
    results: list[ScriptNumber] = []
    for line_num, line in enumerate(stdout.splitlines(), start=1):
        for m in OUTPUT_NUMBER_RE.finditer(line):
            raw = m.group(0)
            try:
                value = float(raw)
            except ValueError:
                continue
            results.append(ScriptNumber(
                value=value,
                raw=raw,
                line_in_output=line_num,
                context=line.strip()[:120],
            ))
    return results


def _run_script_with_env(
    script_path: Path, timeout: int, env: dict
) -> tuple[str, str, int]:
    """Run a Python script with a custom environment and capture output."""
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(script_path.parent),
            env=env,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Script timed out after {timeout}s", -1
    except Exception as e:
        return "", str(e), -1


# ====================================================================
# Public API
# ====================================================================

def verify_numbers(
    tex_path: str | Path,
    script_path: str | Path,
    timeout: int = 120,
    warning_threshold: float = 0.05,
    critical_threshold: float = 0.20,
    pythonpath: str | None = None,
) -> list[ReproducibilityFinding]:
    """Verify that numbers in LaTeX tables match script output.

    Given a .tex file and a Python script:
    1. Extract all numbers from LaTeX tabular environments.
    2. Run the Python script and capture stdout.
    3. Cross-reference: for each table number, find closest match in output.
    4. Flag discrepancies: >warning_threshold as warning,
       >critical_threshold as critical.

    Args:
        tex_path: Path to .tex manuscript file.
        script_path: Path to Python script that produces paper results.
        timeout: Max seconds to run the script.
        warning_threshold: Relative difference for warnings (default 5%).
        critical_threshold: Relative difference for critical (default 20%).
        pythonpath: Optional PYTHONPATH to set when running the script.

    Returns:
        List of ReproducibilityFinding objects sorted by severity.
    """
    tex_path = Path(tex_path)
    script_path = Path(script_path)

    if not tex_path.exists():
        raise FileNotFoundError(f"TeX file not found: {tex_path}")
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    findings: list[ReproducibilityFinding] = []

    # 1. Extract numbers from LaTeX tables
    tex_text = tex_path.read_text(encoding="utf-8", errors="replace")
    table_numbers = _extract_table_numbers(tex_text)

    if not table_numbers:
        findings.append(ReproducibilityFinding(
            file=str(tex_path), line=0, severity="info",
            issue="no_tables_found",
            details="No tabular environments with numbers found.",
        ))
        return findings

    findings.append(ReproducibilityFinding(
        file=str(tex_path), line=0, severity="info",
        issue="tables_parsed",
        details=(
            f"Extracted {len(table_numbers)} numbers from "
            f"{len(set(tn.table_index for tn in table_numbers))} table(s)."
        ),
    ))

    # 2. Run the script
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if pythonpath:
        env["PYTHONPATH"] = pythonpath

    stdout, stderr, returncode = _run_script_with_env(
        script_path, timeout, env
    )

    if returncode != 0:
        findings.append(ReproducibilityFinding(
            file=str(script_path), line=0, severity="critical",
            issue="script_failed",
            details=f"Script failed (rc {returncode}). Stderr: {stderr[:300]}",
            script=str(script_path),
        ))
        return findings

    if not stdout.strip():
        findings.append(ReproducibilityFinding(
            file=str(script_path), line=0, severity="warning",
            issue="no_output",
            details="Script produced no stdout. Cannot verify numbers.",
            script=str(script_path),
        ))
        return findings

    # 3. Extract numbers from script output
    script_numbers = _extract_script_numbers(stdout)

    if not script_numbers:
        findings.append(ReproducibilityFinding(
            file=str(script_path), line=0, severity="warning",
            issue="no_numbers_in_output",
            details="Script output contains no extractable numbers.",
            script=str(script_path),
        ))
        return findings

    findings.append(ReproducibilityFinding(
        file=str(script_path), line=0, severity="info",
        issue="output_parsed",
        details=f"Extracted {len(script_numbers)} numbers from script output.",
        script=str(script_path),
    ))

    # 4. Cross-reference table numbers against script output
    script_vals = [(sn.value, sn) for sn in script_numbers if sn.value != 0]
    matched_count = 0
    discrepancy_count = 0

    for tn in table_numbers:
        if tn.value == 0:
            continue

        best_sn: ScriptNumber | None = None
        best_diff = float("inf")

        for sv, sn in script_vals:
            if sv == 0:
                continue
            rel_diff = abs(tn.value - sv) / max(abs(tn.value), abs(sv))
            if rel_diff < best_diff:
                best_diff = rel_diff
                best_sn = sn

        if best_sn is None or best_diff > 0.50:
            continue

        matched_count += 1

        if best_diff == 0:
            continue

        if best_diff > critical_threshold:
            discrepancy_count += 1
            findings.append(ReproducibilityFinding(
                file=str(tex_path), line=tn.line,
                severity="critical", issue="table_code_mismatch",
                details=(
                    f"Table {tn.table_index + 1} reports {tn.raw} "
                    f"(context: '{tn.context}') but script outputs "
                    f"{best_sn.raw} (context: '{best_sn.context}'). "
                    f"Discrepancy: {best_diff:.1%} "
                    f"(critical threshold: {critical_threshold:.0%})."
                ),
                script=str(script_path),
                expected=str(tn.value),
                actual=str(best_sn.value),
            ))
        elif best_diff > warning_threshold:
            discrepancy_count += 1
            findings.append(ReproducibilityFinding(
                file=str(tex_path), line=tn.line,
                severity="warning", issue="table_code_mismatch",
                details=(
                    f"Table {tn.table_index + 1} reports {tn.raw} "
                    f"(context: '{tn.context}') but script outputs "
                    f"{best_sn.raw} (context: '{best_sn.context}'). "
                    f"Discrepancy: {best_diff:.1%} "
                    f"(warning threshold: {warning_threshold:.0%})."
                ),
                script=str(script_path),
                expected=str(tn.value),
                actual=str(best_sn.value),
            ))

    # Summary
    findings.append(ReproducibilityFinding(
        file=str(tex_path), line=0, severity="info",
        issue="verification_summary",
        details=(
            f"Matched {matched_count} table numbers against script output. "
            f"Found {discrepancy_count} discrepancies "
            f"(warning>{warning_threshold:.0%}, "
            f"critical>{critical_threshold:.0%})."
        ),
        script=str(script_path),
    ))

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 9), f.line))

    return findings

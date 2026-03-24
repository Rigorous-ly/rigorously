"""Reproducibility checking — run scripts and compare output to paper claims.

Finds Python scripts referenced in the paper, runs them, captures output
numbers, and compares to paper claims. Flags discrepancies > 1%.

The verify_numbers() function (in verify_numbers.py) provides a more
targeted check: given an explicit .tex + .py pair, it extracts numbers
from LaTeX tables and cross-references them against script output.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class ReproducibilityFinding:
    """A reproducibility check result."""

    file: str
    line: int
    severity: Literal["critical", "warning", "info"]
    issue: str
    details: str
    script: str = ""
    expected: str = ""
    actual: str = ""


# Pattern to find Python script references in LaTeX/Markdown
SCRIPT_REF_PATTERNS = [
    # \texttt{script.py}, \verb|script.py|, `script.py`
    re.compile(r"\\texttt\{([^}]*\.py)\}", re.IGNORECASE),
    re.compile(r"\\verb\|([^|]*\.py)\|", re.IGNORECASE),
    re.compile(r"`([^`]*\.py)`"),
    # Listing references
    re.compile(r"\\lstinputlisting(?:\[.*?\])?\{([^}]*\.py)\}", re.IGNORECASE),
    # Plain text references
    re.compile(r"(?:run|execute|script|code)\s+(?:in\s+)?(?:the\s+)?[`\"']?(\w[\w/]*\.py)[`\"']?", re.IGNORECASE),
]

# Number extraction from output
OUTPUT_NUMBER_RE = re.compile(
    r"[-+]?\d+\.?\d*(?:e[+-]?\d+)?",
    re.IGNORECASE,
)


def _find_referenced_scripts(
    tex_filepath: Path,
    code_directory: Path,
) -> list[tuple[int, str, Path]]:
    """Find Python scripts referenced in the manuscript.

    Returns:
        List of (line_number, reference_text, resolved_path).
    """
    text = tex_filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    results: list[tuple[int, str, Path]] = []

    for line_num, line in enumerate(lines, start=1):
        for pattern in SCRIPT_REF_PATTERNS:
            for m in pattern.finditer(line):
                script_name = m.group(1).strip()
                # Try to resolve the script path
                candidates = [
                    code_directory / script_name,
                    tex_filepath.parent / script_name,
                ]
                # Also search recursively
                for found in code_directory.rglob(Path(script_name).name):
                    candidates.append(found)

                for candidate in candidates:
                    if candidate.exists() and candidate.is_file():
                        results.append((line_num, script_name, candidate.resolve()))
                        break

    return results


def _extract_numbers_from_text(text: str) -> list[tuple[str, float]]:
    """Extract all numbers from text output.

    Returns:
        List of (raw_string, float_value).
    """
    results: list[tuple[str, float]] = []
    for m in OUTPUT_NUMBER_RE.finditer(text):
        raw = m.group(0)
        try:
            val = float(raw)
            results.append((raw, val))
        except ValueError:
            continue
    return results


def _run_script(script_path: Path, timeout: int = 60) -> tuple[str, str, int]:
    """Run a Python script and capture output.

    Returns:
        (stdout, stderr, return_code)
    """
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(script_path.parent),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Script timed out after {timeout}s", -1
    except Exception as e:
        return "", str(e), -1


def check_reproducibility(
    tex_filepath: str | Path,
    code_directory: str | Path | None = None,
    timeout: int = 60,
    threshold: float = 0.01,
) -> list[ReproducibilityFinding]:
    """Check reproducibility by running referenced scripts.

    Args:
        tex_filepath: Path to .tex or .md manuscript.
        code_directory: Directory containing Python scripts.
        timeout: Maximum seconds to run each script.
        threshold: Maximum allowed relative discrepancy (default 1%).

    Returns:
        List of ReproducibilityFinding objects.
    """
    tex_filepath = Path(tex_filepath)
    if not tex_filepath.exists():
        raise FileNotFoundError(f"File not found: {tex_filepath}")

    if code_directory is None:
        code_directory = tex_filepath.parent
    code_directory = Path(code_directory)

    findings: list[ReproducibilityFinding] = []

    # Find referenced scripts
    scripts = _find_referenced_scripts(tex_filepath, code_directory)

    if not scripts:
        findings.append(
            ReproducibilityFinding(
                file=str(tex_filepath),
                line=0,
                severity="info",
                issue="no_scripts_found",
                details="No Python scripts referenced in the manuscript.",
            )
        )
        return findings

    # Extract numbers from the manuscript for comparison
    tex_text = tex_filepath.read_text(encoding="utf-8", errors="replace")
    paper_numbers = _extract_numbers_from_text(tex_text)
    paper_values = {val for _, val in paper_numbers if val != 0}

    # Run each script and compare
    for line_num, script_name, script_path in scripts:
        stdout, stderr, returncode = _run_script(script_path, timeout)

        if returncode != 0:
            findings.append(
                ReproducibilityFinding(
                    file=str(tex_filepath),
                    line=line_num,
                    severity="critical",
                    issue="script_failed",
                    details=(
                        f"Script '{script_name}' failed with return code {returncode}. "
                        f"Stderr: {stderr[:200]}"
                    ),
                    script=str(script_path),
                )
            )
            continue

        if not stdout.strip():
            findings.append(
                ReproducibilityFinding(
                    file=str(tex_filepath),
                    line=line_num,
                    severity="warning",
                    issue="no_output",
                    details=f"Script '{script_name}' produced no stdout output.",
                    script=str(script_path),
                )
            )
            continue

        # Extract numbers from output
        output_numbers = _extract_numbers_from_text(stdout)

        if not output_numbers:
            findings.append(
                ReproducibilityFinding(
                    file=str(tex_filepath),
                    line=line_num,
                    severity="info",
                    issue="no_numbers_in_output",
                    details=f"Script '{script_name}' output contains no numbers to compare.",
                    script=str(script_path),
                )
            )
            continue

        # Compare output numbers with paper numbers
        for raw_out, out_val in output_numbers:
            if out_val == 0:
                continue
            # Find closest paper number
            best_match = None
            best_diff = float("inf")
            for paper_val in paper_values:
                rel_diff = abs(out_val - paper_val) / max(abs(out_val), abs(paper_val))
                if rel_diff < best_diff:
                    best_diff = rel_diff
                    best_match = paper_val

            if best_match is not None and 0 < best_diff <= 0.1:
                # There's a match within 10% -- check if it exceeds threshold
                if best_diff > threshold:
                    findings.append(
                        ReproducibilityFinding(
                            file=str(tex_filepath),
                            line=line_num,
                            severity="critical" if best_diff > 0.05 else "warning",
                            issue="number_discrepancy",
                            details=(
                                f"Script '{script_name}' outputs {raw_out} ({out_val}) "
                                f"but paper reports {best_match}. "
                                f"Discrepancy: {best_diff:.2%} (threshold: {threshold:.2%})."
                            ),
                            script=str(script_path),
                            expected=str(best_match),
                            actual=str(out_val),
                        )
                    )

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 9), f.line))

    return findings

"""Statistical claims auditing.

For any p-value mentioned in .tex files, checks:
1. Sample size reported nearby?
2. Test name specified?
3. Non-significance not misinterpreted as equivalence?
4. Power analysis mentioned?
5. Multiple comparisons correction mentioned (if multiple tests)?
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class StatisticalFinding:
    """A statistical auditing issue."""

    file: str
    line: int
    severity: Literal["critical", "warning", "info"]
    issue: str
    details: str
    context: str = ""


# Regex for p-values in various formats
P_VALUE_PATTERNS = [
    # p < 0.05, p = 0.001, P < .05, p-value = 0.05
    re.compile(
        r"(?:p|P)[\s-]*(?:value)?\s*([<=>\u2264\u2265])\s*(\d*\.?\d+(?:e[+-]?\d+)?)",
    ),
    # p < .05 (no leading zero)
    re.compile(
        r"(?:p|P)[\s-]*(?:value)?\s*([<=>\u2264\u2265])\s*(\.?\d+(?:e[+-]?\d+)?)",
    ),
]

# Statistical test names
TEST_NAMES = [
    r"t[\s-]?test",
    r"Mann[\s-]Whitney",
    r"Wilcoxon",
    r"ANOVA",
    r"chi[\s-]?square",
    r"\u03c7\s*2",  # chi^2 unicode
    r"chi2",
    r"Kruskal[\s-]Wallis",
    r"Fisher'?s?\s+exact",
    r"Kolmogorov[\s-]Smirnov",
    r"K[\s-]S\s+test",
    r"Shapiro[\s-]Wilk",
    r"Spearman",
    r"Pearson",
    r"linear\s+regression",
    r"logistic\s+regression",
    r"Cox\s+regression",
    r"log[\s-]?rank",
    r"mixed[\s-]?model",
    r"bootstrap",
    r"permutation\s+test",
    r"Friedman",
    r"McNemar",
    r"Tukey",
    r"Bonferroni",
    r"Holm",
    r"Benjamini[\s-]Hochberg",
    r"FDR",
    r"Welch",
    r"Dunnett",
    r"paired",
    r"unpaired",
    r"two[\s-]?sided",
    r"one[\s-]?sided",
    r"two[\s-]?tailed",
    r"one[\s-]?tailed",
]

# Sample size patterns
SAMPLE_SIZE_PATTERNS = [
    re.compile(r"[nN]\s*=\s*\d+"),
    re.compile(r"sample\s+size\s+(?:of\s+)?\d+", re.IGNORECASE),
    re.compile(r"\d+\s+(?:subjects?|participants?|patients?|samples?|observations?|trials?|mice|rats|animals?)", re.IGNORECASE),
]

# Power analysis patterns
POWER_PATTERNS = [
    re.compile(r"power\s+analysis", re.IGNORECASE),
    re.compile(r"statistical\s+power", re.IGNORECASE),
    re.compile(r"sample\s+size\s+calculation", re.IGNORECASE),
    re.compile(r"a\s+priori\s+power", re.IGNORECASE),
    re.compile(r"effect\s+size", re.IGNORECASE),
    re.compile(r"Cohen'?s?\s+[dfw]", re.IGNORECASE),
    re.compile(r"G\*?Power", re.IGNORECASE),
]

# Equivalence/non-significance misinterpretation patterns
EQUIVALENCE_MISUSE = [
    re.compile(r"(?:no|not?)\s+(?:statistically\s+)?significant\s+difference.*(?:similar|same|equal|equivalent|identical|comparable)", re.IGNORECASE),
    re.compile(r"(?:similar|same|equal|equivalent|identical|comparable).*(?:no|not?)\s+(?:statistically\s+)?significant", re.IGNORECASE),
    re.compile(r"p\s*[>=>\u2265]\s*0\.0?5.*(?:no\s+difference|same|equal|equivalent)", re.IGNORECASE),
    re.compile(r"(?:failed\s+to\s+reject|did\s+not\s+reject).*(?:therefore|thus|hence|so)\s+(?:the\s+)?(?:groups?\s+)?(?:are|were)\s+(?:the\s+)?same", re.IGNORECASE),
]

# Multiple comparisons
MULTIPLE_COMPARISON_CORRECTIONS = [
    re.compile(r"Bonferroni", re.IGNORECASE),
    re.compile(r"Holm", re.IGNORECASE),
    re.compile(r"Benjamini[\s-]Hochberg", re.IGNORECASE),
    re.compile(r"FDR\s+correct", re.IGNORECASE),
    re.compile(r"false\s+discovery\s+rate", re.IGNORECASE),
    re.compile(r"multiple\s+comparison", re.IGNORECASE),
    re.compile(r"post[\s-]?hoc\s+correct", re.IGNORECASE),
    re.compile(r"Tukey'?s?\s+HSD", re.IGNORECASE),
    re.compile(r"Dunnett", re.IGNORECASE),
    re.compile(r"Sidak", re.IGNORECASE),
    re.compile(r"family[\s-]?wise\s+error", re.IGNORECASE),
]


def _get_context_window(lines: list[str], line_idx: int, window: int = 5) -> str:
    """Get surrounding lines as context."""
    start = max(0, line_idx - window)
    end = min(len(lines), line_idx + window + 1)
    return " ".join(lines[start:end])


def check_statistics(filepath: str | Path) -> list[StatisticalFinding]:
    """Audit statistical claims in a manuscript.

    Args:
        filepath: Path to .tex or .md file.

    Returns:
        List of StatisticalFinding objects.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    findings: list[StatisticalFinding] = []

    # Find all p-values
    p_value_locations: list[tuple[int, str, str, float]] = []  # (line, operator, raw, value)
    for line_num, line in enumerate(lines, start=1):
        for pattern in P_VALUE_PATTERNS:
            for m in pattern.finditer(line):
                operator = m.group(1)
                val_str = m.group(2)
                try:
                    value = float(val_str)
                    p_value_locations.append((line_num, operator, m.group(0), value))
                except ValueError:
                    continue

    if not p_value_locations:
        findings.append(
            StatisticalFinding(
                file=str(filepath),
                line=0,
                severity="info",
                issue="no_p_values",
                details="No p-values found in the manuscript.",
            )
        )
        return findings

    # For each p-value, check surrounding context
    for line_num, operator, raw_match, p_val in p_value_locations:
        line_idx = line_num - 1
        context = _get_context_window(lines, line_idx)

        # Check 1: Is sample size reported nearby?
        has_sample_size = any(
            pat.search(context) for pat in SAMPLE_SIZE_PATTERNS
        )
        if not has_sample_size:
            findings.append(
                StatisticalFinding(
                    file=str(filepath),
                    line=line_num,
                    severity="warning",
                    issue="no_sample_size",
                    details=(
                        f"P-value ({raw_match}) reported without sample size "
                        f"in surrounding context. Report n for each group."
                    ),
                    context=lines[line_idx].strip(),
                )
            )

        # Check 2: Is the statistical test named?
        has_test_name = any(
            re.search(pattern, context, re.IGNORECASE) for pattern in TEST_NAMES
        )
        if not has_test_name:
            findings.append(
                StatisticalFinding(
                    file=str(filepath),
                    line=line_num,
                    severity="warning",
                    issue="no_test_named",
                    details=(
                        f"P-value ({raw_match}) reported without naming the "
                        f"statistical test used."
                    ),
                    context=lines[line_idx].strip(),
                )
            )

        # Check 3: Suspiciously round p-values
        if p_val in (0.05, 0.01, 0.001) and operator in ("=", ):
            findings.append(
                StatisticalFinding(
                    file=str(filepath),
                    line=line_num,
                    severity="info",
                    issue="round_p_value",
                    details=(
                        f"P-value '{raw_match}' is suspiciously round. "
                        f"Report exact p-values (e.g., p = 0.032) rather than thresholds."
                    ),
                    context=lines[line_idx].strip(),
                )
            )

    # Check 4: Non-significance misinterpreted as equivalence
    for line_num, line in enumerate(lines, start=1):
        for pattern in EQUIVALENCE_MISUSE:
            if pattern.search(line):
                findings.append(
                    StatisticalFinding(
                        file=str(filepath),
                        line=line_num,
                        severity="critical",
                        issue="nonsig_as_equivalence",
                        details=(
                            "Absence of significant difference is not evidence of equivalence. "
                            "Use equivalence testing (TOST) or report effect sizes with "
                            "confidence intervals."
                        ),
                        context=line.strip(),
                    )
                )

    # Check 5: Multiple p-values but no correction mentioned?
    if len(p_value_locations) > 3:
        full_text = text
        has_correction = any(
            pat.search(full_text) for pat in MULTIPLE_COMPARISON_CORRECTIONS
        )
        if not has_correction:
            findings.append(
                StatisticalFinding(
                    file=str(filepath),
                    line=p_value_locations[0][0],
                    severity="warning",
                    issue="no_multiple_comparison_correction",
                    details=(
                        f"Found {len(p_value_locations)} p-values but no mention of "
                        f"multiple comparisons correction (Bonferroni, FDR, etc.)."
                    ),
                )
            )

    # Check 6: Power analysis mentioned anywhere?
    has_power = any(pat.search(text) for pat in POWER_PATTERNS)
    if not has_power and len(p_value_locations) > 0:
        findings.append(
            StatisticalFinding(
                file=str(filepath),
                line=0,
                severity="info",
                issue="no_power_analysis",
                details=(
                    "No mention of statistical power or sample size calculation. "
                    "Consider adding a power analysis or justification for sample sizes."
                ),
            )
        )

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 9), f.line))

    return findings

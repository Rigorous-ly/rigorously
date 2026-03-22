"""Adversarial review simulation.

Runs all other checks, compiles findings, and generates an adversarial
review summary highlighting the most damaging objections a reviewer
would raise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReviewReport:
    """A complete adversarial review."""

    overall_rating: str  # "reject", "major_revision", "minor_revision", "accept"
    summary: str
    major_issues: list[str]
    minor_issues: list[str]
    suggestions: list[str]
    finding_counts: dict[str, int] = field(default_factory=dict)
    raw_findings: dict[str, list[Any]] = field(default_factory=dict)


def _count_by_severity(findings: list) -> dict[str, int]:
    """Count findings by severity level."""
    counts: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        sev = getattr(f, "severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def _format_issue(finding: Any) -> str:
    """Format a finding as a review issue string."""
    details = getattr(finding, "details", "")
    issue = getattr(finding, "issue", "")
    line = getattr(finding, "line", 0)
    file_ = getattr(finding, "file", "")

    parts = []
    if file_ and line:
        parts.append(f"[{Path(file_).name}:{line}]")
    elif file_:
        parts.append(f"[{Path(file_).name}]")

    if issue:
        parts.append(f"({issue})")

    parts.append(details or str(finding))
    return " ".join(parts)


def generate_review(
    tex_filepath: str | Path,
    bib_filepath: str | Path | None = None,
    code_directory: str | Path | None = None,
    skip_citations: bool = False,
    skip_reproducibility: bool = True,
) -> ReviewReport:
    """Run all checks and generate an adversarial review.

    Args:
        tex_filepath: Path to .tex or .md manuscript.
        bib_filepath: Path to .bib file (optional).
        code_directory: Directory with Python code (optional).
        skip_citations: Skip citation verification (requires network).
        skip_reproducibility: Skip reproducibility checks (runs scripts).

    Returns:
        ReviewReport with compiled adversarial review.
    """
    from .consistency import check_consistency
    from .evidence import check_evidence
    from .overclaim import check_overclaims
    from .parameters import check_parameters
    from .statistics import check_statistics

    tex_filepath = Path(tex_filepath)
    all_findings: dict[str, list] = {}
    total_critical = 0
    total_warning = 0
    total_info = 0

    # 1. Overclaim check
    try:
        overclaim_findings = check_overclaims(tex_filepath)
        all_findings["overclaim"] = overclaim_findings
        counts = _count_by_severity(overclaim_findings)
        total_critical += counts["critical"]
        total_warning += counts["warning"]
        total_info += counts["info"]
    except Exception as e:
        all_findings["overclaim"] = [f"Error: {e}"]

    # 2. Consistency check
    try:
        consistency_findings = check_consistency(tex_filepath)
        all_findings["consistency"] = consistency_findings
        counts = _count_by_severity(consistency_findings)
        total_critical += counts["critical"]
        total_warning += counts["warning"]
        total_info += counts["info"]
    except Exception as e:
        all_findings["consistency"] = [f"Error: {e}"]

    # 3. Statistics check
    try:
        stats_findings = check_statistics(tex_filepath)
        all_findings["statistics"] = stats_findings
        counts = _count_by_severity(stats_findings)
        total_critical += counts["critical"]
        total_warning += counts["warning"]
        total_info += counts["info"]
    except Exception as e:
        all_findings["statistics"] = [f"Error: {e}"]

    # 4. Citation check (optional, requires network)
    if not skip_citations and bib_filepath is not None:
        try:
            from .citations import verify_bib_file

            citation_findings = verify_bib_file(bib_filepath)
            all_findings["citations"] = citation_findings
            counts = _count_by_severity(citation_findings)
            total_critical += counts["critical"]
            total_warning += counts["warning"]
            total_info += counts["info"]
        except Exception as e:
            all_findings["citations"] = [f"Error: {e}"]

    # 5. Evidence check
    if code_directory is not None:
        try:
            evidence_findings = check_evidence(tex_filepath, code_directory)
            all_findings["evidence"] = evidence_findings
            counts = _count_by_severity(evidence_findings)
            total_critical += counts["critical"]
            total_warning += counts["warning"]
            total_info += counts["info"]
        except Exception as e:
            all_findings["evidence"] = [f"Error: {e}"]

    # 6. Parameter check (scan code directory for Python ODE files)
    if code_directory is not None:
        code_dir = Path(code_directory)
        param_findings_all: list = []
        for py_file in code_dir.rglob("*.py"):
            try:
                pf = check_parameters(py_file)
                param_findings_all.extend(pf)
            except Exception:
                continue
        all_findings["parameters"] = param_findings_all
        counts = _count_by_severity(param_findings_all)
        total_critical += counts["critical"]
        total_warning += counts["warning"]
        total_info += counts["info"]

    # 7. Reproducibility check (optional, runs scripts)
    if not skip_reproducibility and code_directory is not None:
        try:
            from .reproducibility import check_reproducibility

            repro_findings = check_reproducibility(tex_filepath, code_directory)
            all_findings["reproducibility"] = repro_findings
            counts = _count_by_severity(repro_findings)
            total_critical += counts["critical"]
            total_warning += counts["warning"]
            total_info += counts["info"]
        except Exception as e:
            all_findings["reproducibility"] = [f"Error: {e}"]

    # Compile review
    major_issues: list[str] = []
    minor_issues: list[str] = []
    suggestions: list[str] = []

    for check_name, findings in all_findings.items():
        for f in findings:
            if isinstance(f, str):
                suggestions.append(f"[{check_name}] {f}")
                continue
            sev = getattr(f, "severity", "info")
            formatted = _format_issue(f)
            if sev == "critical":
                major_issues.append(formatted)
            elif sev == "warning":
                minor_issues.append(formatted)
            else:
                suggestions.append(formatted)

    # Determine overall rating
    if total_critical >= 5:
        overall_rating = "reject"
    elif total_critical >= 2:
        overall_rating = "major_revision"
    elif total_warning >= 5 or total_critical >= 1:
        overall_rating = "major_revision"
    elif total_warning >= 2:
        overall_rating = "minor_revision"
    else:
        overall_rating = "accept"

    # Generate summary
    summary_parts = [
        f"Automated integrity review found {total_critical} critical issues, "
        f"{total_warning} warnings, and {total_info} informational notes.",
    ]

    if total_critical > 0:
        summary_parts.append(
            "Critical issues include potential overclaims, data inconsistencies, "
            "or citation problems that must be addressed before publication."
        )

    if overall_rating == "reject":
        summary_parts.append(
            "Recommendation: REJECT. The number of critical issues suggests "
            "fundamental problems with the manuscript's claims."
        )
    elif overall_rating == "major_revision":
        summary_parts.append(
            "Recommendation: MAJOR REVISION. Several issues require substantive "
            "changes to the manuscript."
        )
    elif overall_rating == "minor_revision":
        summary_parts.append(
            "Recommendation: MINOR REVISION. Issues are addressable with "
            "targeted corrections."
        )
    else:
        summary_parts.append(
            "Recommendation: ACCEPT with minor suggestions. No critical "
            "integrity issues detected."
        )

    return ReviewReport(
        overall_rating=overall_rating,
        summary=" ".join(summary_parts),
        major_issues=major_issues,
        minor_issues=minor_issues,
        suggestions=suggestions,
        finding_counts={
            "critical": total_critical,
            "warning": total_warning,
            "info": total_info,
        },
        raw_findings=all_findings,
    )

"""Report generation for Rigorously checks.

Generates unified reports in both terminal-friendly (Rich) and Markdown formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


SEVERITY_COLORS = {
    "critical": "red",
    "warning": "yellow",
    "info": "blue",
}

SEVERITY_ICONS = {
    "critical": "[X]",
    "warning": "[!]",
    "info": "[i]",
}


def _severity_badge(severity: str) -> str:
    """Return a severity badge for markdown."""
    badges = {
        "critical": "**CRITICAL**",
        "warning": "WARNING",
        "info": "info",
    }
    return badges.get(severity, severity)


def print_findings(
    findings: list[Any],
    check_name: str,
    console: Console | None = None,
) -> None:
    """Print findings to the terminal using Rich.

    Args:
        findings: List of finding objects.
        check_name: Name of the check (e.g., "Overclaim Detection").
        console: Rich Console instance (creates one if not provided).
    """
    if console is None:
        console = Console()

    if not findings:
        console.print(f"\n[green]{check_name}: No issues found.[/green]")
        return

    # Count by severity
    counts = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        sev = getattr(f, "severity", "info")
        counts[sev] = counts.get(sev, 0) + 1

    # Header
    total = sum(counts.values())
    header = f"{check_name}: {total} findings"
    if counts["critical"] > 0:
        header += f" ({counts['critical']} critical)"

    table = Table(title=header, show_lines=True)
    table.add_column("Sev", style="bold", width=8)
    table.add_column("Line", width=6)
    table.add_column("Issue", width=25)
    table.add_column("Details", ratio=1)

    for f in findings:
        sev = getattr(f, "severity", "info")
        line = str(getattr(f, "line", ""))
        issue = getattr(f, "issue", getattr(f, "pattern_name", ""))
        details = getattr(f, "details", getattr(f, "suggestion", str(f)))
        file_ = getattr(f, "file", "")

        sev_text = Text(sev.upper(), style=SEVERITY_COLORS.get(sev, "white"))

        if file_ and line:
            loc = f"{Path(file_).name}:{line}"
        else:
            loc = line

        table.add_row(sev_text, loc, issue, details[:200])

    console.print(table)


def print_review(review: Any, console: Console | None = None) -> None:
    """Print an adversarial review to the terminal.

    Args:
        review: ReviewReport object.
        console: Rich Console instance.
    """
    if console is None:
        console = Console()

    # Rating color
    rating_colors = {
        "reject": "red",
        "major_revision": "red",
        "minor_revision": "yellow",
        "accept": "green",
    }
    color = rating_colors.get(review.overall_rating, "white")

    console.print()
    console.print(
        Panel(
            f"[bold {color}]{review.overall_rating.upper().replace('_', ' ')}[/bold {color}]",
            title="Adversarial Review",
            subtitle=f"Critical: {review.finding_counts.get('critical', 0)} | "
            f"Warning: {review.finding_counts.get('warning', 0)} | "
            f"Info: {review.finding_counts.get('info', 0)}",
        )
    )

    console.print(f"\n[bold]Summary:[/bold] {review.summary}\n")

    if review.major_issues:
        console.print("[bold red]Major Issues:[/bold red]")
        for i, issue in enumerate(review.major_issues, 1):
            console.print(f"  {i}. {issue[:200]}")
        console.print()

    if review.minor_issues:
        console.print("[bold yellow]Minor Issues:[/bold yellow]")
        for i, issue in enumerate(review.minor_issues, 1):
            console.print(f"  {i}. {issue[:200]}")
        console.print()

    if review.suggestions:
        console.print("[bold blue]Suggestions:[/bold blue]")
        for i, sug in enumerate(review.suggestions[:10], 1):
            console.print(f"  {i}. {sug[:200]}")
        if len(review.suggestions) > 10:
            console.print(f"  ... and {len(review.suggestions) - 10} more.")
        console.print()


def generate_markdown_report(
    findings_by_check: dict[str, list[Any]],
    output_path: str | Path | None = None,
) -> str:
    """Generate a Markdown report from findings.

    Args:
        findings_by_check: Dict mapping check name -> list of findings.
        output_path: If provided, write report to this file.

    Returns:
        The Markdown report string.
    """
    lines: list[str] = []
    lines.append("# Rigorously Integrity Report")
    lines.append("")

    total_critical = 0
    total_warning = 0
    total_info = 0

    for check_name, findings in findings_by_check.items():
        counts = {"critical": 0, "warning": 0, "info": 0}
        for f in findings:
            sev = getattr(f, "severity", "info")
            counts[sev] = counts.get(sev, 0) + 1
        total_critical += counts["critical"]
        total_warning += counts["warning"]
        total_info += counts["info"]

    lines.append(f"**Total findings:** {total_critical} critical, {total_warning} warnings, {total_info} info")
    lines.append("")

    for check_name, findings in findings_by_check.items():
        lines.append(f"## {check_name}")
        lines.append("")

        if not findings:
            lines.append("No issues found.")
            lines.append("")
            continue

        lines.append("| Severity | Line | Issue | Details |")
        lines.append("|----------|------|-------|---------|")

        for f in findings:
            sev = getattr(f, "severity", "info")
            line = str(getattr(f, "line", ""))
            issue = getattr(f, "issue", getattr(f, "pattern_name", ""))
            details = getattr(f, "details", getattr(f, "suggestion", str(f)))
            # Escape pipe characters in details
            details = details.replace("|", "\\|")[:150]
            lines.append(f"| {_severity_badge(sev)} | {line} | {issue} | {details} |")

        lines.append("")

    report = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")

    return report

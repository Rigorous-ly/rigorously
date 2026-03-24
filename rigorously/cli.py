"""Rigorously CLI — research integrity from the command line.

Usage:
    rigorously check paper.tex       — run all checks
    rigorously citations paper.bib   — verify bibliography
    rigorously overclaims paper.tex  — scan for overclaims
    rigorously install-hook          — install pre-commit hook
    rigorously report paper.tex      — generate full report
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="rigorously",
    help="Automated research quality assurance.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command()
def check(
    filepath: str = typer.Argument(..., help="Path to .tex or .md manuscript"),
    bib: Optional[str] = typer.Option(None, "--bib", "-b", help="Path to .bib file"),
    code: Optional[str] = typer.Option(None, "--code", "-c", help="Code directory for evidence/parameter checks"),
    skip_citations: bool = typer.Option(False, "--skip-citations", help="Skip citation verification (requires network)"),
    skip_repro: bool = typer.Option(True, "--skip-repro/--run-repro", help="Skip reproducibility checks (runs scripts)"),
    db_path: Optional[str] = typer.Option(None, "--db", help="SQLite database path"),
) -> None:
    """Run all integrity checks on a manuscript."""
    from .core.review import generate_review
    from .db import get_connection, store_run
    from .report import print_review

    tex_path = Path(filepath)
    if not tex_path.exists():
        console.print(f"[red]Error: File not found: {filepath}[/red]")
        raise typer.Exit(1)

    bib_path = Path(bib) if bib else None
    code_dir = Path(code) if code else None

    console.print(f"\n[bold]Rigorously checking:[/bold] {tex_path.name}")
    console.print("Running all integrity checks...\n")

    review = generate_review(
        tex_filepath=tex_path,
        bib_filepath=bib_path,
        code_directory=code_dir,
        skip_citations=skip_citations,
        skip_reproducibility=skip_repro,
    )

    print_review(review, console)

    # Store results
    if db_path or True:  # Always store by default
        conn = get_connection(db_path or ".rigorous.db")
        for check_name, findings in review.raw_findings.items():
            if findings and not isinstance(findings[0], str):
                store_run(conn, str(tex_path), check_name, findings)
        conn.close()


@app.command()
def citations(
    filepath: str = typer.Argument(..., help="Path to .bib file"),
    rate_limit: float = typer.Option(1.0, "--rate-limit", "-r", help="Seconds between CrossRef API requests"),
) -> None:
    """Verify bibliography entries against CrossRef."""
    from .core.citations import verify_bib_file
    from .report import print_findings

    bib_path = Path(filepath)
    if not bib_path.exists():
        console.print(f"[red]Error: File not found: {filepath}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Verifying citations:[/bold] {bib_path.name}")
    console.print("Checking against CrossRef API...\n")

    findings = verify_bib_file(bib_path, rate_limit=rate_limit)
    print_findings(findings, "Citation Verification", console)


@app.command()
def overclaims(
    filepath: str = typer.Argument(..., help="Path to .tex or .md file"),
) -> None:
    """Scan manuscript for overclaimed results."""
    from .core.overclaim import check_overclaims
    from .report import print_findings

    tex_path = Path(filepath)
    if not tex_path.exists():
        console.print(f"[red]Error: File not found: {filepath}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Scanning for overclaims:[/bold] {tex_path.name}\n")

    findings = check_overclaims(tex_path)
    print_findings(findings, "Overclaim Detection", console)

    # Summary
    critical = sum(1 for f in findings if f.severity == "critical")
    if critical > 0:
        console.print(f"\n[red bold]{critical} critical overclaims found. Address before submission.[/red bold]")
    elif findings:
        console.print(f"\n[yellow]{len(findings)} potential overclaims found. Review suggestions above.[/yellow]")
    else:
        console.print("\n[green]No overclaims detected.[/green]")


@app.command()
def report(
    filepath: str = typer.Argument(..., help="Path to .tex or .md manuscript"),
    bib: Optional[str] = typer.Option(None, "--bib", "-b", help="Path to .bib file"),
    code: Optional[str] = typer.Option(None, "--code", "-c", help="Code directory"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output Markdown file path"),
    skip_citations: bool = typer.Option(False, "--skip-citations", help="Skip citation verification"),
) -> None:
    """Generate a full integrity report (Markdown)."""
    from .core.consistency import check_consistency
    from .core.overclaim import check_overclaims
    from .core.statistics import check_statistics
    from .report import generate_markdown_report, print_review

    tex_path = Path(filepath)
    if not tex_path.exists():
        console.print(f"[red]Error: File not found: {filepath}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Generating integrity report:[/bold] {tex_path.name}\n")

    findings_by_check: dict[str, list] = {}

    # Run checks
    try:
        findings_by_check["Overclaim Detection"] = check_overclaims(tex_path)
    except Exception as e:
        console.print(f"[yellow]Overclaim check error: {e}[/yellow]")

    try:
        findings_by_check["Number Consistency"] = check_consistency(tex_path)
    except Exception as e:
        console.print(f"[yellow]Consistency check error: {e}[/yellow]")

    try:
        findings_by_check["Statistical Auditing"] = check_statistics(tex_path)
    except Exception as e:
        console.print(f"[yellow]Statistics check error: {e}[/yellow]")

    if bib and not skip_citations:
        try:
            from .core.citations import verify_bib_file

            findings_by_check["Citation Verification"] = verify_bib_file(bib)
        except Exception as e:
            console.print(f"[yellow]Citation check error: {e}[/yellow]")

    if code:
        try:
            from .core.evidence import check_evidence

            findings_by_check["Evidence Mapping"] = check_evidence(tex_path, code)
        except Exception as e:
            console.print(f"[yellow]Evidence check error: {e}[/yellow]")

    # Generate markdown
    out_path = output or f"{tex_path.stem}_integrity_report.md"
    md = generate_markdown_report(findings_by_check, out_path)

    console.print(f"[green]Report written to: {out_path}[/green]")

    # Also print summary to terminal
    total = sum(len(f) for f in findings_by_check.values())
    critical = sum(
        1 for fs in findings_by_check.values() for f in fs if getattr(f, "severity", "") == "critical"
    )
    console.print(f"\nTotal findings: {total} ({critical} critical)")


@app.command(name="install-hook")
def install_hook(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Git repo path (default: current directory)"),
) -> None:
    """Install a pre-commit hook for integrity checks."""
    from .integrations.precommit import install_precommit_hook

    repo_path = Path(path) if path else Path.cwd()

    try:
        hook_path = install_precommit_hook(repo_path)
        console.print(f"[green]Pre-commit hook installed: {hook_path}[/green]")
        console.print("The hook will check .tex and .md files for overclaims and consistency issues.")
    except Exception as e:
        console.print(f"[red]Error installing hook: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def stats(
    filepath: str = typer.Argument(..., help="Path to .tex or .md file"),
) -> None:
    """Audit statistical claims in a manuscript."""
    from .core.statistics import check_statistics
    from .report import print_findings

    tex_path = Path(filepath)
    if not tex_path.exists():
        console.print(f"[red]Error: File not found: {filepath}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Auditing statistics:[/bold] {tex_path.name}\n")

    findings = check_statistics(tex_path)
    print_findings(findings, "Statistical Auditing", console)


@app.command()
def params(
    filepath: str = typer.Argument(..., help="Path to Python file with ODE model"),
) -> None:
    """Check ODE parameter consistency in a Python file."""
    from .core.parameters import check_parameters
    from .report import print_findings

    py_path = Path(filepath)
    if not py_path.exists():
        console.print(f"[red]Error: File not found: {filepath}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Auditing parameters:[/bold] {py_path.name}\n")

    findings = check_parameters(py_path)
    print_findings(findings, "Parameter Consistency", console)


@app.command(name="time-units")
def time_units(
    directory: str = typer.Argument(..., help="Directory containing ODE model Python files"),
    solver: Optional[str] = typer.Option(None, "--solver", "-s", help="Additional solver/coupling directory"),
) -> None:
    """Audit time unit consistency across coupled ODE model files."""
    from .core.time_units import audit_time_units
    from .report import print_findings

    dir_path = Path(directory)
    if not dir_path.exists():
        console.print(f"[red]Error: Directory not found: {directory}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Auditing time units:[/bold] {dir_path}\n")

    solver_dirs = [Path(solver)] if solver else None
    findings = audit_time_units(dir_path, solver_directories=solver_dirs)
    print_findings(findings, "Time Unit Consistency", console)

    critical = sum(1 for f in findings if f.severity == "critical")
    warnings = sum(1 for f in findings if f.severity == "warning")
    if critical > 0:
        console.print(f"\n[red bold]{critical} critical time unit issue(s). Models may produce wrong results.[/red bold]")
    elif warnings > 0:
        console.print(f"\n[yellow]{warnings} warning(s). Review time unit declarations.[/yellow]")
    else:
        console.print("\n[green]No time unit issues detected.[/green]")


@app.command(name="verify-numbers")
def verify_numbers_cmd(
    tex_file: str = typer.Argument(..., help="Path to .tex manuscript file"),
    script: str = typer.Argument(..., help="Path to Python script that produces paper results"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Max seconds to run script"),
    warning_pct: float = typer.Option(5.0, "--warning", "-w", help="Warning threshold in percent"),
    critical_pct: float = typer.Option(20.0, "--critical", "-c", help="Critical threshold in percent"),
) -> None:
    """Verify that numbers in LaTeX tables match Python script output."""
    from .core.verify_numbers import verify_numbers
    from .report import print_findings

    tex_path = Path(tex_file)
    script_path = Path(script)
    if not tex_path.exists():
        console.print(f"[red]Error: File not found: {tex_file}[/red]")
        raise typer.Exit(1)
    if not script_path.exists():
        console.print(f"[red]Error: File not found: {script}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Verifying numbers:[/bold] {tex_path.name} vs {script_path.name}\n")

    findings = verify_numbers(
        tex_path=tex_path,
        script_path=script_path,
        timeout=timeout,
        warning_threshold=warning_pct / 100.0,
        critical_threshold=critical_pct / 100.0,
    )
    print_findings(findings, "Code-Paper Number Verification", console)

    critical = sum(1 for f in findings if f.severity == "critical")
    warnings = sum(1 for f in findings if f.severity == "warning")
    if critical > 0:
        console.print(f"\n[red bold]{critical} critical discrepancy(ies). Paper numbers do NOT match code output.[/red bold]")
    elif warnings > 0:
        console.print(f"\n[yellow]{warnings} warning(s). Some numbers differ slightly from code output.[/yellow]")
    else:
        console.print("\n[green]All table numbers consistent with script output.[/green]")


@app.command()
def serve() -> None:
    """Start the MCP server for editor integration."""
    console.print("[bold]Starting Rigorously MCP server...[/bold]")
    console.print("Waiting for MCP client connection (stdio).\n")
    import asyncio
    from .mcp_server import main as mcp_main
    asyncio.run(mcp_main())


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()


@app.command()
def example() -> None:
    """Run Rigorously on a built-in example paper with known issues."""
    from pathlib import Path
    example_path = Path(__file__).parent / "examples" / "bad_paper.tex"
    if not example_path.exists():
        console.print("[red]Example file not found[/red]")
        raise typer.Exit(1)
    console.print(f"\n[bold]Running on built-in example paper with known issues...[/bold]\n")
    # Run overclaims
    from .core.overclaim import check_overclaims
    from .core.consistency import check_consistency
    from .core.statistics import check_statistics
    from .report import print_findings
    findings = check_overclaims(example_path)
    print_findings(findings, "Overclaim Detection", console)
    findings = check_consistency(example_path)
    print_findings(findings, "Number Consistency", console)
    findings = check_statistics(example_path)
    print_findings(findings, "Statistical Auditing", console)

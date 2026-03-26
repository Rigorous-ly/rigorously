"""Plan CLI — human interface for the verification-gated registry.

Usage:
    rigorously plan load gates.yml
    rigorously plan status [spec-id]
    rigorously plan verify task.id
    rigorously plan regress-check [spec-id]
    rigorously plan models
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

plan_app = typer.Typer(
    name="plan",
    help="Verification-gated task registry. Trust nothing, verify everything.",
    no_args_is_help=True,
)
console = Console()


def _registry(db: str | None = None):
    from .registry import TaskRegistry
    return TaskRegistry(db_path=db)


@plan_app.command("load")
def load(
    yaml_path: str = typer.Argument(..., help="Path to YAML task definitions"),
    db: Optional[str] = typer.Option(None, "--db", help="Database path"),
) -> None:
    """Load task definitions from YAML into the registry."""
    reg = _registry(db)
    count = reg.load_yaml(yaml_path)
    console.print(f"[green]Loaded {count} tasks from {yaml_path}[/green]")


@plan_app.command("status")
def status(
    spec_id: str = typer.Argument("", help="Spec ID to filter (empty = all)"),
    state: str = typer.Option("", "--state", "-s", help="Filter by state"),
    db: Optional[str] = typer.Option(None, "--db", help="Database path"),
) -> None:
    """Show task status."""
    reg = _registry(db)
    tasks = reg.list_tasks(spec_id=spec_id, state=state)

    if not tasks:
        console.print("[dim]No tasks found.[/dim]")
        return

    table = Table(title=f"Plan Status{f' ({spec_id})' if spec_id else ''}")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", max_width=40)
    table.add_column("State", justify="center")
    table.add_column("Diff", justify="center")
    table.add_column("Claimed By")

    state_styles = {
        "pending": "[dim]pending[/dim]",
        "in_progress": "[yellow]working[/yellow]",
        "claimed": "[blue]claimed[/blue]",
        "verified": "[green]verified[/green]",
        "regressed": "[red]REGRESSED[/red]",
    }

    for t in tasks:
        s = state_styles.get(t["state"], t["state"])
        d = str(t["difficulty"])
        table.add_row(t["id"], t["title"][:40], s, d, t["claimed_by"] or "")

    console.print(table)

    # Summary
    counts = {}
    for t in tasks:
        counts[t["state"]] = counts.get(t["state"], 0) + 1
    parts = [f"{v} {k}" for k, v in sorted(counts.items())]
    console.print(f"\n[dim]{', '.join(parts)} ({len(tasks)} total)[/dim]")


@plan_app.command("verify")
def verify(
    task_id: str = typer.Argument(..., help="Task ID to verify"),
    db: Optional[str] = typer.Option(None, "--db", help="Database path"),
) -> None:
    """Run SIV for a specific task. Only the harness calls this."""
    reg = _registry(db)
    result = reg.verify(task_id)

    if result.get("passed"):
        console.print(f"[green]VERIFIED[/green] {task_id} ({result['duration']}s)")
        if result.get("contention"):
            for c in result["contention"]:
                console.print(f"  [yellow]CONTENTION:[/yellow] {c}")
    else:
        console.print(f"[red]FAILED[/red] {task_id}: {result.get('reason', '?')}")
        if result.get("stdout"):
            console.print(f"[dim]{result['stdout'][:500]}[/dim]")


@plan_app.command("regress-check")
def regress_check(
    spec_id: str = typer.Argument("", help="Spec ID (empty = all)"),
    db: Optional[str] = typer.Option(None, "--db", help="Database path"),
) -> None:
    """Re-verify all verified tasks. Flag regressions."""
    reg = _registry(db)
    regressions = reg.regress_check(spec_id)

    if not regressions:
        console.print("[green]All verified tasks still pass.[/green]")
    else:
        console.print(f"[red]{len(regressions)} REGRESSIONS:[/red]")
        for r in regressions:
            console.print(f"  [red]REGRESSED[/red] {r['task_id']}: {r.get('reason')}")


@plan_app.command("models")
def models(
    db: Optional[str] = typer.Option(None, "--db", help="Database path"),
) -> None:
    """Show model performance statistics."""
    reg = _registry(db)
    stats = reg.model_stats()

    if not stats:
        console.print("[dim]No model data yet.[/dim]")
        return

    table = Table(title="Model Performance")
    table.add_column("Model", style="cyan")
    table.add_column("Difficulty", justify="center")
    table.add_column("Attempts", justify="right")
    table.add_column("Success", justify="right")
    table.add_column("Fail", justify="right")
    table.add_column("Rate", justify="right")

    for s in stats:
        total = s["successes"] + s["failures"]
        rate = f"{s['successes']/total*100:.0f}%" if total > 0 else "-"
        table.add_row(
            s["model_id"], str(s["task_difficulty"]),
            str(s["attempts"]), str(s["successes"]),
            str(s["failures"]), rate,
        )

    console.print(table)

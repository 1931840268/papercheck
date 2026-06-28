"""Rich terminal report output."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from papercheck.models import Category, CheckResult, Severity

console = Console()

_SEVERITY_STYLE = {
    Severity.ERROR: "bold red",
    Severity.WARNING: "yellow",
    Severity.INFO: "dim",
}

_CATEGORY_EMOJI = {
    Category.REFERENCES: "📚",
    Category.CROSS_REFS: "🔗",
    Category.MATH: "🧮",
    Category.CONTENT: "📝",
    Category.FIGURES: "🖼️",
    Category.STRUCTURE: "🏗️",
    Category.ANONYMITY: "🕵️",
}


def print_report(result: CheckResult) -> None:
    """Print a beautiful terminal report."""
    console.print()

    # Score banner
    score = result.score
    if score >= 80:
        score_style = "bold green"
        grade = "GOOD"
    elif score >= 50:
        score_style = "bold yellow"
        grade = "NEEDS WORK"
    else:
        score_style = "bold red"
        grade = "HIGH RISK"

    header = Text()
    header.append("Paper Health: ", style="bold")
    header.append(f"{score}/100 ", style=score_style)
    header.append(f"({grade})", style=score_style)

    stats = (
        f"[dim]{result.total_lines} lines across {len(result.files_checked)} files | "
        f"[red]{result.error_count} errors[/red], "
        f"[yellow]{result.warning_count} warnings[/yellow], "
        f"[dim]{result.info_count} suggestions[/dim][/dim]"
    )

    console.print(
        Panel(
            f"{header}\n{stats}",
            title="📋 papercheck",
            border_style="cyan",
        )
    )

    if not result.issues:
        console.print(
            "\n[bold green]✨ No issues found! Paper looks ready for submission.[/bold green]\n"
        )
        return

    # Group by category
    by_cat = result.by_category()

    for category, issues in by_cat.items():
        emoji = _CATEGORY_EMOJI.get(category, "•")
        console.print(f"\n{emoji} [bold]{category.value.upper()}[/bold] ({len(issues)} issues)")

        table = Table(show_header=False, show_edge=False, pad_edge=False, expand=True)
        table.add_column("Sev", width=3)
        table.add_column("Code", width=8, style="dim")
        table.add_column("Location", width=20, style="cyan")
        table.add_column("Message", ratio=3)

        for issue in issues[:15]:  # Cap per category
            loc_str = str(issue.location) if issue.location else "—"
            sev_icon = issue.icon
            table.add_row(
                sev_icon,
                issue.code,
                loc_str,
                f"[{_SEVERITY_STYLE[issue.severity]}]{issue.message}[/]",
            )

        if len(issues) > 15:
            table.add_row("", "", "", f"[dim]... and {len(issues) - 15} more[/dim]")

        console.print(table)

    # Summary footer
    console.print()
    if result.error_count > 0:
        console.print(
            "[bold red]⛔ Fix errors before submission — likely desk rejection.[/bold red]"
        )
    elif result.warning_count > 0:
        console.print(
            "[yellow]⚡ Warnings won't block submission but reviewers may notice them.[/yellow]"
        )
    else:
        console.print("[green]✅ Only minor suggestions. Paper is in good shape.[/green]")
    console.print()

"""Watch mode — re-run checks on file changes with a live-updating summary."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from papercheck.engine import run_checks
from papercheck.models import CheckResult
from papercheck.parser import load_project

_WATCH_EXTENSIONS = {".tex", ".bib", ".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg"}
_DEBOUNCE_SECONDS = 0.5


def _collect_watched_files(target: Path) -> dict[Path, float]:
    """Return a mapping of watched file paths to their mtime."""
    mtimes: dict[Path, float] = {}
    if target.is_file():
        if target.suffix.lower() in _WATCH_EXTENSIONS:
            mtimes[target] = target.stat().st_mtime
        return mtimes
    for path in target.rglob("*"):
        if path.is_file() and path.suffix.lower() in _WATCH_EXTENSIONS:
            mtimes[path] = path.stat().st_mtime
    return mtimes


def _detect_changes(
    previous: dict[Path, float],
    current: dict[Path, float],
) -> list[Path]:
    """Return paths that were added, removed, or modified."""
    changed: list[Path] = []
    for path, mtime in current.items():
        if path not in previous or previous[path] != mtime:
            changed.append(path)
    for path in previous:
        if path not in current:
            changed.append(path)
    return changed


def _build_summary(
    result: CheckResult,
    check_time: datetime,
    changed_files: list[Path],
    run_duration: float,
) -> Panel:
    """Build a Rich panel showing the current check summary."""
    score = result.score
    if score >= 80:
        score_style = "bold green"
    elif score >= 50:
        score_style = "bold yellow"
    else:
        score_style = "bold red"

    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="dim")
    table.add_column()

    score_text = Text(f"{score}/100", style=score_style)
    table.add_row("Score", score_text)
    table.add_row("Errors", Text(str(result.error_count), style="red"))
    table.add_row("Warnings", Text(str(result.warning_count), style="yellow"))
    table.add_row("Info", Text(str(result.info_count), style="blue"))
    table.add_row("Files checked", Text(str(len(result.files_checked))))
    table.add_row("Lines", Text(str(result.total_lines)))
    table.add_row("Check duration", Text(f"{run_duration:.2f}s"))
    table.add_row("Last check", Text(check_time.strftime("%H:%M:%S")))

    if changed_files:
        names = ", ".join(p.name for p in changed_files[:5])
        if len(changed_files) > 5:
            names += f" (+{len(changed_files) - 5} more)"
        table.add_row("Changed", Text(names, style="cyan"))

    subtitle = "[dim]Watching for changes... Press Ctrl+C to stop[/dim]"
    return Panel(table, title="papercheck --watch", subtitle=subtitle, border_style="blue")


def watch_project(
    target: Path,
    anonymous: bool = True,
    interval: float = 1.0,
) -> None:
    """Watch a LaTeX project and re-run checks on changes.

    Polls watched files at *interval* seconds. When a change is detected,
    waits for the debounce window (500ms) to settle, then re-runs all checks
    and updates a Rich Live display with the summary.

    Args:
        target: Path to the project directory or main .tex file.
        anonymous: Whether to enforce anonymity checks.
        interval: Polling interval in seconds.
    """
    console = Console()
    target = target.resolve()

    console.print(f"[blue]papercheck[/blue] watching: [bold]{target}[/bold]")
    console.print("[dim]Running initial check...[/dim]\n")

    # Initial run
    project = load_project(target)
    start = time.monotonic()
    result = run_checks(project, anonymous=anonymous)
    duration = time.monotonic() - start
    check_time = datetime.now()
    changed: list[Path] = []

    previous_mtimes = _collect_watched_files(target)

    try:
        with Live(_build_summary(result, check_time, changed, duration), console=console) as live:
            while True:
                time.sleep(interval)

                current_mtimes = _collect_watched_files(target)
                changed = _detect_changes(previous_mtimes, current_mtimes)

                if not changed:
                    continue

                # Debounce: wait for changes to settle
                last_change = time.monotonic()
                while time.monotonic() - last_change < _DEBOUNCE_SECONDS:
                    time.sleep(0.1)
                    new_mtimes = _collect_watched_files(target)
                    new_changes = _detect_changes(current_mtimes, new_mtimes)
                    if new_changes:
                        last_change = time.monotonic()
                        current_mtimes = new_mtimes
                        changed = list(set(changed) | set(new_changes))

                previous_mtimes = current_mtimes

                # Re-run checks
                try:
                    project = load_project(target)
                    start = time.monotonic()
                    result = run_checks(project, anonymous=anonymous)
                    duration = time.monotonic() - start
                    check_time = datetime.now()
                except Exception as exc:
                    console.print(f"[red]Check failed:[/red] {exc}")
                    continue

                live.update(_build_summary(result, check_time, changed, duration))

    except KeyboardInterrupt:
        console.print("\n[blue]papercheck[/blue] watch stopped. Goodbye!")

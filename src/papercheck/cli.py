"""CLI entry point."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console

from papercheck.config import load_config
from papercheck.engine import run_checks
from papercheck.fixer import apply_fixes, compute_fixes, format_diff
from papercheck.html_report import generate_html_report
from papercheck.parser import load_project
from papercheck.report import print_report
from papercheck.watcher import watch_project

console = Console(stderr=True)


def main() -> None:
    """Lint a LaTeX paper for pre-submission issues."""
    args = sys.argv[1:]

    output_json = False
    output_html: str | None = None
    anonymous: bool | None = None  # None means "use config"
    strict = False
    watch = False
    fix_mode = False
    show_diff = False

    positional: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--help", "-h"):
            _print_help()
            sys.exit(0)
        elif arg == "--json":
            output_json = True
        elif arg == "--html":
            i += 1
            if i < len(args) and not args[i].startswith("-"):
                output_html = args[i]
            else:
                output_html = "papercheck-report.html"
                i -= 1  # Reprocess this arg
        elif arg == "--no-anon":
            anonymous = False
        elif arg == "--strict":
            strict = True
        elif arg == "--watch":
            watch = True
        elif arg == "--fix":
            fix_mode = True
        elif arg == "--diff":
            show_diff = True
        elif arg.startswith("-"):
            console.print(f"[red]Unknown flag: {arg}[/red]")
            sys.exit(2)
        else:
            positional.append(arg)
        i += 1

    if not positional:
        _print_help()
        sys.exit(0)

    target = Path(positional[0])
    if not target.exists():
        console.print(f"[red]Path not found: {target}[/red]")
        sys.exit(1)

    # Load configuration
    config_dir = target if target.is_dir() else target.parent
    config = load_config(config_dir)

    # Resolve anonymous setting: CLI flag > config > default True
    if anonymous is None:
        anonymous = config.anonymous

    # Watch mode
    if watch:
        watch_project(target, anonymous=anonymous)
        return

    # Load project
    project = load_project(target)
    if not project.tex_files:
        console.print("[red]No .tex files found.[/red]")
        sys.exit(1)

    # Run checks
    result = run_checks(project, anonymous=anonymous, config=config)

    # Fix mode: compute and apply auto-fixes
    if fix_mode or show_diff:
        fixes = compute_fixes(result.issues, project)
        if not fixes:
            console.print("[dim]No auto-fixable issues found.[/dim]")
        elif show_diff and not fix_mode:
            # Show diffs only
            for fix in fixes:
                console.print(f"[bold]{fix.description}[/bold] ({fix.code})")
                console.print(f"  [red]- {fix.original}[/red]")
                console.print(f"  [green]+ {fix.fixed}[/green]")
                console.print()
        elif fix_mode:
            if show_diff:
                for fix in fixes:
                    console.print(format_diff(fix))
                    console.print()
            count = apply_fixes(fixes, project.root)
            console.print(f"[green]Applied {count} fix(es).[/green]")
            # Re-run checks after fixes
            project = load_project(target)
            result = run_checks(project, anonymous=anonymous, config=config)

    # Output
    if output_json:
        data = {
            "score": result.score,
            "errors": result.error_count,
            "warnings": result.warning_count,
            "info": result.info_count,
            "files": result.files_checked,
            "issues": [
                {
                    "code": iss.code,
                    "severity": iss.severity.value,
                    "category": iss.category.value,
                    "message": iss.message,
                    "location": str(iss.location) if iss.location else None,
                    "suggestion": iss.suggestion,
                }
                for iss in result.issues
            ],
        }
        print(json.dumps(data, indent=2))
    elif output_html is not None:
        html_path = Path(output_html)
        generate_html_report(result, output_path=html_path)
        console.print(f"[green]HTML report written to {html_path}[/green]")
    else:
        print_report(result)

    # Exit code
    if strict and result.error_count > 0:
        sys.exit(1)


def _print_help() -> None:
    console.print(
        "[bold]papercheck[/bold] — Pre-submission linter for LaTeX research papers.\n\n"
        "Usage:\n"
        "  [cyan]papercheck paper.tex[/cyan]        Check a single file\n"
        "  [cyan]papercheck ./project/[/cyan]       Check entire project directory\n\n"
        "Options:\n"
        "  --json          Output JSON report\n"
        "  --html [FILE]   Generate standalone HTML report (default: papercheck-report.html)\n"
        "  --no-anon       Skip anonymity checks (camera-ready)\n"
        "  --strict        Exit code 1 if any errors found (for CI)\n"
        "  --watch         Watch for file changes and re-run checks\n"
        "  --fix           Auto-fix fixable issues (TYPO001-4, CONT002-5)\n"
        "  --diff          Show fix suggestions as diffs (combine with --fix to apply)\n"
    )

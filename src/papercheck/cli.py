"""CLI entry point."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console

from papercheck.engine import run_checks
from papercheck.parser import load_project
from papercheck.report import print_report

console = Console(stderr=True)


def main() -> None:
    """Lint a LaTeX paper for pre-submission issues."""
    args = sys.argv[1:]

    output_json = False
    anonymous = True
    strict = False

    positional: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--help", "-h"):
            _print_help()
            sys.exit(0)
        elif arg == "--json":
            output_json = True
        elif arg == "--no-anon":
            anonymous = False
        elif arg == "--strict":
            strict = True
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

    # Load project
    project = load_project(target)
    if not project.tex_files:
        console.print("[red]No .tex files found.[/red]")
        sys.exit(1)

    # Run checks
    result = run_checks(project, anonymous=anonymous)

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
                    "code": i.code,
                    "severity": i.severity.value,
                    "category": i.category.value,
                    "message": i.message,
                    "location": str(i.location) if i.location else None,
                    "suggestion": i.suggestion,
                }
                for i in result.issues
            ],
        }
        print(json.dumps(data, indent=2))
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
        "  --json        Output JSON report\n"
        "  --no-anon     Skip anonymity checks (camera-ready)\n"
        "  --strict      Exit code 1 if any errors found (for CI)\n"
    )

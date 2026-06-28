"""CLI entry point with subcommand support."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console

console = Console(stderr=True)


def main() -> None:
    """Main entry point — dispatch to subcommands or default lint."""
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        _print_main_help()
        sys.exit(0)

    # Check for subcommands
    cmd = args[0]
    if cmd == "pack":
        _cmd_pack(args[1:])
    elif cmd == "pdf":
        _cmd_pdf(args[1:])
    elif cmd == "suggest":
        _cmd_suggest(args[1:])
    else:
        # Default: lint mode (original behavior)
        _cmd_lint(args)


# ---------------------------------------------------------------------------
# Lint (default)
# ---------------------------------------------------------------------------


def _cmd_lint(args: list[str]) -> None:
    """Lint a LaTeX paper for pre-submission issues."""
    from papercheck.config import load_config
    from papercheck.engine import run_checks
    from papercheck.fixer import apply_fixes, compute_fixes, format_diff
    from papercheck.html_report import generate_html_report
    from papercheck.parser import load_project
    from papercheck.report import print_report
    from papercheck.watcher import watch_project

    output_json = False
    output_html: str | None = None
    anonymous: bool | None = None
    strict = False
    watch = False
    fix_mode = False
    show_diff = False

    positional: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--help", "-h"):
            _print_lint_help()
            sys.exit(0)
        elif arg == "--json":
            output_json = True
        elif arg == "--html":
            i += 1
            if i < len(args) and not args[i].startswith("-"):
                output_html = args[i]
            else:
                output_html = "papercheck-report.html"
                i -= 1
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
        _print_lint_help()
        sys.exit(0)

    target = Path(positional[0])
    if not target.exists():
        console.print(f"[red]Path not found: {target}[/red]")
        sys.exit(1)

    config_dir = target if target.is_dir() else target.parent
    config = load_config(config_dir)

    if anonymous is None:
        anonymous = config.anonymous

    if watch:
        watch_project(target, anonymous=anonymous)
        return

    project = load_project(target)
    if not project.tex_files:
        console.print("[red]No .tex files found.[/red]")
        sys.exit(1)

    result = run_checks(project, anonymous=anonymous, config=config)

    if fix_mode or show_diff:
        fixes = compute_fixes(result.issues, project)
        if not fixes:
            console.print("[dim]No auto-fixable issues found.[/dim]")
        elif show_diff and not fix_mode:
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
            project = load_project(target)
            result = run_checks(project, anonymous=anonymous, config=config)

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

    if strict and result.error_count > 0:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Pack
# ---------------------------------------------------------------------------


def _cmd_pack(args: list[str]) -> None:
    """Package a LaTeX project for arXiv submission."""
    from papercheck.pack import pack

    output: str | None = None
    positional: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--help", "-h"):
            _print_pack_help()
            sys.exit(0)
        elif arg in ("-o", "--output"):
            i += 1
            if i < len(args):
                output = args[i]
            else:
                console.print("[red]-o requires an argument[/red]")
                sys.exit(2)
        elif arg.startswith("-"):
            console.print(f"[red]Unknown flag: {arg}[/red]")
            sys.exit(2)
        else:
            positional.append(arg)
        i += 1

    if not positional:
        _print_pack_help()
        sys.exit(0)

    project_dir = Path(positional[0])
    if not project_dir.exists():
        console.print(f"[red]Path not found: {project_dir}[/red]")
        sys.exit(1)

    out_path = Path(output) if output else None
    result = pack(project_dir, output=out_path)

    if result.errors:
        for err in result.errors:
            console.print(f"[red]ERROR:[/red] {err}")
        sys.exit(1)

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]WARNING:[/yellow] {w}")

    console.print(f"\n[green]Archive created:[/green] {result.output_path}")
    console.print(f"  Files: {len(result.files)}")
    total_mb = result.total_size / 1024 / 1024
    console.print(f"  Total size: {total_mb:.2f} MB")
    console.print("\n  Contents:")
    for name, size in result.files:
        console.print(f"    {name} ({size / 1024:.1f} KB)")


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def _cmd_pdf(args: list[str]) -> None:
    """Validate a PDF for submission readiness."""
    from papercheck.pdf_check import check_pdf

    venue: str | None = None
    max_pages: int | None = None
    positional: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--help", "-h"):
            _print_pdf_help()
            sys.exit(0)
        elif arg == "--venue":
            i += 1
            if i < len(args):
                venue = args[i]
            else:
                console.print("[red]--venue requires an argument[/red]")
                sys.exit(2)
        elif arg == "--pages":
            i += 1
            if i < len(args):
                max_pages = int(args[i])
            else:
                console.print("[red]--pages requires an argument[/red]")
                sys.exit(2)
        elif arg.startswith("-"):
            console.print(f"[red]Unknown flag: {arg}[/red]")
            sys.exit(2)
        else:
            positional.append(arg)
        i += 1

    if not positional:
        _print_pdf_help()
        sys.exit(0)

    pdf_path = Path(positional[0])
    result = check_pdf(pdf_path, venue=venue, max_pages=max_pages)

    console.print(f"\n[bold]PDF Check:[/bold] {result.path.name}")
    console.print(f"  Pages: {result.pages}")
    if result.pdf_version:
        console.print(f"  Version: PDF {result.pdf_version}")
    console.print(f"  PyMuPDF: {'yes' if result.has_pymupdf else 'no (limited checks)'}")

    if result.metadata:
        console.print("\n  [yellow]Metadata:[/yellow]")
        for k, v in result.metadata.items():
            console.print(f"    {k}: {v}")

    if result.issues:
        console.print()
        for issue in result.issues:
            color = {"error": "red", "warning": "yellow", "info": "blue"}[issue.severity]
            console.print(f"  [{color}]{issue.severity.upper()}:[/{color}] {issue.message}")

    if result.ok:
        console.print("\n  [green]PDF looks ready for submission.[/green]")
    else:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Suggest
# ---------------------------------------------------------------------------


def _cmd_suggest(args: list[str]) -> None:
    """Suggest citations for a LaTeX document."""
    from papercheck.suggest import suggest

    include_bib = False
    positional: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--help", "-h"):
            _print_suggest_help()
            sys.exit(0)
        elif arg == "--bib":
            include_bib = True
        elif arg.startswith("-"):
            console.print(f"[red]Unknown flag: {arg}[/red]")
            sys.exit(2)
        else:
            positional.append(arg)
        i += 1

    if not positional:
        _print_suggest_help()
        sys.exit(0)

    tex_path = Path(positional[0])
    if not tex_path.exists():
        console.print(f"[red]File not found: {tex_path}[/red]")
        sys.exit(1)

    console.print("[dim]Extracting key phrases and querying Semantic Scholar...[/dim]")
    result = suggest(tex_path, include_bibtex=include_bib)

    if result.errors:
        for err in result.errors:
            console.print(f"[red]ERROR:[/red] {err}")
        sys.exit(1)

    console.print(f"\n[bold]Key phrases extracted:[/bold] {len(result.key_phrases)}")
    for p in result.key_phrases:
        console.print(f"  - {p[:80]}")

    if not result.suggestions:
        console.print("\n[yellow]No new citation suggestions found.[/yellow]")
        return

    console.print(f"\n[bold]Top {len(result.suggestions)} suggestions:[/bold]\n")
    for i, s in enumerate(result.suggestions, 1):
        console.print(
            f"  {i}. [bold]{s.title}[/bold]\n"
            f"     {s.author_str} ({s.year or '?'}) "
            f"— {s.citation_count} citations\n"
            f"     [dim]{s.reason}[/dim]"
        )
        if s.bibtex:
            console.print(f"\n{s.bibtex}\n")
        console.print()


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------


def _print_main_help() -> None:
    console.print(
        "[bold]papercheck[/bold] — Pre-submission toolkit for LaTeX research papers.\n\n"
        "Commands:\n"
        "  [cyan]papercheck paper.tex[/cyan]              Lint (default)\n"
        "  [cyan]papercheck pack ./project/ -o out.tar.gz[/cyan]  "
        "Package for arXiv\n"
        "  [cyan]papercheck pdf paper.pdf[/cyan]          Validate PDF\n"
        "  [cyan]papercheck suggest paper.tex[/cyan]      Citation suggestions\n\n"
        "Run [cyan]papercheck <command> --help[/cyan] for command-specific options."
    )


def _print_lint_help() -> None:
    console.print(
        "[bold]papercheck[/bold] [file.tex | dir/] — Lint for pre-submission issues.\n\n"
        "Options:\n"
        "  --json          Output JSON report\n"
        "  --html [FILE]   Generate HTML report\n"
        "  --no-anon       Skip anonymity checks\n"
        "  --strict        Exit 1 if errors found (CI)\n"
        "  --watch         Watch for changes\n"
        "  --fix           Auto-fix fixable issues\n"
        "  --diff          Show fix diffs\n"
    )


def _print_pack_help() -> None:
    console.print(
        "[bold]papercheck pack[/bold] [dir/] — Package LaTeX project for arXiv.\n\n"
        "Options:\n"
        "  -o, --output FILE   Output .tar.gz path (default: submission.tar.gz)\n"
    )


def _print_pdf_help() -> None:
    console.print(
        "[bold]papercheck pdf[/bold] [file.pdf] — Validate PDF for submission.\n\n"
        "Options:\n"
        "  --venue NAME    Check against venue page limit "
        "(neurips, icml, iclr, aaai, cvpr, acl, ...)\n"
        "  --pages N       Explicit page limit\n"
    )


def _print_suggest_help() -> None:
    console.print(
        "[bold]papercheck suggest[/bold] [file.tex] — Citation suggestions.\n\n"
        "Options:\n"
        "  --bib    Include BibTeX entries in output\n"
    )

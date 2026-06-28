"""Figure and table checks."""

from __future__ import annotations

from papercheck.models import Category, Issue, Location, Severity, TexProject
from papercheck.parser import ParsedTex


def check_missing_graphics(
    parsed: ParsedTex,
    project: TexProject,
    filename: str,
) -> list[Issue]:
    """Check that \\includegraphics paths point to existing files."""
    issues = []
    for img_path, line in parsed.graphics.items():
        # Try common extensions if none specified
        found = _resolve_image(img_path, project)
        if not found:
            issues.append(
                Issue(
                    code="FIG001",
                    message=f"Image file not found: {img_path}",
                    severity=Severity.ERROR,
                    category=Category.FIGURES,
                    location=Location(filename, line),
                    suggestion="Check the file path and ensure the image exists.",
                )
            )
    return issues


def check_unreferenced_figures(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Detect figure/table environments that are never referenced in text."""
    issues = []
    all_ref_targets = set(parsed.refs.keys())

    for env_name, start_line, end_line in parsed.environments:
        if env_name not in ("figure", "figure*", "table", "table*"):
            continue
        # Find the label inside this environment
        env_labels = [key for key, line in parsed.labels.items() if start_line <= line <= end_line]
        for label in env_labels:
            if label not in all_ref_targets:
                issues.append(
                    Issue(
                        code="FIG002",
                        message=f"Unreferenced {env_name}: \\label{{{label}}}",
                        severity=Severity.WARNING,
                        category=Category.FIGURES,
                        location=Location(filename, start_line),
                        suggestion=f"Add \\ref{{{label}}} in text or remove.",
                    )
                )
    return issues


def check_figure_placement(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Warn about figures without placement specifiers."""
    issues = []
    import re

    begin_fig_re = re.compile(r"\\begin\{(figure|table)\*?\}\s*$")

    for lineno, line in enumerate(parsed.lines, 1):
        match = begin_fig_re.match(line.strip())
        if match and "[" not in line:
            env = match.group(1)
            issues.append(
                Issue(
                    code="FIG003",
                    message=f"\\begin{{{env}}} without placement specifier",
                    severity=Severity.INFO,
                    category=Category.FIGURES,
                    location=Location(filename, lineno),
                    suggestion=f"Add [t] or [htbp]: \\begin{{{env}}}[t]",
                )
            )
    return issues


def _resolve_image(img_path: str, project: TexProject) -> bool:
    """Check if an image path resolves to an existing file."""
    # Direct check
    if img_path in project.image_files:
        return True

    # Try with common extensions
    extensions = ["", ".png", ".jpg", ".jpeg", ".pdf", ".eps"]
    for ext in extensions:
        candidate = img_path + ext
        if candidate in project.image_files:
            return True
        # Also check with path normalization
        norm = candidate.replace("\\", "/")
        if norm in project.image_files or any(
            f.replace("\\", "/") == norm for f in project.image_files
        ):
            return True

    # Check if file exists on disk
    full_path = project.root / img_path
    return any((full_path.parent / (full_path.name + ext)).exists() for ext in extensions)

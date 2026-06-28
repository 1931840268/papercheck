"""Document structure checks."""

from __future__ import annotations

import re

from papercheck.models import Category, Issue, Location, Severity
from papercheck.parser import ParsedTex

_ABSTRACT_RE = re.compile(r"\\begin\{abstract\}")


def check_missing_abstract(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Check that the paper has an abstract."""
    has_abstract = any(env[0] == "abstract" for env in parsed.environments)
    if not has_abstract:
        # Also check for \abstract{} style
        full_text = "\n".join(parsed.lines)
        if "\\begin{abstract}" not in full_text and "\\abstract{" not in full_text:
            return [
                Issue(
                    code="STRUCT001",
                    message="No abstract found",
                    severity=Severity.WARNING,
                    category=Category.STRUCTURE,
                    location=Location(filename, 1),
                    suggestion="Add \\begin{abstract}...\\end{abstract}.",
                )
            ]
    return []


def check_section_ordering(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Check that section nesting is logical (no subsection before section)."""
    issues = []
    level_order = {"chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4}
    last_level = -1

    for level_name, title, lineno in parsed.sections:
        level = level_order.get(level_name, 5)
        if level > last_level + 1 and last_level >= 0:
            issues.append(
                Issue(
                    code="STRUCT002",
                    message=f"Section level jump: \\{level_name}{{{title}}} without parent section",
                    severity=Severity.WARNING,
                    category=Category.STRUCTURE,
                    location=Location(filename, lineno),
                    suggestion="Add a parent section or change the heading level.",
                )
            )
        last_level = level

    return issues


def check_bibliography(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Check that a bibliography is included."""
    full_text = "\n".join(parsed.lines)
    has_bib = (
        "\\bibliography{" in full_text
        or "\\printbibliography" in full_text
        or "\\begin{thebibliography}" in full_text
    )
    if not has_bib:
        return [
            Issue(
                code="STRUCT003",
                message="No bibliography command found",
                severity=Severity.WARNING,
                category=Category.STRUCTURE,
                location=Location(filename, len(parsed.lines)),
                suggestion="Add \\bibliography{refs} or \\printbibliography.",
            )
        ]
    return []


def check_document_class(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Verify a \\documentclass is present."""
    full_text = "\n".join(parsed.lines)
    if "\\documentclass" not in full_text:
        return [
            Issue(
                code="STRUCT004",
                message="No \\documentclass found — is this the main file?",
                severity=Severity.INFO,
                category=Category.STRUCTURE,
                location=Location(filename, 1),
            )
        ]
    return []

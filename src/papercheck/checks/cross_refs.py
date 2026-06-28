"""Cross-reference checks (\\label / \\ref consistency)."""

from __future__ import annotations

from papercheck.models import Category, Issue, Location, Severity
from papercheck.parser import ParsedTex


def check_undefined_refs(parsed: ParsedTex, all_labels: set[str], filename: str) -> list[Issue]:
    """Find \\ref{key} where key has no corresponding \\label."""
    issues = []
    for key, lines in parsed.refs.items():
        if key not in all_labels:
            issues.append(
                Issue(
                    code="XREF001",
                    message=f"Undefined reference: \\ref{{{key}}}",
                    severity=Severity.ERROR,
                    category=Category.CROSS_REFS,
                    location=Location(filename, lines[0]),
                    suggestion="Add a \\label{" + key + "} or fix the typo.",
                )
            )
    return issues


def check_unused_labels(parsed: ParsedTex, all_refs: set[str], filename: str) -> list[Issue]:
    """Find \\label{key} that is never referenced."""
    issues = []
    for key, line in parsed.labels.items():
        if key not in all_refs:
            issues.append(
                Issue(
                    code="XREF002",
                    message=f"Unused label: \\label{{{key}}}",
                    severity=Severity.INFO,
                    category=Category.CROSS_REFS,
                    location=Location(filename, line),
                    suggestion="Reference this label or remove it.",
                )
            )
    return issues


def check_duplicate_labels(all_labels_with_loc: list[tuple[str, str, int]]) -> list[Issue]:
    """Detect the same label defined in multiple places."""
    issues = []
    seen: dict[str, tuple[str, int]] = {}
    for key, filename, line in all_labels_with_loc:
        if key in seen:
            prev_file, prev_line = seen[key]
            issues.append(
                Issue(
                    code="XREF003",
                    message=f"Duplicate label: \\label{{{key}}} (first at {prev_file}:{prev_line})",
                    severity=Severity.ERROR,
                    category=Category.CROSS_REFS,
                    location=Location(filename, line),
                    suggestion="Rename one of the duplicate labels.",
                )
            )
        else:
            seen[key] = (filename, line)
    return issues

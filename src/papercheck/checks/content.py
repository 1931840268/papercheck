"""Content checks: TODO markers, anonymity, repeated words, common issues."""

from __future__ import annotations

import re

from papercheck.models import Category, Issue, Location, Severity
from papercheck.parser import ParsedTex

# Patterns for anonymity violations
_ANON_PATTERNS = [
    (re.compile(r"\\author\{[^}]+\}", re.IGNORECASE), "Author name in \\author{}"),
    (re.compile(r"\\institute\{[^}]+\}", re.IGNORECASE), "Institute in \\institute{}"),
    (re.compile(r"our previous work\s*\\cite", re.IGNORECASE), "Self-citation hint"),
    (re.compile(r"we previously showed", re.IGNORECASE), "Self-reference language"),
    (re.compile(r"in our earlier", re.IGNORECASE), "Self-reference language"),
    (re.compile(r"github\.com/[a-zA-Z0-9_-]+/", re.IGNORECASE), "GitHub URL with username"),
]

# Common academic writing issues
_WRITING_PATTERNS = [
    (re.compile(r"\b(\w+)\s+\1\b"), "CONT001", "Repeated word: '{0}'"),
    (re.compile(r"\betc\b(?!\.)"), "CONT002", "'etc' should be followed by a period: 'etc.'"),
    (re.compile(r"\bi\.e\b(?!\.)"), "CONT003", "Use 'i.e.' with period"),
    (re.compile(r"\be\.g\b(?!\.)"), "CONT004", "Use 'e.g.' with period"),
    (re.compile(r"(?<!\.)\.{3}(?!\.)"), "CONT005", "Use \\ldots instead of '...' in LaTeX"),
    (re.compile(r"\bvery unique\b", re.I), "CONT006", "'Very unique' — unique is absolute"),
    (re.compile(r"\bin order to\b", re.I), "CONT007", "'In order to' can be simplified to 'to'"),
    (re.compile(r"\bthis paper\b", re.I), "CONT008", "Consider 'this work' for anonymity"),
]

_TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX|TEMP)\b", re.IGNORECASE)
_TRAILING_SPACE_RE = re.compile(r"[ \t]+$")


def check_todo_markers(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Find TODO/FIXME markers left in the source."""
    issues = []
    for lineno, line in enumerate(parsed.lines, 1):
        for match in _TODO_RE.finditer(line):
            issues.append(
                Issue(
                    code="CONT010",
                    message=f"TODO marker found: {match.group(0)}",
                    severity=Severity.WARNING,
                    category=Category.CONTENT,
                    location=Location(filename, lineno),
                    suggestion="Remove or address this before submission.",
                )
            )
    return issues


def check_anonymity(parsed: ParsedTex, filename: str, anonymous: bool = True) -> list[Issue]:
    """Check for anonymity violations in blind submissions."""
    if not anonymous:
        return []
    issues = []
    full_text = "\n".join(parsed.lines)
    for pattern, description in _ANON_PATTERNS:
        for match in pattern.finditer(full_text):
            # Find line number
            pos = match.start()
            line = full_text[:pos].count("\n") + 1
            issues.append(
                Issue(
                    code="ANON001",
                    message=f"Potential anonymity violation: {description}",
                    severity=Severity.ERROR,
                    category=Category.ANONYMITY,
                    location=Location(filename, line),
                    suggestion="Remove or anonymize for blind review.",
                )
            )
    return issues


def check_writing_issues(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Check for common academic writing issues."""
    issues = []
    for lineno, line in enumerate(parsed.lines, 1):
        # Skip comments and commands
        if line.strip().startswith("%"):
            continue
        for pattern, code, msg_template in _WRITING_PATTERNS:
            for match in pattern.finditer(line):
                msg = msg_template.format(match.group(1) if match.groups() else match.group(0))
                issues.append(
                    Issue(
                        code=code,
                        message=msg,
                        severity=Severity.INFO,
                        category=Category.CONTENT,
                        location=Location(filename, lineno),
                    )
                )
    return issues


def check_empty_sections(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Detect sections with no content between them."""
    issues = []
    sections = parsed.sections
    for i in range(len(sections) - 1):
        _, title, start_line = sections[i]
        _, _, next_line = sections[i + 1]
        # Check if there's meaningful content between sections
        content_between = parsed.lines[start_line : next_line - 1]  # lines between
        non_empty = [
            line for line in content_between if line.strip() and not line.strip().startswith("%")
        ]
        if len(non_empty) <= 1:  # Only the section command itself
            issues.append(
                Issue(
                    code="CONT011",
                    message=f"Section '{title}' appears to be empty",
                    severity=Severity.WARNING,
                    category=Category.CONTENT,
                    location=Location(filename, start_line),
                    suggestion="Add content or remove the section.",
                )
            )
    return issues

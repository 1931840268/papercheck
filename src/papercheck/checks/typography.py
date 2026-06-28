"""LaTeX typography checks — spacing, dashes, quotes, punctuation."""

from __future__ import annotations

import re

from papercheck.models import Category, Issue, Location, Severity
from papercheck.parser import ParsedTex

# --- Patterns ---

# Missing ~ before \cite (should be "text~\cite{}" not "text \cite{}")
_CITE_NO_TILDE = re.compile(r"[a-zA-Z0-9]\s+\\cite")
# Missing ~ before \ref
_REF_NO_TILDE = re.compile(r"[a-zA-Z]\s+\\ref")
# Wrong quotes: "text" should be ``text''
_WRONG_QUOTES = re.compile(r'"([^"]+)"')
# Hyphen used for range instead of en-dash (e.g., "pages 1-10" not "pages 1--10")
_HYPHEN_RANGE = re.compile(r"\b(\d+)-(\d+)\b")
# Three dots instead of \ldots or \dots
_THREE_DOTS = re.compile(r"(?<!\.)\.{3}(?!\.)")
# Space before punctuation
_SPACE_BEFORE_PUNCT = re.compile(r"\s+[,;:!?](?!\w)")
# Double space
_DOUBLE_SPACE = re.compile(r"(?<!\\)  +(?!\\)")
# Period followed by lowercase (possible abbreviation spacing issue)
_ABBREV_SPACING = re.compile(r"\b(e\.g|i\.e|et al|vs|cf|Fig|Tab|Eq|Sec)\.\s+[A-Z]")
# \\ at end of line outside tabular (common mistake: line break in text)
_WRONG_LINEBREAK = re.compile(r"\\\\\s*$")


def check_typography(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Check for LaTeX typography issues."""
    issues = []
    in_tabular = False

    for lineno, line in enumerate(parsed.lines, 1):
        stripped = line.strip()
        if stripped.startswith("%"):
            continue

        # Track environments
        if "\\begin{tabular" in line or "\\begin{align" in line or "\\begin{equation" in line:
            in_tabular = True
        if "\\end{tabular" in line or "\\end{align" in line or "\\end{equation" in line:
            in_tabular = False

        # Skip checks inside math/tabular environments
        if in_tabular:
            continue

        # Non-breaking space before \cite
        if _CITE_NO_TILDE.search(line):
            issues.append(Issue(
                code="TYPO001",
                message="Missing ~ before \\cite (use 'text~\\cite{key}' for non-breaking space)",
                severity=Severity.INFO,
                category=Category.CONTENT,
                location=Location(filename, lineno),
                suggestion="Replace space with ~ to prevent line break before citation.",
            ))

        # Non-breaking space before \ref
        if _REF_NO_TILDE.search(line):
            issues.append(Issue(
                code="TYPO002",
                message="Missing ~ before \\ref (use 'Figure~\\ref{fig:x}')",
                severity=Severity.INFO,
                category=Category.CONTENT,
                location=Location(filename, lineno),
                suggestion="Replace space with ~ to prevent line break before reference.",
            ))

        # Wrong quotation marks
        for match in _WRONG_QUOTES.finditer(line):
            # Skip if inside a command argument
            pos = match.start()
            before = line[:pos]
            if before.endswith("{") or "\\url{" in before or "\\href{" in before:
                continue
            issues.append(Issue(
                code="TYPO003",
                message=f"Use LaTeX quotes: ``{match.group(1)}'' instead of \"{match.group(1)}\"",
                severity=Severity.WARNING,
                category=Category.CONTENT,
                location=Location(filename, lineno),
                suggestion="Replace \" with `` (opening) and '' (closing).",
            ))

        # Hyphen for number range
        for match in _HYPHEN_RANGE.finditer(line):
            n1, n2 = int(match.group(1)), int(match.group(2))
            if n2 > n1 and n2 - n1 < 1000:  # Likely a range, not subtraction
                # Skip if inside math or a command
                pos = match.start()
                if "$" in line[:pos] and line[:pos].count("$") % 2 == 1:
                    continue
                issues.append(Issue(
                    code="TYPO004",
                    message=f"Use en-dash for range: {n1}--{n2} instead of {n1}-{n2}",
                    severity=Severity.INFO,
                    category=Category.CONTENT,
                    location=Location(filename, lineno),
                    suggestion="Replace - with -- for number ranges.",
                ))

        # Wrong linebreak in text
        if (
            _WRONG_LINEBREAK.search(stripped)
            and not in_tabular
            and not any(cmd in line for cmd in ["\\\\[", "\\newline", "\\hline"])
        ):
                issues.append(Issue(
                    code="TYPO005",
                    message="Bare \\\\ in text paragraph (use \\par or blank line instead)",
                    severity=Severity.WARNING,
                    category=Category.CONTENT,
                    location=Location(filename, lineno),
                    suggestion="Use a blank line for paragraph breaks, not \\\\.",
                ))

    return issues

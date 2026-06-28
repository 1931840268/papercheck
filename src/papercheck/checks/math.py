"""Math notation checks: unclosed delimiters, inconsistent notation."""

from __future__ import annotations

import re
from collections import Counter

from papercheck.models import Category, Issue, Location, Severity
from papercheck.parser import ParsedTex

_LEFT_RE = re.compile(r"\\left[(\[{|.]")
_RIGHT_RE = re.compile(r"\\right[)\]}|.]")
_MATH_CMD_RE = re.compile(r"\\(mathbf|mathbb|mathcal|mathrm|bm|boldsymbol|hat|tilde)\{(\w+)\}")


def check_math_delimiters(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Check for mismatched \\left/\\right and unclosed $ signs."""
    issues = []

    for lineno, line in enumerate(parsed.lines, 1):
        if line.strip().startswith("%"):
            continue

        # Check $...$ balance on each line
        # Count $ that aren't $$ and aren't escaped
        dollars = [i for i, c in enumerate(line) if c == "$" and (i == 0 or line[i - 1] != "\\")]
        # Filter out $$ (display math)
        single_dollars = []
        i = 0
        while i < len(dollars):
            if i + 1 < len(dollars) and dollars[i + 1] == dollars[i] + 1:
                i += 2  # Skip $$
            else:
                single_dollars.append(dollars[i])
                i += 1

        if len(single_dollars) % 2 != 0:
            issues.append(
                Issue(
                    code="MATH001",
                    message="Unclosed inline math delimiter ($)",
                    severity=Severity.ERROR,
                    category=Category.MATH,
                    location=Location(filename, lineno),
                    suggestion="Add a matching $ to close the math environment.",
                )
            )

        # Check \left/\right balance
        lefts = len(_LEFT_RE.findall(line))
        rights = len(_RIGHT_RE.findall(line))
        if lefts != rights:
            issues.append(
                Issue(
                    code="MATH002",
                    message=f"Mismatched \\left/\\right ({lefts} left, {rights} right)",
                    severity=Severity.WARNING,
                    category=Category.MATH,
                    location=Location(filename, lineno),
                    suggestion="Add matching \\right (use \\left. for invisible).",
                )
            )

    return issues


def check_notation_consistency(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Detect inconsistent notation for the same symbol."""
    issues = []

    # Collect all math command usages: e.g. \mathbf{x} vs \bm{x}
    symbol_styles: dict[str, Counter[str]] = {}  # symbol -> Counter of style commands

    for _lineno, line in enumerate(parsed.lines, 1):
        for match in _MATH_CMD_RE.finditer(line):
            cmd = match.group(1)
            symbol = match.group(2)
            symbol_styles.setdefault(symbol, Counter())[cmd] += 1

    # Flag symbols used with multiple styling commands
    for symbol, styles in symbol_styles.items():
        if len(styles) > 1:
            style_desc = ", ".join(f"\\{cmd}{{{symbol}}} ({n}x)" for cmd, n in styles.most_common())
            issues.append(
                Issue(
                    code="MATH003",
                    message=f"Inconsistent notation for '{symbol}': {style_desc}",
                    severity=Severity.WARNING,
                    category=Category.MATH,
                    location=Location(filename, 0),
                    suggestion="Pick one style and use it consistently throughout the paper.",
                )
            )

    return issues

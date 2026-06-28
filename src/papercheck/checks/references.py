"""Reference and citation checks."""

from __future__ import annotations

from papercheck.models import Category, Issue, Location, Severity
from papercheck.parser import ParsedTex


def check_undefined_citations(
    parsed: ParsedTex,
    bib_keys: set[str],
    filename: str,
) -> list[Issue]:
    """Find \\cite{key} where key is not in any .bib file."""
    issues = []
    for key, lines in parsed.citations.items():
        if key not in bib_keys:
            issues.append(
                Issue(
                    code="REF001",
                    message=f"Undefined citation: \\cite{{{key}}}",
                    severity=Severity.ERROR,
                    category=Category.REFERENCES,
                    location=Location(filename, lines[0]),
                    suggestion=f"Add '{key}' to your .bib file or fix the typo.",
                )
            )
    return issues


def check_uncited_bib_entries(
    all_cited_keys: set[str],
    bib_keys: set[str],
    bib_filename: str,
) -> list[Issue]:
    """Find .bib entries that are never cited in any .tex file."""
    issues = []
    orphans = bib_keys - all_cited_keys
    for key in sorted(orphans):
        issues.append(
            Issue(
                code="REF002",
                message=f"Uncited bibliography entry: {key}",
                severity=Severity.INFO,
                category=Category.REFERENCES,
                location=Location(bib_filename, 0),
                suggestion="Remove unused entry or add a citation.",
            )
        )
    return issues


def check_duplicate_citations(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Detect the same citation key appearing multiple times in one \\cite{} command."""
    issues = []
    import re

    cite_re = re.compile(r"\\cite[tp]?\{([^}]+)\}")
    for lineno, line in enumerate(parsed.lines, 1):
        for match in cite_re.finditer(line):
            keys = [k.strip() for k in match.group(1).split(",")]
            seen = set()
            for key in keys:
                if key in seen:
                    issues.append(
                        Issue(
                            code="REF003",
                            message=f"Duplicate key in citation command: {key}",
                            severity=Severity.WARNING,
                            category=Category.REFERENCES,
                            location=Location(filename, lineno),
                            suggestion="Remove the duplicate key.",
                        )
                    )
                seen.add(key)
    return issues

"""Venue-specific compliance checks."""

from __future__ import annotations

import re

from papercheck.models import Category, Issue, Location, Severity
from papercheck.parser import ParsedTex

# Venue detection from documentclass or style files
_VENUE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "neurips": [re.compile(r"neurips", re.I), re.compile(r"\\usepackage\{neurips")],
    "icml": [re.compile(r"icml", re.I), re.compile(r"\\usepackage\{icml")],
    "cvpr": [re.compile(r"cvpr", re.I), re.compile(r"\\documentclass.*cvpr")],
    "iclr": [re.compile(r"iclr", re.I)],
    "acl": [re.compile(r"acl.*2|\\usepackage\{acl", re.I)],
    "aaai": [re.compile(r"aaai", re.I)],
    "ieee": [re.compile(r"IEEEtran", re.I)],
}

# Required elements per venue
_VENUE_REQUIREMENTS: dict[str, dict[str, str]] = {
    "neurips": {
        "checklist": "NeurIPS requires a paper checklist (\\section{Checklist} checklist).",
        "ethics": "Consider adding a broader impact statement.",
    },
    "icml": {
        "checklist": "ICML requires a reproducibility statement.",
    },
    "acl": {
        "limitations": "ACL *CL venues REQUIRE a Limitations section.",
        "ethics": "ACL recommends an Ethics Statement.",
    },
}


def check_venue_compliance(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Detect venue and check for venue-specific requirements."""
    issues = []
    full_text = "\n".join(parsed.lines)

    # Detect venue
    detected_venue = _detect_venue(full_text)
    if not detected_venue:
        return []

    # Check venue-specific requirements
    requirements = _VENUE_REQUIREMENTS.get(detected_venue, {})
    section_titles = [title.lower() for _, title, _ in parsed.sections]

    if "checklist" in requirements:
        has_checklist = any("checklist" in s for s in section_titles)
        if not has_checklist:
            issues.append(Issue(
                code="VENUE001",
                message=f"[{detected_venue.upper()}] {requirements['checklist']}",
                severity=Severity.WARNING,
                category=Category.STRUCTURE,
                location=Location(filename, 0),
                suggestion="Add the required checklist section before submission.",
            ))

    if "limitations" in requirements:
        has_limitations = any("limitation" in s for s in section_titles)
        if not has_limitations:
            issues.append(Issue(
                code="VENUE002",
                message=f"[{detected_venue.upper()}] {requirements['limitations']}",
                severity=Severity.ERROR,
                category=Category.STRUCTURE,
                location=Location(filename, 0),
                suggestion="Add \\section{Limitations} — this is mandatory for this venue.",
            ))

    if "ethics" in requirements:
        has_ethics = any("ethic" in s or "impact" in s for s in section_titles)
        if not has_ethics and "ethic" not in full_text.lower():
            issues.append(Issue(
                code="VENUE003",
                message=f"[{detected_venue.upper()}] {requirements['ethics']}",
                severity=Severity.INFO,
                category=Category.STRUCTURE,
                location=Location(filename, 0),
                suggestion="Consider adding an Ethics/Broader Impact section.",
            ))

    # Check for common venue-specific formatting issues
    if detected_venue == "ieee":
        _check_ieee(parsed, filename, issues)

    return issues


def _detect_venue(text: str) -> str | None:
    """Detect the target venue from document content."""
    for venue, patterns in _VENUE_PATTERNS.items():
        if any(p.search(text) for p in patterns):
            return venue
    return None


def _check_ieee(parsed: ParsedTex, filename: str, issues: list[Issue]) -> None:
    """IEEE-specific checks."""
    full_text = "\n".join(parsed.lines)

    # IEEE requires \IEEEpeerreviewmaketitle or \maketitle
    if "\\maketitle" not in full_text and "\\IEEEpeerreviewmaketitle" not in full_text:
        issues.append(Issue(
            code="VENUE010",
            message="[IEEE] Missing \\maketitle command",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            location=Location(filename, 0),
        ))

    # IEEE prefers \IEEEauthorblockN for authors
    if "\\author{" in full_text and "\\IEEEauthorblockN" not in full_text:
        issues.append(Issue(
            code="VENUE011",
            message="[IEEE] Consider using \\IEEEauthorblockN for author formatting",
            severity=Severity.INFO,
            category=Category.STRUCTURE,
            location=Location(filename, 0),
        ))

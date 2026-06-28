"""Academic writing quality checks — hedge words, weasel words, informality."""

from __future__ import annotations

import re

from papercheck.models import Category, Issue, Location, Severity
from papercheck.parser import ParsedTex

# Weasel words that weaken claims without evidence
_WEASEL_WORDS = [
    "clearly", "obviously", "trivially", "easily", "simply",
    "of course", "it is well known", "it is clear that",
    "needless to say", "it goes without saying",
]

# Hedge words (excessive hedging = weak writing)
_HEDGE_WORDS = [
    "might", "could", "perhaps", "possibly", "somewhat",
    "relatively", "fairly", "rather", "quite", "slightly",
]

# Informal words/phrases to avoid in academic writing
_INFORMAL = [
    (r"\ba lot\b", "'a lot' → 'significantly/substantially'"),
    (r"\bbig\b", "'big' → 'large/substantial'"),
    (r"\bget\b(?!\w)", "'get' → 'obtain/achieve'"),
    (r"\bgot\b", "'got' → 'obtained/achieved'"),
    (r"\bkind of\b", "'kind of' → omit or 'somewhat'"),
    (r"\bsort of\b", "'sort of' → omit or 'approximately'"),
    (r"\bstuff\b", "'stuff' → specific noun"),
    (r"\bthings\b", "'things' → specific noun"),
    (r"\bbasically\b", "'basically' → omit"),
    (r"\bactually\b", "'actually' → omit or 'in fact'"),
    (r"\breally\b", "'really' → omit or 'substantially'"),
]

# Contractions (should not appear in formal writing)
_CONTRACTIONS = re.compile(
    r"\b(don't|won't|can't|isn't|aren't|wasn't|weren't|hasn't|haven't|"
    r"hadn't|doesn't|didn't|couldn't|wouldn't|shouldn't|it's|that's|"
    r"there's|here's|what's|who's|let's)\b", re.IGNORECASE
)

# Sentences starting with "But", "And", "So" (debatable but flagworthy)
_SENTENCE_START = re.compile(r"(?:^|\.\s+)(But|And|So|Also)\s+[A-Z]")

# Very long sentences (>50 words)
_WORD_RE = re.compile(r"\b\w+\b")


def check_language_quality(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Check for academic writing quality issues."""
    issues = []
    hedge_count = 0
    weasel_count = 0

    for lineno, line in enumerate(parsed.lines, 1):
        stripped = line.strip()
        if stripped.startswith("%") or stripped.startswith("\\"):
            continue

        # Contractions
        for match in _CONTRACTIONS.finditer(stripped):
            issues.append(Issue(
                code="LANG001",
                message=f"Contraction in formal writing: '{match.group(0)}'",
                severity=Severity.WARNING,
                category=Category.CONTENT,
                location=Location(filename, lineno),
                suggestion=f"Expand: '{match.group(0)}' → full form.",
            ))

        # Informal words
        for pattern, suggestion in _INFORMAL:
            for _match in re.finditer(pattern, stripped, re.IGNORECASE):
                issues.append(Issue(
                    code="LANG002",
                    message=f"Informal language: {suggestion}",
                    severity=Severity.INFO,
                    category=Category.CONTENT,
                    location=Location(filename, lineno),
                ))

        # Count hedges and weasels (report summary, not each instance)
        lower = stripped.lower()
        for w in _HEDGE_WORDS:
            if w in lower:
                hedge_count += 1
        for w in _WEASEL_WORDS:
            if w in lower:
                weasel_count += 1

    # Summary issues for density
    total_lines = len([ln for ln in parsed.lines if ln.strip() and not ln.strip().startswith("%")])
    if total_lines > 20:
        hedge_ratio = hedge_count / total_lines
        if hedge_ratio > 0.05:
            issues.append(Issue(
                code="LANG003",
                message=f"High hedge word density ({hedge_count} instances in {total_lines} lines)",
                severity=Severity.INFO,
                category=Category.CONTENT,
                location=Location(filename, 0),
                suggestion="Reduce hedging — state findings with confidence.",
            ))

        weasel_ratio = weasel_count / total_lines
        if weasel_ratio > 0.03:
            issues.append(Issue(
                code="LANG004",
                message=f"Weasel words ({weasel_count}x): 'clearly', 'obviously', etc.",
                severity=Severity.INFO,
                category=Category.CONTENT,
                location=Location(filename, 0),
                suggestion="Remove weasel words — provide evidence instead of assertions.",
            ))

    return issues

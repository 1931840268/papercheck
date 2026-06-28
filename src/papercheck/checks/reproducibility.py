"""Reproducibility checklist checks — NeurIPS/ICML/ICLR style requirements."""

from __future__ import annotations

import re

from papercheck.models import Category, Issue, Location, Severity
from papercheck.parser import ParsedTex

# Keywords indicating reproducibility elements
_SEED_PATTERNS = [
    re.compile(r"random\s*seed", re.I),
    re.compile(r"seed\s*=\s*\d+", re.I),
    re.compile(r"reproducib", re.I),
]

_HYPERPARAMS = [
    re.compile(r"learning\s*rate", re.I),
    re.compile(r"batch\s*size", re.I),
    re.compile(r"epoch", re.I),
    re.compile(r"optimizer", re.I),
    re.compile(r"Adam|SGD|AdamW", re.I),
    re.compile(r"lr\s*=", re.I),
    re.compile(r"dropout", re.I),
    re.compile(r"weight\s*decay", re.I),
]

_COMPUTE_PATTERNS = [
    re.compile(r"GPU|TPU|A100|V100|H100|RTX", re.I),
    re.compile(r"compute|hardware|device", re.I),
    re.compile(r"training\s*time|wall[\s-]*clock", re.I),
    re.compile(r"hours?|minutes?", re.I),
]

_CODE_PATTERNS = [
    re.compile(r"code.*available|open[\s-]*source", re.I),
    re.compile(r"github\.com|gitlab\.com|bitbucket", re.I),
    re.compile(r"supplementary\s*material", re.I),
    re.compile(r"anonymous.*url|anonymized.*repository", re.I),
]

_DATASET_PATTERNS = [
    re.compile(r"dataset|benchmark|corpus", re.I),
    re.compile(r"train(?:ing)?.*split|test.*split|validation", re.I),
    re.compile(r"samples?|instances?|examples?", re.I),
]

_STATS_PATTERNS = [
    re.compile(r"mean|average|std|standard\s*deviation", re.I),
    re.compile(r"±|\\pm", re.I),
    re.compile(r"confidence\s*interval", re.I),
    re.compile(r"statistical.*significan", re.I),
    re.compile(r"p[\s-]*value|t[\s-]*test|wilcoxon", re.I),
]

_LIMITATION_PATTERNS = [
    re.compile(r"\\section\{.*[Ll]imitation", re.I),
    re.compile(r"\\section\{.*[Bb]roader [Ii]mpact", re.I),
    re.compile(r"\\section\{.*[Ee]thic", re.I),
    re.compile(r"limitation|shortcoming|drawback", re.I),
]


def check_reproducibility(parsed: ParsedTex, filename: str) -> list[Issue]:
    """Check for reproducibility elements required by top venues."""
    issues = []
    full_text = "\n".join(parsed.lines)

    # Check each category
    checks = [
        ("REPR001", "No random seed mentioned",
         _SEED_PATTERNS, Severity.WARNING,
         "Report random seeds for reproducibility (required by NeurIPS/ICML checklist)."),

        ("REPR002", "No hyperparameter details found",
         _HYPERPARAMS, Severity.WARNING,
         "Report learning rate, batch size, optimizer, epochs for reproducibility."),

        ("REPR003", "No compute/hardware information",
         _COMPUTE_PATTERNS, Severity.INFO,
         "Report GPU type, training time, and compute resources used."),

        ("REPR004", "No code availability statement",
         _CODE_PATTERNS, Severity.WARNING,
         "Add a code availability statement (even 'will be released upon acceptance')."),

        ("REPR005", "No dataset description found",
         _DATASET_PATTERNS, Severity.WARNING,
         "Describe datasets: size, splits, preprocessing, and access method."),

        ("REPR006", "No error bars or statistical reporting",
         _STATS_PATTERNS, Severity.WARNING,
         "Report mean±std over multiple runs or confidence intervals."),

        ("REPR007", "No limitations section",
         _LIMITATION_PATTERNS, Severity.INFO,
         "Consider adding a Limitations section (required by ACL, recommended by others)."),
    ]

    for code, message, patterns, severity, suggestion in checks:
        found = any(p.search(full_text) for p in patterns)
        if not found:
            issues.append(Issue(
                code=code,
                message=message,
                severity=severity,
                category=Category.STRUCTURE,
                location=Location(filename, 0),
                suggestion=suggestion,
            ))

    return issues

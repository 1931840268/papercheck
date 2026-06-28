"""Data models for papercheck."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(Enum):
    """Issue severity level."""

    ERROR = "error"  # Will likely cause desk rejection
    WARNING = "warning"  # Reviewers will notice
    INFO = "info"  # Suggestion for improvement


class Category(Enum):
    """Issue category."""

    REFERENCES = "references"
    CROSS_REFS = "cross-refs"
    MATH = "math"
    CONTENT = "content"
    FIGURES = "figures"
    STRUCTURE = "structure"
    ANONYMITY = "anonymity"


@dataclass(frozen=True)
class Location:
    """Source location of an issue."""

    file: str
    line: int
    col: int = 0

    def __str__(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass(frozen=True)
class Issue:
    """A single detected issue."""

    code: str  # e.g. "REF001"
    message: str
    severity: Severity
    category: Category
    location: Location | None = None
    suggestion: str = ""

    @property
    def icon(self) -> str:
        return {"error": "❌", "warning": "⚠️", "info": "💡"}[self.severity.value]


@dataclass
class CheckResult:
    """Aggregated results from all checks."""

    issues: list[Issue] = field(default_factory=list)
    files_checked: list[str] = field(default_factory=list)
    total_lines: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.INFO)

    @property
    def score(self) -> int:
        """Paper health score (0-100). Deduct points per issue."""
        deductions = self.error_count * 10 + self.warning_count * 3 + self.info_count * 1
        return max(0, 100 - deductions)

    def by_category(self) -> dict[Category, list[Issue]]:
        groups: dict[Category, list[Issue]] = {}
        for issue in self.issues:
            groups.setdefault(issue.category, []).append(issue)
        return groups


@dataclass
class TexProject:
    """Parsed LaTeX project."""

    root: Path
    main_file: str
    tex_files: dict[str, str] = field(default_factory=dict)  # filename -> content
    bib_files: dict[str, str] = field(default_factory=dict)  # filename -> content
    image_files: list[str] = field(default_factory=list)  # paths to images

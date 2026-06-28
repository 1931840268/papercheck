"""Auto-fix module: compute fix suggestions and apply them to LaTeX source files."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from papercheck.models import Issue, TexProject

# --- Fixable rule patterns ---
# Each entry: (code, regex_pattern, replacement_function_or_string)

_CITE_NO_TILDE = re.compile(r"(?<=[a-zA-Z0-9])\s+(\\cite)")
_REF_NO_TILDE = re.compile(r"(?<=[a-zA-Z])\s+(\\ref)")
_WRONG_QUOTES = re.compile(r'"([^"]+)"')
_HYPHEN_RANGE = re.compile(r"\b(\d+)-(\d+)\b")
_ETC_NO_DOT = re.compile(r"\betc\b(?!\.)")
_IE_NO_DOT = re.compile(r"\bi\.e\b(?!\.)")
_EG_NO_DOT = re.compile(r"\be\.g\b(?!\.)")
_THREE_DOTS = re.compile(r"(?<!\.)\.{3}(?!\.)")

FIXABLE_CODES = frozenset({
    "TYPO001", "TYPO002", "TYPO003", "TYPO004",
    "CONT002", "CONT003", "CONT004", "CONT005",
})


@dataclass
class FixSuggestion:
    """A concrete fix that can be auto-applied."""

    file: str
    line: int
    original: str  # The original line content
    fixed: str  # The fixed line content
    code: str  # Rule code
    description: str


def _apply_typo001(line: str) -> str:
    """Replace space before \\cite with ~."""
    return _CITE_NO_TILDE.sub(r"~\1", line)


def _apply_typo002(line: str) -> str:
    """Replace space before \\ref with ~."""
    return _REF_NO_TILDE.sub(r"~\1", line)


def _apply_typo003(line: str) -> str:
    """Replace straight quotes with LaTeX quotes."""

    def _replace_quote(match: re.Match[str]) -> str:
        pos = match.start()
        before = line[:pos]
        # Skip if inside a command argument like \url{} or \href{}
        if before.endswith("{") or "\\url{" in before or "\\href{" in before:
            return match.group(0)
        return f"``{match.group(1)}''"

    return _WRONG_QUOTES.sub(_replace_quote, line)


def _apply_typo004(line: str) -> str:
    """Replace hyphen range with en-dash."""

    def _replace_range(match: re.Match[str]) -> str:
        n1, n2 = int(match.group(1)), int(match.group(2))
        if n2 > n1 and n2 - n1 < 1000:
            # Skip if inside math mode
            pos = match.start()
            if "$" in line[:pos] and line[:pos].count("$") % 2 == 1:
                return match.group(0)
            return f"{match.group(1)}--{match.group(2)}"
        return match.group(0)

    return _HYPHEN_RANGE.sub(_replace_range, line)


def _apply_cont002(line: str) -> str:
    """Replace 'etc' with 'etc.'."""
    return _ETC_NO_DOT.sub("etc.", line)


def _apply_cont003(line: str) -> str:
    """Replace 'i.e' with 'i.e.'."""
    return _IE_NO_DOT.sub("i.e.", line)


def _apply_cont004(line: str) -> str:
    """Replace 'e.g' with 'e.g.'."""
    return _EG_NO_DOT.sub("e.g.", line)


def _apply_cont005(line: str) -> str:
    """Replace '...' with '\\ldots'."""
    return _THREE_DOTS.sub(r"\\ldots", line)


_FIX_DISPATCH: dict[str, tuple[callable, str]] = {
    "TYPO001": (_apply_typo001, "Replace space with ~ before \\cite"),
    "TYPO002": (_apply_typo002, "Replace space with ~ before \\ref"),
    "TYPO003": (_apply_typo003, "Replace straight quotes with LaTeX quotes"),
    "TYPO004": (_apply_typo004, "Replace hyphen with en-dash for range"),
    "CONT002": (_apply_cont002, "Add period after 'etc'"),
    "CONT003": (_apply_cont003, "Add period after 'i.e'"),
    "CONT004": (_apply_cont004, "Add period after 'e.g'"),
    "CONT005": (_apply_cont005, "Replace '...' with \\ldots"),
}


def compute_fixes(issues: list[Issue], project: TexProject) -> list[FixSuggestion]:
    """Compute auto-fixable suggestions for issues.

    Only issues with codes in FIXABLE_CODES and valid locations are processed.
    The fix is computed by applying the rule-specific transform to the source line.
    """
    fixes: list[FixSuggestion] = []

    for issue in issues:
        if issue.code not in FIXABLE_CODES:
            continue
        if issue.location is None:
            continue

        filename = issue.location.file
        lineno = issue.location.line

        # Get the source content for this file
        content = project.tex_files.get(filename)
        if content is None:
            continue

        lines = content.splitlines()
        if lineno < 1 or lineno > len(lines):
            continue

        original = lines[lineno - 1]
        fix_func, description = _FIX_DISPATCH[issue.code]
        fixed = fix_func(original)

        # Only suggest if the line actually changed
        if fixed != original:
            fixes.append(FixSuggestion(
                file=filename,
                line=lineno,
                original=original,
                fixed=fixed,
                code=issue.code,
                description=description,
            ))

    # Deduplicate: multiple issues on the same line may produce the same fix
    seen: set[tuple[str, int]] = set()
    unique_fixes: list[FixSuggestion] = []
    for fix in fixes:
        key = (fix.file, fix.line)
        if key in seen:
            # Merge: apply the new fix on top of the already-fixed line
            for i, existing in enumerate(unique_fixes):
                if existing.file == fix.file and existing.line == fix.line:
                    merged_func, _merged_desc = _FIX_DISPATCH[fix.code]
                    merged_line = merged_func(existing.fixed)
                    if merged_line != existing.fixed:
                        unique_fixes[i] = FixSuggestion(
                            file=fix.file,
                            line=fix.line,
                            original=existing.original,
                            fixed=merged_line,
                            code=f"{existing.code}+{fix.code}",
                            description=f"{existing.description}; {fix.description}",
                        )
                    break
        else:
            seen.add(key)
            unique_fixes.append(fix)

    return unique_fixes


def format_diff(fix: FixSuggestion) -> str:
    """Format a fix as a colorless unified-diff-style snippet.

    Output example:
        --- a/main.tex:42
        +++ b/main.tex:42
        -  results show that \\cite{foo}
        +  results show that~\\cite{foo}
    """
    header = (
        f"--- a/{fix.file}:{fix.line}\n"
        f"+++ b/{fix.file}:{fix.line}\n"
        f"- {fix.original}\n"
        f"+ {fix.fixed}"
    )
    return header


def apply_fixes(fixes: list[FixSuggestion], project_root: Path) -> int:
    """Apply fixes to files on disk. Returns count of fixes applied.

    Fixes are grouped by file and applied from bottom to top (highest line number
    first) to avoid line-number shifts invalidating subsequent fixes.
    """
    if not fixes:
        return 0

    # Group fixes by file
    by_file: dict[str, list[FixSuggestion]] = defaultdict(list)
    for fix in fixes:
        by_file[fix.file].append(fix)

    applied = 0

    for filename, file_fixes in by_file.items():
        filepath = project_root / filename
        if not filepath.is_file():
            continue

        # Read the current file content
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        # Sort fixes by line number descending to apply from bottom to top
        file_fixes.sort(key=lambda f: f.line, reverse=True)

        for fix in file_fixes:
            idx = fix.line - 1
            if idx < 0 or idx >= len(lines):
                continue

            # Preserve the original line ending
            current_line = lines[idx]
            ending = ""
            if current_line.endswith("\r\n"):
                ending = "\r\n"
            elif current_line.endswith("\n"):
                ending = "\n"
            elif current_line.endswith("\r"):
                ending = "\r"

            # Verify the line content matches what we expect (stripped of ending)
            current_stripped = current_line.rstrip("\r\n")
            if current_stripped != fix.original:
                continue

            lines[idx] = fix.fixed + ending
            applied += 1

        # Write back
        filepath.write_text("".join(lines), encoding="utf-8")

    return applied

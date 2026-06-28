"""Tests for the fixer module."""

from __future__ import annotations

from pathlib import Path

from papercheck.fixer import (
    FixSuggestion,
    apply_fixes,
    compute_fixes,
    format_diff,
)
from papercheck.models import (
    Category,
    Issue,
    Location,
    Severity,
    TexProject,
)


class TestComputeFixes:
    def _make_project(self, content: str) -> TexProject:
        return TexProject(
            root=Path("/fake"),
            main_file="main.tex",
            tex_files={"main.tex": content},
        )

    def test_fix_typo001_cite_tilde(self):
        content = "As shown by Author \\cite{foo}."
        project = self._make_project(content)
        issues = [
            Issue(
                code="TYPO001",
                message="Missing ~",
                severity=Severity.INFO,
                category=Category.CONTENT,
                location=Location("main.tex", 1),
            )
        ]
        fixes = compute_fixes(issues, project)
        assert len(fixes) == 1
        assert "~\\cite" in fixes[0].fixed

    def test_fix_typo003_quotes(self):
        content = 'We call this a "novel" approach.'
        project = self._make_project(content)
        issues = [
            Issue(
                code="TYPO003",
                message="Wrong quotes",
                severity=Severity.WARNING,
                category=Category.CONTENT,
                location=Location("main.tex", 1),
            )
        ]
        fixes = compute_fixes(issues, project)
        assert len(fixes) == 1
        assert "``novel''" in fixes[0].fixed

    def test_fix_cont002_etc(self):
        content = "We tested many methods, etc and found results."
        project = self._make_project(content)
        issues = [
            Issue(
                code="CONT002",
                message="etc should have period",
                severity=Severity.INFO,
                category=Category.CONTENT,
                location=Location("main.tex", 1),
            )
        ]
        fixes = compute_fixes(issues, project)
        assert len(fixes) == 1
        assert "etc." in fixes[0].fixed

    def test_no_fix_for_unfixable(self):
        content = "Some text"
        project = self._make_project(content)
        issues = [
            Issue(
                code="REF001",
                message="Undefined citation",
                severity=Severity.ERROR,
                category=Category.REFERENCES,
                location=Location("main.tex", 1),
            )
        ]
        fixes = compute_fixes(issues, project)
        assert len(fixes) == 0

    def test_no_fix_without_location(self):
        content = "Some text"
        project = self._make_project(content)
        issues = [
            Issue(
                code="TYPO001",
                message="Missing ~",
                severity=Severity.INFO,
                category=Category.CONTENT,
                location=None,
            )
        ]
        fixes = compute_fixes(issues, project)
        assert len(fixes) == 0


class TestFormatDiff:
    def test_diff_format(self):
        fix = FixSuggestion(
            file="main.tex",
            line=42,
            original="results show that \\cite{foo}",
            fixed="results show that~\\cite{foo}",
            code="TYPO001",
            description="Replace space with ~ before \\cite",
        )
        diff = format_diff(fix)
        assert "--- a/main.tex:42" in diff
        assert "+++ b/main.tex:42" in diff
        assert "- results show that \\cite{foo}" in diff
        assert "+ results show that~\\cite{foo}" in diff


class TestApplyFixes:
    def test_applies_fixes_to_file(self, tmp_path):
        tex_file = tmp_path / "main.tex"
        tex_file.write_text("Line 1\nresults show that \\cite{foo}\nLine 3\n")

        fixes = [
            FixSuggestion(
                file="main.tex",
                line=2,
                original="results show that \\cite{foo}",
                fixed="results show that~\\cite{foo}",
                code="TYPO001",
                description="test",
            )
        ]
        count = apply_fixes(fixes, tmp_path)
        assert count == 1
        content = tex_file.read_text()
        assert "that~\\cite{foo}" in content
        assert "Line 1" in content  # Other lines unchanged
        assert "Line 3" in content

    def test_applies_multiple_fixes_bottom_to_top(self, tmp_path):
        tex_file = tmp_path / "main.tex"
        tex_file.write_text("Line 1\nAuthor \\cite{a}\nAuthor \\cite{b}\nLine 4\n")

        fixes = [
            FixSuggestion(
                file="main.tex",
                line=2,
                original="Author \\cite{a}",
                fixed="Author~\\cite{a}",
                code="TYPO001",
                description="test",
            ),
            FixSuggestion(
                file="main.tex",
                line=3,
                original="Author \\cite{b}",
                fixed="Author~\\cite{b}",
                code="TYPO001",
                description="test",
            ),
        ]
        count = apply_fixes(fixes, tmp_path)
        assert count == 2

    def test_empty_fixes(self, tmp_path):
        count = apply_fixes([], tmp_path)
        assert count == 0

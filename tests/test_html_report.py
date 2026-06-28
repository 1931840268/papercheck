"""Tests for the HTML report generator."""

from __future__ import annotations

from papercheck.html_report import generate_html_report
from papercheck.models import (
    Category,
    CheckResult,
    Issue,
    Location,
    Severity,
)


class TestHtmlReport:
    def _make_result(self) -> CheckResult:
        return CheckResult(
            issues=[
                Issue(
                    code="REF001",
                    message="Undefined citation: foo",
                    severity=Severity.ERROR,
                    category=Category.REFERENCES,
                    location=Location("main.tex", 10),
                ),
                Issue(
                    code="TYPO001",
                    message="Missing ~ before \\cite",
                    severity=Severity.INFO,
                    category=Category.CONTENT,
                    location=Location("main.tex", 20),
                    suggestion="Replace space with ~.",
                ),
                Issue(
                    code="LANG001",
                    message="Contraction: don't",
                    severity=Severity.WARNING,
                    category=Category.CONTENT,
                    location=Location("intro.tex", 5),
                ),
            ],
            files_checked=["main.tex", "intro.tex"],
            total_lines=150,
        )

    def test_returns_html_string(self):
        result = self._make_result()
        html = generate_html_report(result)
        assert "<!DOCTYPE html>" in html
        assert "papercheck report" in html

    def test_contains_score(self):
        result = self._make_result()
        html = generate_html_report(result)
        # Score should be in the output
        assert str(result.score) in html

    def test_contains_issue_codes(self):
        result = self._make_result()
        html = generate_html_report(result)
        assert "REF001" in html
        assert "TYPO001" in html
        assert "LANG001" in html

    def test_contains_severity_classes(self):
        result = self._make_result()
        html = generate_html_report(result)
        assert "error" in html
        assert "warning" in html
        assert "info" in html

    def test_writes_to_file(self, tmp_path):
        result = self._make_result()
        out_file = tmp_path / "report.html"
        html = generate_html_report(result, output_path=out_file)
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert content == html

    def test_empty_result(self):
        result = CheckResult(files_checked=["main.tex"], total_lines=100)
        html = generate_html_report(result)
        assert "No issues found" in html
        assert "100" in html  # score should be 100

    def test_escapes_html(self):
        result = CheckResult(
            issues=[
                Issue(
                    code="TEST",
                    message="Found <script>alert('xss')</script>",
                    severity=Severity.ERROR,
                    category=Category.CONTENT,
                    location=Location("main.tex", 1),
                ),
            ],
            files_checked=["main.tex"],
            total_lines=10,
        )
        html = generate_html_report(result)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

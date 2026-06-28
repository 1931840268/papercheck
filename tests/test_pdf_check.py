"""Tests for the pdf_check module."""

from __future__ import annotations

import builtins
from pathlib import Path
from unittest.mock import patch

from papercheck.pdf_check import (
    VENUE_LIMITS,
    PDFCheckResult,
    _check_page_limit,
    check_pdf,
)

original_import = builtins.__import__


def _mock_import_no_fitz(name, *args, **kwargs):
    """Mock import that raises ImportError for fitz."""
    if name == "fitz":
        raise ImportError("No module named 'fitz'")
    return original_import(name, *args, **kwargs)


class TestCheckPdfBasic:
    def test_file_not_found(self, tmp_path):
        result = check_pdf(tmp_path / "nonexistent.pdf")
        assert not result.ok
        assert any("not found" in i.message.lower() for i in result.issues)

    def test_not_a_pdf(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("not a pdf")
        result = check_pdf(f)
        assert not result.ok
        assert any("not a PDF" in i.message for i in result.issues)

    def test_basic_pdf_header(self, tmp_path):
        """Basic check reads PDF version from header."""
        pdf = tmp_path / "test.pdf"
        # Minimal PDF-like content
        content = b"%PDF-1.5\n" + b"/Type /Page\n" * 3 + b"/Type /Pages\n"
        pdf.write_bytes(content)
        with (
            patch.dict("sys.modules", {"fitz": None}),
            patch("builtins.__import__", side_effect=_mock_import_no_fitz),
        ):
            result = check_pdf(pdf)
        assert result.pdf_version == "1.5"


class TestPageLimitCheck:
    def test_warns_over_limit(self):
        result = PDFCheckResult(path=Path("x.pdf"), pages=12)
        _check_page_limit(result, venue="neurips", max_pages=None)
        assert any("exceeds" in i.message for i in result.issues)

    def test_ok_under_limit(self):
        result = PDFCheckResult(path=Path("x.pdf"), pages=8)
        _check_page_limit(result, venue="neurips", max_pages=None)
        assert not any("exceeds" in i.message for i in result.issues)

    def test_unknown_venue(self):
        result = PDFCheckResult(path=Path("x.pdf"), pages=5)
        _check_page_limit(result, venue="unknownvenue", max_pages=None)
        assert any("Unknown venue" in i.message for i in result.issues)

    def test_explicit_max_pages(self):
        result = PDFCheckResult(path=Path("x.pdf"), pages=15)
        _check_page_limit(result, venue=None, max_pages=10)
        assert any("exceeds" in i.message for i in result.issues)


class TestVenueLimits:
    def test_known_venues(self):
        assert "neurips" in VENUE_LIMITS
        assert "icml" in VENUE_LIMITS
        assert "iclr" in VENUE_LIMITS
        assert VENUE_LIMITS["neurips"] == 9

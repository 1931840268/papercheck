"""Tests for the suggest (citation suggestion) module."""

from __future__ import annotations

import builtins
from unittest.mock import patch

from papercheck.suggest import (
    Suggestion,
    extract_key_phrases,
    generate_bibtex,
    get_bib_titles,
    get_existing_cite_keys,
    suggest,
)

_original_import = builtins.__import__


def _mock_import_no_httpx(name, *args, **kwargs):
    """Mock import that raises ImportError for httpx."""
    if name == "httpx":
        raise ImportError("No module named 'httpx'")
    return _original_import(name, *args, **kwargs)


class TestExtractKeyPhrases:
    def test_extracts_title(self):
        tex = r"\title{Deep Learning for Natural Language Processing}"
        phrases = extract_key_phrases(tex)
        assert any("Deep Learning" in p for p in phrases)

    def test_extracts_section_headings(self):
        tex = (
            r"\section{Introduction}" + "\n"
            r"\section{Methodology}" + "\n"
            r"\section{Experiments}" + "\n"
        )
        phrases = extract_key_phrases(tex)
        assert any("Methodology" in p for p in phrases)
        assert any("Experiments" in p for p in phrases)

    def test_skips_generic_sections(self):
        tex = (
            r"\section{Introduction}" + "\n"
            r"\section{Conclusion}" + "\n"
            r"\section{References}" + "\n"
        )
        phrases = extract_key_phrases(tex)
        # These generic sections should be excluded
        assert not any("Introduction" in p for p in phrases)
        assert not any("Conclusion" in p for p in phrases)
        assert not any("References" in p for p in phrases)

    def test_extracts_bold_terms(self):
        tex = (
            r"\textbf{attention mechanism} is key. "
            r"We also use \textbf{attention mechanism} in layer 2."
        )
        phrases = extract_key_phrases(tex)
        assert any("attention mechanism" in p for p in phrases)

    def test_extracts_abstract(self):
        tex = (
            r"\begin{abstract}" + "\n"
            "We propose a novel approach to image segmentation.\n"
            r"\end{abstract}"
        )
        phrases = extract_key_phrases(tex)
        assert any("image segmentation" in p or "novel approach" in p for p in phrases)

    def test_respects_max_phrases(self):
        tex = "\n".join(f"\\section{{Topic {i}}}" for i in range(20))
        phrases = extract_key_phrases(tex, max_phrases=5)
        assert len(phrases) <= 5


class TestGetExistingCiteKeys:
    def test_extracts_cite_keys(self):
        tex = r"We cite \cite{smith2020} and \citep{jones2021,wang2022}."
        keys = get_existing_cite_keys(tex)
        assert "smith2020" in keys
        assert "jones2021" in keys
        assert "wang2022" in keys

    def test_handles_citet(self):
        tex = r"\citet{brown2020} showed that..."
        keys = get_existing_cite_keys(tex)
        assert "brown2020" in keys


class TestGetBibTitles:
    def test_extracts_titles(self, tmp_path):
        bib = tmp_path / "refs.bib"
        bib.write_text(
            "@article{k1,\n  title = {Attention Is All You Need},\n  year={2017}\n}\n"
            "@article{k2,\n  title = {BERT: Pre-training},\n  year={2019}\n}\n"
        )
        titles = get_bib_titles(bib)
        assert "attention is all you need" in titles
        assert "bert: pre-training" in titles

    def test_missing_file(self, tmp_path):
        titles = get_bib_titles(tmp_path / "none.bib")
        assert titles == set()


class TestGenerateBibtex:
    def test_basic_entry(self):
        s = Suggestion(
            title="A Great Paper",
            authors=["Smith, John", "Doe, Jane"],
            year=2023,
            citation_count=100,
            doi="10.1234/test",
        )
        bib = generate_bibtex(s)
        assert "@article{" in bib
        assert "A Great Paper" in bib
        assert "2023" in bib
        assert "10.1234/test" in bib

    def test_arxiv_entry(self):
        s = Suggestion(
            title="Another Paper",
            authors=["Wang, Yu"],
            year=2024,
            citation_count=200,
            arxiv_id="2401.12345",
        )
        bib = generate_bibtex(s)
        assert "2401.12345" in bib
        assert "arXiv" in bib


class TestSuggest:
    def test_no_httpx_error(self, tmp_path):
        """If httpx missing, returns a helpful error."""
        tex = tmp_path / "paper.tex"
        tex.write_text(r"\title{Test}\section{Methods}")
        with (
            patch.dict("sys.modules", {"httpx": None}),
            patch("builtins.__import__", side_effect=_mock_import_no_httpx),
        ):
            result = suggest(tex)
        assert any("httpx" in e for e in result.errors)

    def test_file_not_found(self, tmp_path):
        result = suggest(tmp_path / "nonexistent.tex")
        assert result.errors

    def test_no_key_phrases(self, tmp_path):
        tex = tmp_path / "empty.tex"
        tex.write_text("No useful content here at all.")
        result = suggest(tex)
        # Should either find no phrases or handle gracefully
        assert isinstance(result.key_phrases, list)

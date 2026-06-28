"""Tests for the pack (arXiv submission packager) module."""

from __future__ import annotations

import tarfile

from papercheck.pack import (
    collect_bib_files,
    collect_bst_files,
    collect_images,
    flatten_tex,
    pack,
    strip_comments,
)


class TestStripComments:
    def test_removes_full_line_comment(self):
        text = "% This is a comment\nReal content\n"
        assert strip_comments(text) == "Real content\n"

    def test_removes_inline_comment(self):
        text = "Some text % inline comment\n"
        result = strip_comments(text)
        assert result == "Some text \n"

    def test_preserves_escaped_percent(self):
        text = r"Accuracy is 95\% on the test set." + "\n"
        result = strip_comments(text)
        assert r"95\%" in result

    def test_multiple_lines(self):
        text = "% header\nLine 1\nLine 2 % trailing\n% another\nLine 3\n"
        result = strip_comments(text)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
        assert "header" not in result
        assert "trailing" not in result
        assert "another" not in result


class TestFlattenTex:
    def test_resolves_input(self, tmp_path):
        (tmp_path / "main.tex").write_text(
            "\\documentclass{article}\n\\input{intro}\n\\end{document}\n"
        )
        (tmp_path / "intro.tex").write_text("Hello from intro.\n")
        result = flatten_tex(tmp_path / "main.tex")
        assert "Hello from intro." in result
        assert "\\input{intro}" not in result

    def test_nested_input(self, tmp_path):
        (tmp_path / "main.tex").write_text("Start\n\\input{a}\nEnd\n")
        (tmp_path / "a.tex").write_text("A content\n\\input{b}\n")
        (tmp_path / "b.tex").write_text("B content\n")
        result = flatten_tex(tmp_path / "main.tex")
        assert "A content" in result
        assert "B content" in result

    def test_circular_input_handled(self, tmp_path):
        (tmp_path / "main.tex").write_text("\\input{main}\n")
        result = flatten_tex(tmp_path / "main.tex")
        assert "circular" in result.lower()

    def test_missing_input_preserved(self, tmp_path):
        (tmp_path / "main.tex").write_text("\\input{nonexistent}\n")
        result = flatten_tex(tmp_path / "main.tex")
        assert "\\input{nonexistent}" in result


class TestCollectImages:
    def test_finds_referenced_images(self, tmp_path):
        (tmp_path / "fig1.png").write_bytes(b"PNG")
        tex = r"\includegraphics[width=0.5\linewidth]{fig1.png}"
        images = collect_images(tex, tmp_path)
        assert len(images) == 1
        assert images[0].name == "fig1.png"

    def test_tries_extensions(self, tmp_path):
        (tmp_path / "diagram.pdf").write_bytes(b"PDF")
        tex = r"\includegraphics{diagram}"
        images = collect_images(tex, tmp_path)
        assert len(images) == 1
        assert images[0].name == "diagram.pdf"

    def test_skips_missing(self, tmp_path):
        tex = r"\includegraphics{nofile.png}"
        images = collect_images(tex, tmp_path)
        assert images == []


class TestCollectBibFiles:
    def test_finds_bib(self, tmp_path):
        (tmp_path / "refs.bib").write_text("@article{key, title={T}}")
        tex = r"\bibliography{refs}"
        bibs = collect_bib_files(tex, tmp_path)
        assert any(b.name == "refs.bib" for b in bibs)

    def test_finds_bbl(self, tmp_path):
        (tmp_path / "paper.bbl").write_text("\\bibitem{x}")
        tex = "No bibliography command"
        bibs = collect_bib_files(tex, tmp_path)
        assert any(b.suffix == ".bbl" for b in bibs)


class TestCollectBstFiles:
    def test_finds_bst(self, tmp_path):
        (tmp_path / "plain.bst").write_text("ENTRY{}")
        tex = r"\bibliographystyle{plain}"
        bsts = collect_bst_files(tex, tmp_path)
        assert any(b.name == "plain.bst" for b in bsts)


class TestPack:
    def test_creates_archive(self, tmp_path):
        (tmp_path / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}\n"
        )
        output = tmp_path / "out.tar.gz"
        result = pack(tmp_path, output=output)
        assert result.ok
        assert output.exists()
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
            assert "main.tex" in names

    def test_strips_comments_in_archive(self, tmp_path):
        (tmp_path / "main.tex").write_text(
            "\\documentclass{article}\n% secret comment\n\\begin{document}\n"
            "Real content\n\\end{document}\n"
        )
        output = tmp_path / "out.tar.gz"
        result = pack(tmp_path, output=output)
        assert result.ok
        with tarfile.open(output, "r:gz") as tar:
            f = tar.extractfile("main.tex")
            content = f.read().decode()
            assert "secret comment" not in content
            assert "Real content" in content

    def test_includes_images(self, tmp_path):
        (tmp_path / "fig.png").write_bytes(b"PNGDATA" * 100)
        (tmp_path / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\n"
            "\\includegraphics{fig.png}\n\\end{document}\n"
        )
        output = tmp_path / "out.tar.gz"
        result = pack(tmp_path, output=output)
        assert result.ok
        assert any("fig.png" in name for name, _ in result.files)

    def test_error_on_missing_tex(self, tmp_path):
        result = pack(tmp_path)
        assert not result.ok
        assert any("Cannot find" in e for e in result.errors)

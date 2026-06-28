"""Tests for the watcher module (unit tests for helper functions)."""

from __future__ import annotations

from pathlib import Path

from papercheck.watcher import _collect_watched_files, _detect_changes


class TestCollectWatchedFiles:
    def test_collects_tex_files(self, tmp_path):
        (tmp_path / "main.tex").write_text("content")
        (tmp_path / "refs.bib").write_text("@article{a,}")
        (tmp_path / "readme.md").write_text("# readme")  # Not watched
        files = _collect_watched_files(tmp_path)
        extensions = {p.suffix for p in files}
        assert ".tex" in extensions
        assert ".bib" in extensions
        assert ".md" not in extensions

    def test_collects_images(self, tmp_path):
        (tmp_path / "fig.png").write_bytes(b"\x89PNG")
        (tmp_path / "fig.jpg").write_bytes(b"\xff\xd8")
        files = _collect_watched_files(tmp_path)
        extensions = {p.suffix for p in files}
        assert ".png" in extensions
        assert ".jpg" in extensions

    def test_handles_single_file(self, tmp_path):
        tex = tmp_path / "paper.tex"
        tex.write_text("content")
        files = _collect_watched_files(tex)
        assert tex in files

    def test_empty_dir(self, tmp_path):
        files = _collect_watched_files(tmp_path)
        assert len(files) == 0


class TestDetectChanges:
    def test_detects_modified(self, tmp_path):
        p = tmp_path / "a.tex"
        previous = {p: 1000.0}
        current = {p: 1001.0}
        changes = _detect_changes(previous, current)
        assert p in changes

    def test_detects_added(self, tmp_path):
        p = tmp_path / "new.tex"
        previous: dict[Path, float] = {}
        current = {p: 1000.0}
        changes = _detect_changes(previous, current)
        assert p in changes

    def test_detects_removed(self, tmp_path):
        p = tmp_path / "old.tex"
        previous = {p: 1000.0}
        current: dict[Path, float] = {}
        changes = _detect_changes(previous, current)
        assert p in changes

    def test_no_changes(self, tmp_path):
        p = tmp_path / "same.tex"
        previous = {p: 1000.0}
        current = {p: 1000.0}
        changes = _detect_changes(previous, current)
        assert len(changes) == 0

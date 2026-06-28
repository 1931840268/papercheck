"""Tests for config module."""

from __future__ import annotations

from textwrap import dedent

from papercheck.config import Config, find_config_file, load_config
from papercheck.models import Severity


class TestConfig:
    def test_default_config(self):
        cfg = Config()
        assert cfg.disabled_rules == []
        assert cfg.severity_overrides == {}
        assert cfg.anonymous is True
        assert cfg.venue == ""
        assert cfg.anon_patterns == []

    def test_is_rule_disabled(self):
        cfg = Config(disabled_rules=["TYPO001", "CONT008"])
        assert cfg.is_rule_disabled("TYPO001")
        assert cfg.is_rule_disabled("CONT008")
        assert not cfg.is_rule_disabled("REF001")


class TestFindConfigFile:
    def test_finds_config_in_dir(self, tmp_path):
        config_file = tmp_path / ".papercheckrc"
        config_file.write_text("anonymous = false\n")
        result = find_config_file(tmp_path)
        assert result == config_file

    def test_returns_none_when_missing(self, tmp_path, monkeypatch):
        # Isolate the search so it doesn't find real config files
        monkeypatch.setattr("papercheck.config.Path.home", staticmethod(lambda: tmp_path))
        subdir = tmp_path / "project"
        subdir.mkdir()
        result = find_config_file(subdir)
        assert result is None


class TestLoadConfig:
    def test_loads_basic_config(self, tmp_path):
        config_file = tmp_path / ".papercheckrc"
        config_file.write_text(dedent("""\
            disable = ["TYPO001", "CONT008"]
            anonymous = false
            venue = "neurips"
            anon_patterns = ["My Lab"]

            [severity_overrides]
            TYPO003 = "error"
        """))
        cfg = load_config(tmp_path)
        assert cfg.disabled_rules == ["TYPO001", "CONT008"]
        assert cfg.anonymous is False
        assert cfg.venue == "neurips"
        assert cfg.anon_patterns == ["My Lab"]
        assert cfg.severity_overrides == {"TYPO003": Severity.ERROR}

    def test_returns_defaults_on_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("papercheck.config.Path.home", staticmethod(lambda: tmp_path))
        subdir = tmp_path / "project"
        subdir.mkdir()
        cfg = load_config(subdir)
        assert cfg.anonymous is True
        assert cfg.disabled_rules == []

    def test_handles_malformed_gracefully(self, tmp_path):
        config_file = tmp_path / ".papercheckrc"
        config_file.write_text("not valid = [[[toml content\n\x00\x01")
        cfg = load_config(tmp_path)
        assert cfg.anonymous is True  # Falls back to defaults

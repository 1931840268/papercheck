"""Configuration file support for papercheck.

Loads settings from a `.papercheckrc` file in TOML format.

Example .papercheckrc
---------------------

    # Disable specific rules by code
    disable = ["TYPO001", "CONT008"]

    # Enable anonymous mode (default: true)
    anonymous = true

    # Target venue for venue-specific checks
    venue = "neurips"

    # Custom patterns to flag in anonymity checks
    anon_patterns = ["John Smith", "MIT Lab"]

    # Override severity for specific rules
    [severity_overrides]
    TYPO003 = "error"
    REF002 = "info"

The file is searched starting from the project directory upwards
through parent directories, stopping at the user's home directory.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from papercheck.models import Severity

if sys.version_info >= (3, 11):
    import tomllib
else:
    tomllib = None

logger = logging.getLogger(__name__)

_CONFIG_FILENAME = ".papercheckrc"


@dataclass
class Config:
    """Papercheck configuration loaded from .papercheckrc."""

    disabled_rules: list[str] = field(default_factory=list)
    severity_overrides: dict[str, Severity] = field(default_factory=dict)
    anonymous: bool = True
    venue: str = ""
    anon_patterns: list[str] = field(default_factory=list)

    def is_rule_disabled(self, code: str) -> bool:
        """Check if a rule is disabled."""
        return code in self.disabled_rules


def find_config_file(start_dir: Path) -> Path | None:
    """Find .papercheckrc walking up from start_dir to home directory.

    Returns the path to the first config file found, or None.
    """
    start_dir = start_dir.resolve()
    home = Path.home().resolve()
    current = start_dir

    while True:
        candidate = current / _CONFIG_FILENAME
        if candidate.is_file():
            return candidate

        # Stop if we've reached home or filesystem root
        if current == home or current.parent == current:
            break
        # Also stop if we've gone above home (safety bound)
        try:
            current.relative_to(home)
        except ValueError:
            break
        current = current.parent

    # Check home itself if we haven't already
    home_candidate = home / _CONFIG_FILENAME
    if home_candidate.is_file() and home_candidate != start_dir / _CONFIG_FILENAME:
        return home_candidate

    return None


def _parse_toml_fallback(text: str) -> dict:
    """Minimal TOML parser for Python 3.10 (no tomllib).

    Supports: bare keys, string/bool/list-of-strings values, and [sections].
    This is intentionally limited to the subset used by .papercheckrc.
    """
    import re

    result: dict = {}
    current_section: dict = result

    for raw_line in text.splitlines():
        line = raw_line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Section header
        section_match = re.match(r"^\[([a-zA-Z_][a-zA-Z0-9_]*)\]$", line)
        if section_match:
            section_name = section_match.group(1)
            result.setdefault(section_name, {})
            current_section = result[section_name]
            continue

        # Key = value
        kv_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$', line)
        if not kv_match:
            continue

        key = kv_match.group(1)
        val_str = kv_match.group(2).strip()

        # Parse value
        current_section[key] = _parse_toml_value(val_str)

    return result


def _parse_toml_value(val_str: str):
    """Parse a single TOML value (string, bool, or list of strings)."""
    import re

    # Boolean
    if val_str == "true":
        return True
    if val_str == "false":
        return False

    # Quoted string
    if (val_str.startswith('"') and val_str.endswith('"')) or (
        val_str.startswith("'") and val_str.endswith("'")
    ):
        return val_str[1:-1]

    # Array of strings
    if val_str.startswith("[") and val_str.endswith("]"):
        inner = val_str[1:-1].strip()
        if not inner:
            return []
        items = re.findall(r'"([^"]*)"', inner)
        if not items:
            items = re.findall(r"'([^']*)'", inner)
        return items

    # Unquoted string (bare value)
    return val_str


def _read_toml(path: Path) -> dict:
    """Read and parse a TOML file, using tomllib on 3.11+ with fallback."""
    text = path.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)
    return _parse_toml_fallback(text)


def _parse_severity(value: str) -> Severity | None:
    """Convert a string to Severity enum, or None if invalid."""
    try:
        return Severity(value.lower())
    except ValueError:
        return None


def _build_config(data: dict) -> Config:
    """Build a Config dataclass from parsed TOML data."""
    disabled = data.get("disable", [])
    if isinstance(disabled, str):
        disabled = [disabled]

    anonymous = data.get("anonymous", True)
    if not isinstance(anonymous, bool):
        anonymous = True

    venue = data.get("venue", "")
    if not isinstance(venue, str):
        venue = ""

    anon_patterns = data.get("anon_patterns", [])
    if isinstance(anon_patterns, str):
        anon_patterns = [anon_patterns]

    # Parse severity overrides
    raw_overrides = data.get("severity_overrides", {})
    severity_overrides: dict[str, Severity] = {}
    if isinstance(raw_overrides, dict):
        for code, sev_str in raw_overrides.items():
            if isinstance(sev_str, str):
                parsed = _parse_severity(sev_str)
                if parsed is not None:
                    severity_overrides[code] = parsed

    return Config(
        disabled_rules=[str(r) for r in disabled],
        severity_overrides=severity_overrides,
        anonymous=anonymous,
        venue=venue,
        anon_patterns=[str(p) for p in anon_patterns],
    )


def load_config(project_dir: Path) -> Config:
    """Load configuration from .papercheckrc file.

    Searches from project_dir upwards to home directory.
    Returns a Config with defaults if no file is found or parsing fails.
    """
    config_path = find_config_file(project_dir)
    if config_path is None:
        return Config()

    try:
        data = _read_toml(config_path)
    except Exception:
        logger.warning("Failed to parse config at %s, using defaults", config_path)
        return Config()

    # Support both flat format and [papercheck] section
    if "papercheck" in data and isinstance(data["papercheck"], dict):
        data = data["papercheck"]

    return _build_config(data)

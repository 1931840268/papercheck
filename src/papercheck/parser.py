"""LaTeX parser — extract structural information from .tex files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from papercheck.models import TexProject


@dataclass
class ParsedTex:
    """Structural information extracted from LaTeX source."""

    # Citations: \cite{key}, \citep{key}, \citet{key}, etc.
    citations: dict[str, list[int]] = field(default_factory=dict)  # key -> [line numbers]

    # Labels: \label{key}
    labels: dict[str, int] = field(default_factory=dict)  # key -> line number

    # References: \ref{key}, \eqref{key}, \autoref{key}, \cref{key}
    refs: dict[str, list[int]] = field(default_factory=dict)  # key -> [line numbers]

    # Figures: \includegraphics paths
    graphics: dict[str, int] = field(default_factory=dict)  # path -> line number

    # Environments: figure, table, equation, etc.
    environments: list[tuple[str, int, int]] = field(default_factory=list)  # (name, start, end)

    # Sections
    sections: list[tuple[str, str, int]] = field(default_factory=list)  # (level, title, line)

    # Math delimiters
    inline_math: list[tuple[int, int, int]] = field(default_factory=list)  # (line, start, end)

    # Raw lines (for content checks)
    lines: list[str] = field(default_factory=list)


# Regex patterns
_CITE_RE = re.compile(r"\\(?:cite[tp]?|citealp|citeauthor|citeyear)\{([^}]+)\}")
_LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
_REF_RE = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref|pageref)\{([^}]+)\}")
_GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
_BEGIN_RE = re.compile(r"\\begin\{(\w+)\}")
_END_RE = re.compile(r"\\end\{(\w+)\}")
_SECTION_RE = re.compile(r"\\(section|subsection|subsubsection|chapter|paragraph)\*?\{([^}]+)\}")
_INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
_BIB_KEY_RE = re.compile(r"@\w+\{([^,\s]+),")


def load_project(path: Path) -> TexProject:
    """Load a LaTeX project from a directory or single .tex file."""
    if path.is_file():
        root = path.parent
        main_file = path.name
        single_file_mode = True
    else:
        root = path
        # Find main file (the one with \documentclass)
        main_file = _find_main_file(root)
        single_file_mode = False

    project = TexProject(root=root, main_file=main_file)

    if single_file_mode:
        # Only load the specified file + .bib files in same directory
        project.tex_files[main_file] = path.read_text(encoding="utf-8", errors="replace")
        for bib_path in root.glob("*.bib"):
            rel = str(bib_path.relative_to(root))
            project.bib_files[rel] = bib_path.read_text(encoding="utf-8", errors="replace")
        # Also load \input'd files
        content = project.tex_files[main_file]
        for match in _INPUT_RE.finditer(content):
            input_name = match.group(1)
            if not input_name.endswith(".tex"):
                input_name += ".tex"
            input_path = root / input_name
            if input_path.exists():
                project.tex_files[input_name] = input_path.read_text(
                    encoding="utf-8", errors="replace"
                )
    else:
        # Load all .tex files in project
        for tex_path in root.rglob("*.tex"):
            rel = str(tex_path.relative_to(root))
            project.tex_files[rel] = tex_path.read_text(encoding="utf-8", errors="replace")
        for bib_path in root.rglob("*.bib"):
            rel = str(bib_path.relative_to(root))
            project.bib_files[rel] = bib_path.read_text(encoding="utf-8", errors="replace")

    # Collect image files
    img_extensions = {".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg"}
    for img_path in root.rglob("*"):
        if img_path.suffix.lower() in img_extensions and "node_modules" not in str(img_path):
            project.image_files.append(str(img_path.relative_to(root)))

    return project


def parse_tex(content: str) -> ParsedTex:
    """Parse a single .tex file content into structured data."""
    result = ParsedTex()
    result.lines = content.splitlines()
    env_stack: list[tuple[str, int]] = []

    for lineno, line in enumerate(result.lines, 1):
        # Skip comments
        stripped = _strip_comment(line)

        # Citations
        for match in _CITE_RE.finditer(stripped):
            keys = [k.strip() for k in match.group(1).split(",")]
            for key in keys:
                result.citations.setdefault(key, []).append(lineno)

        # Labels
        for match in _LABEL_RE.finditer(stripped):
            result.labels[match.group(1)] = lineno

        # References
        for match in _REF_RE.finditer(stripped):
            result.refs.setdefault(match.group(1), []).append(lineno)

        # Graphics
        for match in _GRAPHICS_RE.finditer(stripped):
            result.graphics[match.group(1)] = lineno

        # Environments
        for match in _BEGIN_RE.finditer(stripped):
            env_stack.append((match.group(1), lineno))
        for match in _END_RE.finditer(stripped):
            env_name = match.group(1)
            # Pop matching begin
            for i in range(len(env_stack) - 1, -1, -1):
                if env_stack[i][0] == env_name:
                    start_line = env_stack[i][1]
                    env_stack.pop(i)
                    result.environments.append((env_name, start_line, lineno))
                    break

        # Sections
        for match in _SECTION_RE.finditer(stripped):
            result.sections.append((match.group(1), match.group(2), lineno))

    return result


def parse_bib_keys(content: str) -> set[str]:
    """Extract all entry keys from a .bib file."""
    return set(_BIB_KEY_RE.findall(content))


def _find_main_file(root: Path) -> str:
    """Find the main .tex file (contains \\documentclass)."""
    for tex_path in root.rglob("*.tex"):
        content = tex_path.read_text(encoding="utf-8", errors="replace")
        if "\\documentclass" in content:
            return str(tex_path.relative_to(root))
    # Fallback: first .tex file found
    for tex_path in root.rglob("*.tex"):
        return str(tex_path.relative_to(root))
    return "main.tex"


def _strip_comment(line: str) -> str:
    """Remove LaTeX comment (% not preceded by \\)."""
    i = 0
    while i < len(line):
        if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
            return line[:i]
        i += 1
    return line

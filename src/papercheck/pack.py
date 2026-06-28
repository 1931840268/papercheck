"""arXiv submission packager — flatten, strip, and archive a LaTeX project."""

from __future__ import annotations

import re
import tarfile
from io import BytesIO
from pathlib import Path

MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

_INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
_GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
_BIB_RE = re.compile(r"\\bibliography\{([^}]+)\}")
_BIBSTYLE_RE = re.compile(r"\\bibliographystyle\{([^}]+)\}")

# Common image extensions to try when the tex omits the extension
_IMG_EXTENSIONS = (
    ".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".tiff", ".tif",
)


def strip_comments(text: str) -> str:
    """Remove LaTeX comments while preserving escaped percent signs."""
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        # Remove full-line comments
        stripped = line.lstrip()
        if stripped.startswith("%"):
            continue
        # Remove inline comments: find % not preceded by \
        result: list[str] = []
        i = 0
        while i < len(line):
            if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
                # Rest is comment, keep the newline if present
                if line.endswith("\n"):
                    result.append("\n")
                break
            result.append(line[i])
            i += 1
        lines.append("".join(result))
    return "".join(lines)


def _resolve_tex_path(base_dir: Path, name: str) -> Path | None:
    """Resolve a \\input/\\include argument to an actual file path."""
    candidate = base_dir / name
    if candidate.exists():
        return candidate
    if not candidate.suffix:
        candidate = candidate.with_suffix(".tex")
        if candidate.exists():
            return candidate
    return None


def flatten_tex(main_file: Path, _seen: set[Path] | None = None) -> str:
    """Recursively flatten \\input and \\include into a single string."""
    if _seen is None:
        _seen = set()

    resolved = main_file.resolve()
    if resolved in _seen:
        return (
            f"% [papercheck: circular input skipped: {main_file.name}]\n"
        )
    _seen.add(resolved)

    text = main_file.read_text(encoding="utf-8")
    base_dir = main_file.parent

    def _replace(m: re.Match) -> str:
        target = _resolve_tex_path(base_dir, m.group(1))
        if target is None:
            return m.group(0)  # keep original if not found
        return flatten_tex(target, _seen)

    return _INPUT_RE.sub(_replace, text)


def _resolve_image(base_dir: Path, ref: str) -> Path | None:
    """Find the actual image file, trying common extensions if needed."""
    candidate = base_dir / ref
    if candidate.exists() and candidate.is_file():
        return candidate
    # Try adding extensions
    for ext in _IMG_EXTENSIONS:
        attempt = base_dir / (ref + ext)
        if attempt.exists() and attempt.is_file():
            return attempt
    # Try with graphicspath-style subdirectories
    for subdir in ("figures", "figs", "images", "img"):
        for ext in ("", *_IMG_EXTENSIONS):
            attempt = base_dir / subdir / (ref + ext)
            if attempt.exists() and attempt.is_file():
                return attempt
    return None


def collect_images(flat_tex: str, base_dir: Path) -> list[Path]:
    """Extract all image paths referenced via \\includegraphics."""
    refs = _GRAPHICS_RE.findall(flat_tex)
    images: list[Path] = []
    seen: set[Path] = set()
    for ref in refs:
        img = _resolve_image(base_dir, ref)
        if img and img.resolve() not in seen:
            seen.add(img.resolve())
            images.append(img)
    return images


def collect_bib_files(flat_tex: str, base_dir: Path) -> list[Path]:
    """Collect .bib files referenced in the document."""
    bibs: list[Path] = []
    seen: set[Path] = set()
    for m in _BIB_RE.finditer(flat_tex):
        for name in m.group(1).split(","):
            name = name.strip()
            candidate = base_dir / name
            if not candidate.suffix:
                candidate = candidate.with_suffix(".bib")
            if candidate.exists() and candidate.resolve() not in seen:
                seen.add(candidate.resolve())
                bibs.append(candidate)
    # Also look for any .bbl file (pre-compiled bibliography)
    for bbl in base_dir.glob("*.bbl"):
        if bbl.resolve() not in seen:
            seen.add(bbl.resolve())
            bibs.append(bbl)
    return bibs


def collect_bst_files(flat_tex: str, base_dir: Path) -> list[Path]:
    """Collect .bst files referenced in the document."""
    bsts: list[Path] = []
    seen: set[Path] = set()
    for m in _BIBSTYLE_RE.finditer(flat_tex):
        name = m.group(1).strip()
        candidate = base_dir / name
        if not candidate.suffix:
            candidate = candidate.with_suffix(".bst")
        if candidate.exists() and candidate.resolve() not in seen:
            seen.add(candidate.resolve())
            bsts.append(candidate)
    return bsts


class PackResult:
    """Result of a pack operation."""

    def __init__(self) -> None:
        self.files: list[tuple[str, int]] = []  # (archive_name, size)
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.output_path: Path | None = None

    @property
    def total_size(self) -> int:
        return sum(s for _, s in self.files)

    @property
    def ok(self) -> bool:
        return not self.errors


def pack(
    project_dir: Path,
    output: Path | None = None,
    main_tex: str | None = None,
) -> PackResult:
    """Package a LaTeX project into an arXiv-ready .tar.gz archive.

    Args:
        project_dir: Directory containing the LaTeX project.
        output: Output .tar.gz path. Defaults to project_dir/submission.tar.gz.
        main_tex: Name of the main .tex file. Auto-detected if None.
    """
    result = PackResult()
    project_dir = Path(project_dir).resolve()

    if not project_dir.is_dir():
        result.errors.append(f"Not a directory: {project_dir}")
        return result

    # Find main tex file
    main_path = (
        project_dir / main_tex if main_tex else _find_main_tex(project_dir)
    )

    if main_path is None or not main_path.exists():
        result.errors.append(
            "Cannot find main .tex file (with \\documentclass)."
        )
        return result

    # Flatten and strip
    flat_content = flatten_tex(main_path)
    stripped_content = strip_comments(flat_content)

    # Collect assets
    images = collect_images(stripped_content, project_dir)
    bibs = collect_bib_files(stripped_content, project_dir)
    bsts = collect_bst_files(stripped_content, project_dir)

    # Also collect any .cls or .sty files in the project
    style_files = (
        list(project_dir.glob("*.cls"))
        + list(project_dir.glob("*.sty"))
    )

    # Build archive
    if output is None:
        output = project_dir / "submission.tar.gz"

    # Check sizes before writing
    tex_bytes = stripped_content.encode("utf-8")
    all_extra_files = images + bibs + bsts + style_files

    if len(tex_bytes) > MAX_FILE_SIZE:
        result.errors.append(
            f"Flattened .tex exceeds 15 MB"
            f" ({len(tex_bytes) / 1024 / 1024:.1f} MB)"
        )
        return result

    total = len(tex_bytes)
    for f in all_extra_files:
        size = f.stat().st_size
        if size > MAX_FILE_SIZE:
            result.errors.append(
                f"File exceeds 15 MB: {f.name}"
                f" ({size / 1024 / 1024:.1f} MB)"
            )
        total += size

    if total > MAX_TOTAL_SIZE:
        result.errors.append(
            f"Total size exceeds 50 MB limit"
            f" ({total / 1024 / 1024:.1f} MB)"
        )
        return result

    if result.errors:
        return result

    # Create archive
    with tarfile.open(output, "w:gz") as tar:
        # Add flattened tex as main.tex
        info = tarfile.TarInfo(name="main.tex")
        info.size = len(tex_bytes)
        tar.addfile(info, BytesIO(tex_bytes))
        result.files.append(("main.tex", len(tex_bytes)))

        added: set[str] = {"main.tex"}
        for f in all_extra_files:
            arcname = f.name
            # Handle duplicate names by prefixing directory
            if arcname in added:
                arcname = f"{f.parent.name}/{arcname}"
            if arcname in added:
                continue
            added.add(arcname)
            tar.add(str(f), arcname=arcname)
            result.files.append((arcname, f.stat().st_size))

    result.output_path = output
    return result


def _find_main_tex(project_dir: Path) -> Path | None:
    """Find the main .tex file by looking for \\documentclass."""
    tex_files = list(project_dir.glob("*.tex"))
    for tf in tex_files:
        try:
            content = tf.read_text(encoding="utf-8", errors="ignore")
            if "\\documentclass" in content:
                return tf
        except OSError:
            continue
    # Fallback: return first .tex file
    return tex_files[0] if tex_files else None

"""PDF validation — check fonts, metadata, pages, and image resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Venue page limits (main content, excluding references/appendix)
VENUE_LIMITS: dict[str, int] = {
    "neurips": 9,
    "icml": 8,
    "iclr": 10,
    "aaai": 7,
    "cvpr": 8,
    "eccv": 14,
    "acl": 8,
    "emnlp": 8,
    "naacl": 8,
    "sigchi": 10,
}

# Metadata fields that may reveal author identity
_IDENTITY_FIELDS = (
    "Author",
    "Creator",
    "Producer",
    "Company",
    "ModDate",
    "CreationDate",
)


@dataclass
class PDFIssue:
    """A single issue found in the PDF."""

    severity: str  # "error", "warning", "info"
    message: str


@dataclass
class PDFCheckResult:
    """Result of PDF validation."""

    path: Path
    pages: int = 0
    pdf_version: str = ""
    fonts_embedded: bool = True
    unembedded_fonts: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    issues: list[PDFIssue] = field(default_factory=list)
    has_pymupdf: bool = False

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)


def check_pdf(
    pdf_path: Path,
    venue: str | None = None,
    max_pages: int | None = None,
    min_dpi: int = 150,
) -> PDFCheckResult:
    """Validate a PDF file for submission readiness.

    Args:
        pdf_path: Path to the PDF file.
        venue: Optional venue name for page limit checking.
        max_pages: Explicit page limit (overrides venue).
        min_dpi: Minimum acceptable image DPI (default 150).
    """
    pdf_path = Path(pdf_path).resolve()
    result = PDFCheckResult(path=pdf_path)

    if not pdf_path.exists():
        result.issues.append(
            PDFIssue("error", f"File not found: {pdf_path}")
        )
        return result

    if pdf_path.suffix.lower() != ".pdf":
        result.issues.append(PDFIssue("error", "File is not a PDF"))
        return result

    try:
        import fitz  # noqa: F401

        result.has_pymupdf = True
        return _check_with_pymupdf(
            pdf_path, result, venue, max_pages, min_dpi
        )
    except ImportError:
        return _check_basic(pdf_path, result, venue, max_pages)


def _check_basic(
    pdf_path: Path,
    result: PDFCheckResult,
    venue: str | None,
    max_pages: int | None,
) -> PDFCheckResult:
    """Basic PDF checks without PyMuPDF — reads raw bytes."""
    result.issues.append(
        PDFIssue(
            "info",
            "PyMuPDF not installed. Install with: "
            "pip install papercheck[pdf]  "
            "for full PDF analysis "
            "(font embedding, DPI checks, detailed metadata).",
        )
    )

    try:
        with open(pdf_path, "rb") as f:
            header = f.read(1024)
            # Check PDF version from header
            if header[:5] == b"%PDF-":
                version_end = (
                    header.index(b"\n")
                    if b"\n" in header[:20]
                    else 8
                )
                result.pdf_version = (
                    header[5:version_end]
                    .decode("ascii", errors="ignore")
                    .strip()
                )

            # Count pages approximately
            f.seek(0)
            content = f.read()

        # Count page objects (rough heuristic)
        page_count = content.count(b"/Type /Page") - content.count(
            b"/Type /Pages"
        )
        if page_count <= 0:
            # Fallback: count page tree leaves
            page_count = content.count(b"/Type/Page") - content.count(
                b"/Type/Pages"
            )
        result.pages = max(page_count, 0)

        _check_page_limit(result, venue, max_pages)

    except OSError as e:
        result.issues.append(PDFIssue("error", f"Cannot read PDF: {e}"))

    return result


def _check_with_pymupdf(
    pdf_path: Path,
    result: PDFCheckResult,
    venue: str | None,
    max_pages: int | None,
    min_dpi: int,
) -> PDFCheckResult:
    """Full PDF analysis using PyMuPDF."""
    import fitz

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        result.issues.append(
            PDFIssue("error", f"Cannot open PDF: {e}")
        )
        return result

    # Basic info
    result.pages = len(doc)
    metadata = doc.metadata or {}
    result.pdf_version = metadata.get("format", "").replace("PDF ", "")

    # Metadata identity leak check
    for key in _IDENTITY_FIELDS:
        val = metadata.get(key.lower(), "") or metadata.get(key, "")
        if val:
            result.metadata[key] = val

    if result.metadata:
        identity_fields = [
            k
            for k in result.metadata
            if k in ("Author", "Creator", "Company")
        ]
        if identity_fields:
            result.issues.append(
                PDFIssue(
                    "warning",
                    "PDF metadata may reveal identity: "
                    f"{', '.join(identity_fields)}. "
                    "Consider clearing metadata before submission.",
                )
            )

    # Font embedding check
    unembedded: set[str] = set()
    for page_num in range(len(doc)):
        page = doc[page_num]
        fonts = page.get_fonts(full=True)
        for font_info in fonts:
            # font_info: (xref, ext, type, basefont, name, encoding, ...)
            font_type = (
                font_info[2] if len(font_info) > 2 else ""
            )
            font_name = (
                font_info[3] if len(font_info) > 3 else ""
            )
            # Type3 fonts are always embedded; check others
            if font_type and font_type.lower() not in ("type3",):
                # If ext field is empty, font might not be embedded
                ext = font_info[1] if len(font_info) > 1 else ""
                if not ext:
                    unembedded.add(font_name)

    if unembedded:
        result.fonts_embedded = False
        result.unembedded_fonts = sorted(unembedded)
        result.issues.append(
            PDFIssue(
                "error",
                "Fonts not embedded: "
                f"{', '.join(result.unembedded_fonts)}. "
                "arXiv requires all fonts to be embedded.",
            )
        )

    # Image DPI check
    low_dpi_images: list[str] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            try:
                img = doc.extract_image(xref)
                width = img.get("width", 0)
                height = img.get("height", 0)
                if width > 0 and height > 0:
                    # Estimate DPI from page dimensions
                    page_rect = page.rect
                    page_width_in = page_rect.width / 72
                    if page_width_in > 0:
                        effective_dpi = width / page_width_in
                        if effective_dpi < min_dpi:
                            low_dpi_images.append(
                                f"page {page_num + 1}:"
                                f" ~{effective_dpi:.0f} DPI"
                            )
            except Exception:
                continue

    if low_dpi_images:
        suffix = (
            f" (+{len(low_dpi_images) - 5} more)"
            if len(low_dpi_images) > 5
            else ""
        )
        result.issues.append(
            PDFIssue(
                "warning",
                f"Low resolution images (< {min_dpi} DPI): "
                + "; ".join(low_dpi_images[:5])
                + suffix,
            )
        )

    # PDF version check
    if result.pdf_version:
        try:
            ver = float(result.pdf_version.split("-")[0])
            if ver > 2.0:
                result.issues.append(
                    PDFIssue(
                        "warning",
                        f"PDF version {result.pdf_version} "
                        "may not be supported.",
                    )
                )
        except ValueError:
            pass

    _check_page_limit(result, venue, max_pages)
    doc.close()
    return result


def _check_page_limit(
    result: PDFCheckResult,
    venue: str | None,
    max_pages: int | None,
) -> None:
    """Check page count against venue or explicit limit."""
    limit = max_pages
    if limit is None and venue:
        limit = VENUE_LIMITS.get(venue.lower())
        if limit is None:
            result.issues.append(
                PDFIssue(
                    "info",
                    f"Unknown venue '{venue}'. "
                    f"Known: {', '.join(VENUE_LIMITS)}",
                )
            )
            return

    if limit and result.pages > limit:
        label = f" ({venue})" if venue else ""
        result.issues.append(
            PDFIssue(
                "warning",
                f"Page count ({result.pages}) exceeds "
                f"limit of {limit}{label}. "
                "Note: this counts total pages "
                "including references/appendix.",
            )
        )

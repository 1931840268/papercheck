"""Citation suggestion engine — find missing highly-cited papers for your bibliography."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

_SECTION_RE = re.compile(r"\\(?:section|subsection)\*?\{([^}]+)\}")
_BOLD_RE = re.compile(r"\\textbf\{([^}]+)\}")
_TITLE_RE = re.compile(r"\\title\{([^}]+)\}")
_ABSTRACT_BEGIN = re.compile(r"\\begin\{abstract\}")
_ABSTRACT_END = re.compile(r"\\end\{abstract\}")
_CITE_RE = re.compile(r"\\cite[tp]?\*?\{([^}]+)\}")

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_SEARCH_URL = f"{S2_API_BASE}/paper/search"
S2_FIELDS = "title,authors,year,citationCount,externalIds,abstract"


@dataclass
class Suggestion:
    """A citation suggestion."""

    title: str
    authors: list[str]
    year: int | None
    citation_count: int
    doi: str | None = None
    arxiv_id: str | None = None
    reason: str = ""
    bibtex: str | None = None

    @property
    def author_str(self) -> str:
        if not self.authors:
            return "Unknown"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."


@dataclass
class SuggestResult:
    """Result of citation suggestion analysis."""

    key_phrases: list[str] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    existing_keys: set[str] = field(default_factory=set)


def extract_key_phrases(tex_content: str, max_phrases: int = 10) -> list[str]:
    """Extract key phrases from LaTeX content for citation search.

    Sources: title, section headings, abstract keywords, bold terms.
    """
    phrases: list[str] = []

    # Title
    for m in _TITLE_RE.finditer(tex_content):
        title = _clean_tex(m.group(1))
        if title:
            phrases.append(title)

    # Abstract content (extract key noun phrases)
    abstract = _extract_abstract(tex_content)
    if abstract:
        # Take first ~200 chars of abstract as a query phrase
        cleaned = _clean_tex(abstract)[:200].strip()
        if cleaned:
            phrases.append(cleaned)

    # Section headings
    for m in _SECTION_RE.finditer(tex_content):
        heading = _clean_tex(m.group(1))
        if heading and heading.lower() not in (
            "introduction",
            "conclusion",
            "conclusions",
            "references",
            "acknowledgments",
            "acknowledgements",
            "appendix",
            "related work",
        ):
            phrases.append(heading)

    # Bold terms (often key concepts)
    bold_terms: list[str] = []
    for m in _BOLD_RE.finditer(tex_content):
        term = _clean_tex(m.group(1))
        if term and len(term.split()) <= 5:
            bold_terms.append(term)
    # Take most common bold terms
    if bold_terms:
        from collections import Counter

        common = Counter(bold_terms).most_common(5)
        phrases.extend(term for term, _ in common)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for p in phrases:
        low = p.lower()
        if low not in seen and len(p) > 3:
            seen.add(low)
            unique.append(p)

    return unique[:max_phrases]


def get_existing_cite_keys(tex_content: str) -> set[str]:
    """Extract all citation keys used in the document."""
    keys: set[str] = set()
    for m in _CITE_RE.finditer(tex_content):
        for key in m.group(1).split(","):
            keys.add(key.strip())
    return keys


def get_bib_titles(bib_path: Path) -> set[str]:
    """Extract paper titles from a .bib file for deduplication."""
    titles: set[str] = set()
    if not bib_path.exists():
        return titles
    content = bib_path.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(
        r"title\s*=\s*\{([^}]+)\}", content, re.IGNORECASE
    ):
        titles.add(m.group(1).lower().strip())
    return titles


def query_semantic_scholar(
    phrase: str,
    min_citations: int = 50,
    limit: int = 10,
) -> list[dict]:
    """Query Semantic Scholar API for papers matching a phrase.

    Returns raw paper dicts from S2 API.
    """
    try:
        import httpx
    except ImportError:
        return []

    params = {
        "query": phrase,
        "fields": S2_FIELDS,
        "limit": str(limit),
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(S2_SEARCH_URL, params=params)
            if resp.status_code == 429:
                # Rate limited, wait and retry once
                time.sleep(2.0)
                resp = client.get(S2_SEARCH_URL, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
    except Exception:
        return []

    papers = data.get("data", [])
    # Filter by citation count
    return [
        p for p in papers if (p.get("citationCount") or 0) >= min_citations
    ]


def _paper_to_suggestion(paper: dict, reason: str) -> Suggestion:
    """Convert S2 API paper dict to a Suggestion."""
    authors = [
        a.get("name", "") for a in (paper.get("authors") or [])
    ]
    ext_ids = paper.get("externalIds") or {}
    return Suggestion(
        title=paper.get("title", "Unknown"),
        authors=authors,
        year=paper.get("year"),
        citation_count=paper.get("citationCount", 0),
        doi=ext_ids.get("DOI"),
        arxiv_id=ext_ids.get("ArXiv"),
        reason=reason,
    )


def generate_bibtex(s: Suggestion) -> str:
    """Generate a BibTeX entry for a suggestion."""
    # Create a citation key
    first_author = (
        s.authors[0].split()[-1] if s.authors else "unknown"
    )
    year = s.year or "XXXX"
    key = f"{first_author.lower()}{year}"

    authors_str = (
        " and ".join(s.authors) if s.authors else "Unknown"
    )

    lines = [f"@article{{{key},"]
    lines.append(f"  title = {{{s.title}}},")
    lines.append(f"  author = {{{authors_str}}},")
    lines.append(f"  year = {{{year}}},")
    if s.doi:
        lines.append(f"  doi = {{{s.doi}}},")
    if s.arxiv_id:
        lines.append(f"  eprint = {{{s.arxiv_id}}},")
        lines.append("  archivePrefix = {arXiv},")
    lines.append("}")
    return "\n".join(lines)


def suggest(
    tex_path: Path,
    bib_path: Path | None = None,
    min_citations: int = 50,
    max_suggestions: int = 10,
    include_bibtex: bool = False,
) -> SuggestResult:
    """Find citation suggestions for a LaTeX document.

    Args:
        tex_path: Path to the main .tex file.
        bib_path: Path to .bib file for deduplication.
            Auto-detected if None.
        min_citations: Minimum citation count for suggestions.
        max_suggestions: Maximum number of suggestions to return.
        include_bibtex: Generate BibTeX entries for suggestions.
    """
    result = SuggestResult()
    tex_path = Path(tex_path).resolve()

    if not tex_path.exists():
        result.errors.append(f"File not found: {tex_path}")
        return result

    try:
        import httpx  # noqa: F401
    except ImportError:
        result.errors.append(
            "httpx not installed. Install with: "
            "pip install papercheck[suggest] or pip install httpx"
        )
        return result

    content = tex_path.read_text(encoding="utf-8", errors="ignore")

    # Extract phrases
    result.key_phrases = extract_key_phrases(content)
    if not result.key_phrases:
        result.errors.append(
            "Could not extract key phrases from the document."
        )
        return result

    # Get existing citations for dedup
    result.existing_keys = get_existing_cite_keys(content)

    # Find bib file for title-based dedup
    existing_titles: set[str] = set()
    if bib_path is None:
        # Auto-detect
        bib_candidates = list(tex_path.parent.glob("*.bib"))
        if bib_candidates:
            bib_path = bib_candidates[0]
    if bib_path and bib_path.exists():
        existing_titles = get_bib_titles(bib_path)

    # Query S2 for each phrase
    all_suggestions: dict[str, Suggestion] = {}
    for phrase in result.key_phrases:
        papers = query_semantic_scholar(
            phrase, min_citations=min_citations
        )
        for paper in papers:
            title = paper.get("title", "")
            title_lower = title.lower().strip()
            # Skip if already cited
            if title_lower in existing_titles:
                continue
            if title_lower not in all_suggestions:
                s = _paper_to_suggestion(
                    paper, f"Related to: {phrase[:60]}"
                )
                all_suggestions[title_lower] = s
        # Small delay to be nice to S2 API
        time.sleep(0.5)

    # Rank by citation count
    ranked = sorted(
        all_suggestions.values(),
        key=lambda s: s.citation_count,
        reverse=True,
    )
    result.suggestions = ranked[:max_suggestions]

    # Generate BibTeX if requested
    if include_bibtex:
        for s in result.suggestions:
            s.bibtex = generate_bibtex(s)

    return result


def _extract_abstract(tex: str) -> str:
    """Extract abstract text from LaTeX source."""
    begin = _ABSTRACT_BEGIN.search(tex)
    if not begin:
        return ""
    end = _ABSTRACT_END.search(tex, begin.end())
    if not end:
        return ""
    return tex[begin.end():end.start()]


def _clean_tex(text: str) -> str:
    """Remove LaTeX commands from text, leaving plain words."""
    # Remove common commands
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"[{}$~^_]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


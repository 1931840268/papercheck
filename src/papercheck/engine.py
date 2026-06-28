"""Main checker engine — orchestrates all checks."""

from __future__ import annotations

from papercheck.checks.content import (
    check_anonymity,
    check_empty_sections,
    check_todo_markers,
    check_writing_issues,
)
from papercheck.checks.cross_refs import (
    check_duplicate_labels,
    check_undefined_refs,
    check_unused_labels,
)
from papercheck.checks.figures import (
    check_figure_placement,
    check_missing_graphics,
    check_unreferenced_figures,
)
from papercheck.checks.math import check_math_delimiters, check_notation_consistency
from papercheck.checks.references import (
    check_duplicate_citations,
    check_uncited_bib_entries,
    check_undefined_citations,
)
from papercheck.checks.structure import (
    check_bibliography,
    check_document_class,
    check_missing_abstract,
    check_section_ordering,
)
from papercheck.models import CheckResult, TexProject
from papercheck.parser import parse_bib_keys, parse_tex


def run_checks(project: TexProject, anonymous: bool = True) -> CheckResult:
    """Run all checks on a LaTeX project."""
    result = CheckResult()

    # Parse all files
    parsed_files: dict[str, object] = {}
    all_bib_keys: set[str] = set()
    all_cited_keys: set[str] = set()
    all_labels: set[str] = set()
    all_refs: set[str] = set()
    all_labels_with_loc: list[tuple[str, str, int]] = []

    # Parse .bib files
    for _bib_name, bib_content in project.bib_files.items():
        keys = parse_bib_keys(bib_content)
        all_bib_keys.update(keys)

    # Parse .tex files
    for tex_name, tex_content in project.tex_files.items():
        parsed = parse_tex(tex_content)
        parsed_files[tex_name] = parsed
        result.files_checked.append(tex_name)
        result.total_lines += len(parsed.lines)

        all_cited_keys.update(parsed.citations.keys())
        all_labels.update(parsed.labels.keys())
        all_refs.update(parsed.refs.keys())
        for key, line in parsed.labels.items():
            all_labels_with_loc.append((key, tex_name, line))

    # Run checks on each file
    for tex_name, parsed in parsed_files.items():
        # References
        result.issues.extend(check_undefined_citations(parsed, all_bib_keys, tex_name))
        result.issues.extend(check_duplicate_citations(parsed, tex_name))

        # Cross-references
        result.issues.extend(check_undefined_refs(parsed, all_labels, tex_name))
        result.issues.extend(check_unused_labels(parsed, all_refs, tex_name))

        # Math
        result.issues.extend(check_math_delimiters(parsed, tex_name))
        result.issues.extend(check_notation_consistency(parsed, tex_name))

        # Content
        result.issues.extend(check_todo_markers(parsed, tex_name))
        result.issues.extend(check_anonymity(parsed, tex_name, anonymous=anonymous))
        result.issues.extend(check_writing_issues(parsed, tex_name))
        result.issues.extend(check_empty_sections(parsed, tex_name))

        # Figures
        result.issues.extend(check_missing_graphics(parsed, project, tex_name))
        result.issues.extend(check_unreferenced_figures(parsed, tex_name))
        result.issues.extend(check_figure_placement(parsed, tex_name))

        # Structure (only on main file)
        if tex_name == project.main_file:
            result.issues.extend(check_missing_abstract(parsed, tex_name))
            result.issues.extend(check_section_ordering(parsed, tex_name))
            result.issues.extend(check_bibliography(parsed, tex_name))
            result.issues.extend(check_document_class(parsed, tex_name))

    # Cross-file checks
    result.issues.extend(check_duplicate_labels(all_labels_with_loc))
    for bib_name in project.bib_files:
        bib_keys = parse_bib_keys(project.bib_files[bib_name])
        result.issues.extend(check_uncited_bib_entries(all_cited_keys, bib_keys, bib_name))

    # Sort: errors first, then warnings, then info
    severity_order = {"error": 0, "warning": 1, "info": 2}
    result.issues.sort(key=lambda i: severity_order[i.severity.value])

    return result

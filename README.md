# papercheck

> **Pre-submission linter for LaTeX research papers. Catch desk-rejection issues before reviewers do.**

[![CI](https://github.com/1931840268/papercheck/actions/workflows/ci.yml/badge.svg)](https://github.com/1931840268/papercheck/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/papercheck?style=flat-square)](https://pypi.org/project/papercheck/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)]()
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)]()

---

Every researcher has been there: submit a paper, get desk-rejected for a broken reference. Or worse — reviewers find a TODO you forgot to remove.

**papercheck** runs 30+ automated checks on your LaTeX source and catches these issues in seconds:

```bash
papercheck ./my-paper/
```

```
📋 papercheck
┌───────────────────────────────────────────────────────────────────┐
│ Paper Health: 35/100 (HIGH RISK)                                  │
│ 847 lines across 1 file | 5 errors, 8 warnings, 6 suggestions    │
└───────────────────────────────────────────────────────────────────┘

📚 REFERENCES (3 issues)
 ❌  REF001   main.tex:15     Undefined citation: \cite{undefined_paper}
 ⚠️  REF003   main.tex:16     Duplicate key in citation command: bordes2013
 💡  REF002   refs.bib:0      Uncited bibliography entry: orphan_entry

🔗 CROSS-REFS (3 issues)
 ❌  XREF001  main.tex:38     Undefined reference: \ref{fig:nonexistent}
 ❌  XREF001  main.tex:38     Undefined reference: \ref{fig:architecture}
 💡  XREF002  main.tex:61     Unused label: \label{sec:phantom_label}

🧮 MATH (3 issues)
 ❌  MATH001  main.tex:33     Unclosed inline math delimiter ($)
 ⚠️  MATH002  main.tex:35     Mismatched \left/\right (1 left, 0 right)
 ⚠️  MATH003  main.tex:0      Inconsistent notation for 'x': \mathbf vs \bm

🕵️ ANONYMITY (3 issues)
 ❌  ANON001  main.tex:6      Potential anonymity violation: Author name in \author{}
 ❌  ANON001  main.tex:19     Potential anonymity violation: Self-reference language
 ❌  ANON001  main.tex:55     Potential anonymity violation: GitHub URL with username

📝 CONTENT (4 issues)
 ⚠️  CONT010  main.tex:12     TODO marker found: TODO
 ⚠️  CONT010  main.tex:57     TODO marker found: FIXME
 💡  CONT001  main.tex:13     Repeated word: 'are'
 💡  CONT007  main.tex:10     'In order to' can be simplified to 'to'

⛔ Fix errors before submission — they will likely cause desk rejection.
```

## Install

```bash
pip install papercheck
```

## What It Checks

| Category | Checks | Examples |
|----------|--------|----------|
| **📚 References** | Undefined citations, orphan bib entries, duplicate keys | `\cite{typo}` where "typo" isn't in .bib |
| **🔗 Cross-refs** | Undefined `\ref`, unused `\label`, duplicate labels | `\ref{fig:old}` when label was renamed |
| **🧮 Math** | Unclosed `$`, `\left`/`\right` mismatch, inconsistent notation | Using both `\mathbf{x}` and `\bm{x}` |
| **🕵️ Anonymity** | Author names, self-citations, GitHub URLs, institution names | Forgetting to anonymize for blind review |
| **📝 Content** | TODO/FIXME, repeated words, empty sections, style issues | "the the", "in order to" |
| **🖼️ Figures** | Missing image files, unreferenced figures, no placement | `\includegraphics{deleted.png}` |
| **🏗️ Structure** | Missing abstract, bibliography, section ordering | `\subsection` before any `\section` |

## Usage

```bash
# Check a single file
papercheck paper.tex

# Check an entire project directory
papercheck ./my-paper/

# JSON output (for CI)
papercheck ./my-paper/ --json

# Skip anonymity checks (for camera-ready)
papercheck ./my-paper/ --no-anon

# Fail CI if errors exist
papercheck ./my-paper/ --strict
```

## CI Integration

```yaml
# .github/workflows/paper-check.yml
- run: pip install papercheck
- run: papercheck ./paper/ --strict
```

## Zero Dependencies (beyond rich)

papercheck parses LaTeX directly — no TeX installation needed, no external tools, no network calls. It works anywhere Python runs.

## License

MIT

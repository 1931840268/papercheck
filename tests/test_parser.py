"""Unit tests for the LaTeX parser."""

from papercheck.parser import parse_bib_keys, parse_tex


class TestParseTex:
    def test_extracts_citations(self):
        content = r"We cite \cite{smith2020} and \citep{jones2021,wang2022}."
        parsed = parse_tex(content)
        assert "smith2020" in parsed.citations
        assert "jones2021" in parsed.citations
        assert "wang2022" in parsed.citations

    def test_extracts_labels(self):
        content = "\\section{Intro}\n\\label{sec:intro}\nText here."
        parsed = parse_tex(content)
        assert "sec:intro" in parsed.labels

    def test_extracts_refs(self):
        content = r"See Figure \ref{fig:arch} and Eq. \eqref{eq:loss}."
        parsed = parse_tex(content)
        assert "fig:arch" in parsed.refs
        assert "eq:loss" in parsed.refs

    def test_extracts_graphics(self):
        content = r"\includegraphics[width=0.5\linewidth]{images/fig1.png}"
        parsed = parse_tex(content)
        assert "images/fig1.png" in parsed.graphics

    def test_extracts_environments(self):
        content = "\\begin{figure}\nstuff\n\\end{figure}"
        parsed = parse_tex(content)
        assert any(env[0] == "figure" for env in parsed.environments)

    def test_extracts_sections(self):
        content = "\\section{Introduction}\n\\subsection{Background}"
        parsed = parse_tex(content)
        assert len(parsed.sections) == 2
        assert parsed.sections[0][1] == "Introduction"

    def test_ignores_comments(self):
        content = "% \\cite{commented_out}\n\\cite{real_one}"
        parsed = parse_tex(content)
        assert "commented_out" not in parsed.citations
        assert "real_one" in parsed.citations


class TestParseBibKeys:
    def test_extracts_keys(self):
        content = """
@article{smith2020,
  title={A Paper},
  author={Smith},
  year={2020}
}
@inproceedings{jones2021,
  title={Another},
  author={Jones},
  year={2021}
}
"""
        keys = parse_bib_keys(content)
        assert keys == {"smith2020", "jones2021"}

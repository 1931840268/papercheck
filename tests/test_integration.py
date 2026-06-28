"""End-to-end integration test using the sample paper fixture."""

from pathlib import Path

from papercheck.engine import run_checks
from papercheck.models import Category
from papercheck.parser import load_project

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestEndToEnd:
    """Test full pipeline on the sample paper with intentional issues."""

    def setup_method(self):
        project = load_project(FIXTURE_DIR / "sample_paper.tex")
        self.result = run_checks(project, anonymous=True)

    def test_finds_issues(self):
        assert len(self.result.issues) > 0

    def test_detects_undefined_citation(self):
        codes = [i.code for i in self.result.issues]
        assert "REF001" in codes  # undefined_paper not in bib

    def test_detects_uncited_bib_entry(self):
        codes = [i.code for i in self.result.issues]
        assert "REF002" in codes  # orphan_entry never cited

    def test_detects_duplicate_citation(self):
        codes = [i.code for i in self.result.issues]
        assert "REF003" in codes  # bordes2013transe duplicated in \cite{}

    def test_detects_undefined_ref(self):
        codes = [i.code for i in self.result.issues]
        assert "XREF001" in codes  # fig:nonexistent

    def test_detects_unused_label(self):
        codes = [i.code for i in self.result.issues]
        assert "XREF002" in codes  # sec:phantom_label

    def test_detects_unclosed_math(self):
        codes = [i.code for i in self.result.issues]
        assert "MATH001" in codes  # unclosed $ in loss function

    def test_detects_left_right_mismatch(self):
        codes = [i.code for i in self.result.issues]
        assert "MATH002" in codes  # \left( without matching \right)

    def test_detects_notation_inconsistency(self):
        codes = [i.code for i in self.result.issues]
        assert "MATH003" in codes  # \mathbf{x} vs \bm{x}

    def test_detects_todo(self):
        codes = [i.code for i in self.result.issues]
        assert "CONT010" in codes  # TODO and FIXME

    def test_detects_anonymity_violation(self):
        cats = [i.category for i in self.result.issues]
        assert Category.ANONYMITY in cats

    def test_detects_repeated_word(self):
        codes = [i.code for i in self.result.issues]
        assert "CONT001" in codes  # "are are"

    def test_detects_missing_graphics(self):
        codes = [i.code for i in self.result.issues]
        assert "FIG001" in codes  # figures/model_arch.png doesn't exist

    def test_detects_unreferenced_figure(self):
        codes = [i.code for i in self.result.issues]
        assert "FIG002" in codes  # fig:results_unreferenced

    def test_score_is_low(self):
        # Paper has many errors, score should be low
        assert self.result.score < 50

    def test_has_errors(self):
        assert self.result.error_count >= 3

    def test_files_checked(self):
        assert len(self.result.files_checked) == 1
        assert "sample_paper.tex" in self.result.files_checked[0]

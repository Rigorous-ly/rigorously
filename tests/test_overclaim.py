"""Tests for overclaim detection."""

import tempfile
from pathlib import Path

from rigorous.core.overclaim import check_overclaims, OverclaimFinding


def _write_temp(content: str, suffix: str = ".tex") -> Path:
    """Write content to a temp file and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


class TestOverclaimDetection:
    def test_detects_proven(self):
        path = _write_temp("We have proven that the model is correct.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "proof_language" for f in findings)
        assert any(f.severity == "critical" for f in findings)
        path.unlink()

    def test_detects_proves(self):
        path = _write_temp("This result proves the hypothesis.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "proof_language" for f in findings)
        path.unlink()

    def test_detects_validated(self):
        path = _write_temp("The model was validated against experimental data.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "validated" for f in findings)
        path.unlink()

    def test_allows_qualitatively_validated(self):
        path = _write_temp("The model was qualitatively validated.")
        findings = check_overclaims(path)
        validated_findings = [f for f in findings if f.pattern_name == "validated"]
        assert len(validated_findings) == 0
        path.unlink()

    def test_allows_not_validated(self):
        path = _write_temp("The model has not validated this claim.")
        findings = check_overclaims(path)
        validated_findings = [f for f in findings if f.pattern_name == "validated"]
        assert len(validated_findings) == 0
        path.unlink()

    def test_detects_impossible(self):
        path = _write_temp("It is impossible for the system to fail.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "impossible" for f in findings)
        path.unlink()

    def test_detects_machine_precision(self):
        path = _write_temp("Agreement to machine precision was achieved.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "machine_precision" for f in findings)
        path.unlink()

    def test_detects_machine_precision_hyphenated(self):
        path = _write_temp("The results match to machine-precision.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "machine_precision" for f in findings)
        path.unlink()

    def test_detects_statistically_indistinguishable(self):
        path = _write_temp("The groups were statistically indistinguishable.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "statistically_indistinguishable" for f in findings)
        path.unlink()

    def test_detects_confirms(self):
        path = _write_temp("This confirms the theoretical prediction.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "confirms_demonstrates" for f in findings)
        path.unlink()

    def test_detects_demonstrates_that(self):
        path = _write_temp("The experiment demonstrates that our approach works.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "confirms_demonstrates" for f in findings)
        path.unlink()

    def test_detects_novel_in_abstract(self):
        path = _write_temp(
            "\\begin{abstract}\nWe present a novel approach to modeling.\n\\end{abstract}\n"
        )
        findings = check_overclaims(path)
        assert any(f.pattern_name == "novel_in_abstract" for f in findings)
        path.unlink()

    def test_novel_outside_abstract_not_flagged(self):
        path = _write_temp("We present a novel approach to modeling.")
        findings = check_overclaims(path)
        # "novel" outside abstract should NOT be flagged by novel_in_abstract
        assert not any(f.pattern_name == "novel_in_abstract" for f in findings)
        path.unlink()

    def test_detects_clearly(self):
        path = _write_temp("The results clearly show improvement.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "clearly_obviously" for f in findings)
        path.unlink()

    def test_detects_unprecedented(self):
        path = _write_temp("This is an unprecedented achievement in the field.")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "priority_claim" for f in findings)
        path.unlink()

    def test_clean_text_no_findings(self):
        path = _write_temp(
            "The model predicts a 3.5-fold increase in expression.\n"
            "Results suggest consistency with the published data.\n"
            "We observed substantial improvement in all tested conditions.\n"
        )
        findings = check_overclaims(path)
        # Should have zero or very few findings
        critical = [f for f in findings if f.severity == "critical"]
        assert len(critical) == 0
        path.unlink()

    def test_latex_comments_ignored(self):
        path = _write_temp("% This is proven correct (comment, should be ignored)")
        findings = check_overclaims(path)
        proof_findings = [f for f in findings if f.pattern_name == "proof_language"]
        assert len(proof_findings) == 0
        path.unlink()

    def test_markdown_file(self):
        path = _write_temp("We have proven this works.", suffix=".md")
        findings = check_overclaims(path)
        assert any(f.pattern_name == "proof_language" for f in findings)
        path.unlink()

    def test_severity_ordering(self):
        path = _write_temp(
            "Clearly this proves the impossible result is validated.\n"
        )
        findings = check_overclaims(path)
        assert len(findings) > 1
        # Check ordering: critical before warning before info
        severities = [f.severity for f in findings]
        severity_vals = {"critical": 0, "warning": 1, "info": 2}
        mapped = [severity_vals[s] for s in severities]
        assert mapped == sorted(mapped)
        path.unlink()

    def test_file_not_found(self):
        try:
            check_overclaims("/nonexistent/file.tex")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_unsupported_extension(self):
        path = _write_temp("test", suffix=".py")
        try:
            check_overclaims(path)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
        finally:
            path.unlink()

    def test_finding_has_context(self):
        path = _write_temp("This result proves everything works perfectly.")
        findings = check_overclaims(path)
        proof_findings = [f for f in findings if f.pattern_name == "proof_language"]
        assert len(proof_findings) > 0
        assert proof_findings[0].context != ""
        path.unlink()

    def test_finding_has_line_number(self):
        path = _write_temp("line one\nline two\nThis proves it.\nline four\n")
        findings = check_overclaims(path)
        proof_findings = [f for f in findings if f.pattern_name == "proof_language"]
        assert len(proof_findings) > 0
        assert proof_findings[0].line == 3
        path.unlink()

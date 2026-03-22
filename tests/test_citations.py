"""Tests for citation verification."""

import asyncio
import tempfile
from pathlib import Path

from rigorous.core.citations import (
    CitationEntry,
    parse_bib_file,
    _normalize,
    _title_similarity,
    _parse_authors,
    _parse_bib_field,
)


def _write_temp_bib(content: str) -> Path:
    """Write content to a temp .bib file and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


SAMPLE_BIB = """\
@article{best2010serotonin,
    author = {Best, Janet and Nijhout, H. Frederik and Reed, Michael},
    title = {Serotonin synthesis, release and reuptake in terminals: a mathematical model},
    journal = {Theoretical Biology and Medical Modelling},
    year = {2010},
    volume = {7},
    doi = {10.1186/1742-4682-7-34},
}

@article{karin2020hpa,
    author = {Karin, Omer and Raz, Moriya and Tendler, Avichai and Bar, Alon and Korem Kohanim, Yael and Milo, Tomer and Milo, Ron},
    title = {A new model for the HPA axis explains dysregulation of stress hormones on the timescale of weeks},
    journal = {Molecular Systems Biology},
    year = {2020},
    doi = {10.15252/msb.20209510},
}

@article{no_doi_entry,
    author = {Smith, John},
    title = {Some paper without a DOI},
    journal = {Journal of Examples},
    year = {2023},
}
"""


class TestBibParsing:
    def test_parse_basic_bib(self):
        path = _write_temp_bib(SAMPLE_BIB)
        entries = parse_bib_file(path)
        assert len(entries) == 3
        path.unlink()

    def test_parse_entry_keys(self):
        path = _write_temp_bib(SAMPLE_BIB)
        entries = parse_bib_file(path)
        keys = {e.key for e in entries}
        assert "best2010serotonin" in keys
        assert "karin2020hpa" in keys
        assert "no_doi_entry" in keys
        path.unlink()

    def test_parse_title(self):
        path = _write_temp_bib(SAMPLE_BIB)
        entries = parse_bib_file(path)
        best = [e for e in entries if e.key == "best2010serotonin"][0]
        assert "Serotonin" in best.title
        path.unlink()

    def test_parse_authors(self):
        path = _write_temp_bib(SAMPLE_BIB)
        entries = parse_bib_file(path)
        best = [e for e in entries if e.key == "best2010serotonin"][0]
        assert len(best.authors) == 3
        assert any("Best" in a for a in best.authors)
        path.unlink()

    def test_parse_doi(self):
        path = _write_temp_bib(SAMPLE_BIB)
        entries = parse_bib_file(path)
        best = [e for e in entries if e.key == "best2010serotonin"][0]
        assert best.doi == "10.1186/1742-4682-7-34"
        path.unlink()

    def test_no_doi_entry(self):
        path = _write_temp_bib(SAMPLE_BIB)
        entries = parse_bib_file(path)
        no_doi = [e for e in entries if e.key == "no_doi_entry"][0]
        assert no_doi.doi == ""
        path.unlink()

    def test_parse_journal(self):
        path = _write_temp_bib(SAMPLE_BIB)
        entries = parse_bib_file(path)
        best = [e for e in entries if e.key == "best2010serotonin"][0]
        assert "Theoretical Biology" in best.journal
        path.unlink()

    def test_parse_year(self):
        path = _write_temp_bib(SAMPLE_BIB)
        entries = parse_bib_file(path)
        best = [e for e in entries if e.key == "best2010serotonin"][0]
        assert best.year == "2010"
        path.unlink()

    def test_empty_bib(self):
        path = _write_temp_bib("")
        entries = parse_bib_file(path)
        assert len(entries) == 0
        path.unlink()

    def test_bib_with_comments(self):
        bib = "% This is a comment\n" + SAMPLE_BIB
        path = _write_temp_bib(bib)
        entries = parse_bib_file(path)
        assert len(entries) == 3
        path.unlink()


class TestNormalization:
    def test_normalize_removes_braces(self):
        assert "{" not in _normalize("{Some Title}")

    def test_normalize_lowercase(self):
        assert _normalize("HELLO") == "hello"

    def test_normalize_strips(self):
        assert _normalize("  spaced  ") == "spaced"


class TestTitleSimilarity:
    def test_identical_titles(self):
        t = "Serotonin synthesis, release and reuptake"
        assert _title_similarity(t, t) == 1.0

    def test_similar_titles(self):
        a = "Serotonin synthesis, release and reuptake in terminals"
        b = "Serotonin synthesis release and reuptake in terminals a mathematical model"
        assert _title_similarity(a, b) > 0.7

    def test_different_titles(self):
        a = "Serotonin synthesis"
        b = "Dopamine receptor binding in the striatum"
        assert _title_similarity(a, b) < 0.5


class TestAuthorParsing:
    def test_parse_and_separated(self):
        result = _parse_authors("Best, Janet and Nijhout, H. Frederik and Reed, Michael")
        assert len(result) == 3

    def test_parse_single_author(self):
        result = _parse_authors("Smith, John")
        assert len(result) == 1
        assert "Smith" in result[0]

    def test_empty_string(self):
        result = _parse_authors("")
        assert len(result) == 0

    def test_latex_in_names(self):
        result = _parse_authors(r"M\"{u}ller, Hans")
        assert len(result) == 1


class TestBibFieldParsing:
    def test_braced_field(self):
        text = 'title = {Some Title},'
        assert _parse_bib_field(text, "title") == "Some Title"

    def test_quoted_field(self):
        text = 'title = "Some Title",'
        assert _parse_bib_field(text, "title") == "Some Title"

    def test_missing_field(self):
        text = 'author = {Someone},'
        assert _parse_bib_field(text, "title") == ""

    def test_multiline_field(self):
        text = 'title = {A Long\nTitle},'
        result = _parse_bib_field(text, "title")
        assert "Long" in result

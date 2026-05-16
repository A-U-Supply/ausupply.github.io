"""Tests for HTML generator."""
from src.html_generator import generate_html


def test_generate_html_contains_titles():
    titles = [
        {"id": "1", "title": "Tip of the Fatberg", "date": "2026-01-15", "author_id": "U1", "permalink": None},
        {"id": "2", "title": "sleep cartel", "date": "2026-01-16", "author_id": "U2", "permalink": None},
    ]
    html = generate_html(titles)
    assert "Tip of the Fatberg" in html
    assert "sleep cartel" in html
    assert "<!DOCTYPE html>" in html


def test_generate_html_has_interactivity():
    titles = [{"id": "1", "title": "test", "date": None, "author_id": None, "permalink": None}]
    html = generate_html(titles)
    assert "localStorage" in html
    assert "toolbar" in html.lower()


def test_generate_html_shared_header():
    titles = [{"id": "1", "title": "test", "date": None, "author_id": None, "permalink": None}]
    html = generate_html(titles)
    assert "cheeze-bourger2.png" in html
    assert "vcfmw.css" in html


def test_generate_html_empty():
    html = generate_html([])
    assert "<!DOCTYPE html>" in html
    assert "SONG TITLE LIBRARY" in html

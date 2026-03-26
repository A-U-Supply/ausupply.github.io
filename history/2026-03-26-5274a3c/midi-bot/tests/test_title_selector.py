"""Tests for song title selection with usage tracking."""
import json

from src.title_selector import select_title, load_titles


def test_load_titles(tmp_path):
    path = tmp_path / "titles.json"
    path.write_text(json.dumps([{"id": "1", "title": "first"}, {"id": "2", "title": "second"}]))
    assert len(load_titles(path)) == 2


def test_select_unused(tmp_path):
    titles_path = tmp_path / "titles.json"
    titles_path.write_text(json.dumps([
        {"id": "1", "title": "first"},
        {"id": "2", "title": "second"},
        {"id": "3", "title": "third"},
    ]))
    used_path = tmp_path / "used.json"
    used_path.write_text(json.dumps({"used_ids": ["1"]}))

    title = select_title(titles_path, used_path)
    assert title["id"] in ("2", "3")
    used = json.loads(used_path.read_text())
    assert title["id"] in used["used_ids"]


def test_resets_when_exhausted(tmp_path):
    titles_path = tmp_path / "titles.json"
    titles_path.write_text(json.dumps([{"id": "1", "title": "only"}]))
    used_path = tmp_path / "used.json"
    used_path.write_text(json.dumps({"used_ids": ["1"]}))

    title = select_title(titles_path, used_path)
    assert title["title"] == "only"


def test_creates_used_file(tmp_path):
    titles_path = tmp_path / "titles.json"
    titles_path.write_text(json.dumps([{"id": "1", "title": "first"}]))
    used_path = tmp_path / "used.json"

    select_title(titles_path, used_path)
    assert used_path.exists()


def test_missing_titles():
    from pathlib import Path
    assert load_titles(Path("/nonexistent")) == []

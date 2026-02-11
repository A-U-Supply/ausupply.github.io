"""Tests for state management."""

import json
from pathlib import Path
from state import load_state, save_state, add_urls_to_state, get_new_urls, DEFAULT_STATE


class TestLoadSaveState:
    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "state.json"
        state = load_state(path)
        assert state == DEFAULT_STATE

    def test_round_trip(self, tmp_path):
        path = tmp_path / "state.json"
        state = {
            "playlists": [{"id": "PL1", "title": "muzzik vol. 1", "count": 5}],
            "urls": [{"url": "https://youtu.be/abc", "video_id": "abc", "type": "youtube",
                       "added_to_playlist": True, "date": "2025-01-01", "user": "U1"}],
            "backlog": [],
        }
        save_state(state, path)
        loaded = load_state(path)
        assert loaded == state

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "subdir" / "state.json"
        save_state(DEFAULT_STATE, path)
        assert path.exists()


class TestAddUrlsToState:
    def test_adds_new_url(self):
        state = {"playlists": [], "urls": [], "backlog": []}
        new = [{"url": "https://youtu.be/abc", "video_id": "abc", "type": "youtube",
                "date": "2025-01-01", "user": "U1"}]
        add_urls_to_state(state, new)
        assert len(state["urls"]) == 1
        assert state["urls"][0]["added_to_playlist"] is False

    def test_skips_duplicate_url(self):
        state = {
            "playlists": [], "backlog": [],
            "urls": [{"url": "https://youtu.be/abc", "video_id": "abc", "type": "youtube",
                       "added_to_playlist": True, "date": "2025-01-01", "user": "U1"}],
        }
        new = [{"url": "https://youtu.be/abc", "video_id": "abc", "type": "youtube",
                "date": "2025-01-01", "user": "U1"}]
        add_urls_to_state(state, new)
        assert len(state["urls"]) == 1

    def test_adds_youtube_to_backlog(self):
        state = {"playlists": [], "urls": [], "backlog": []}
        new = [{"url": "https://youtu.be/abc", "video_id": "abc", "type": "youtube",
                "date": "2025-01-01", "user": "U1"}]
        add_urls_to_state(state, new)
        assert state["backlog"] == ["abc"]

    def test_does_not_add_other_to_backlog(self):
        state = {"playlists": [], "urls": [], "backlog": []}
        new = [{"url": "https://soundcloud.com/foo", "video_id": None, "type": "other",
                "date": "2025-01-01", "user": "U1"}]
        add_urls_to_state(state, new)
        assert state["backlog"] == []
        assert len(state["urls"]) == 1

    def test_new_videos_prepended_to_backlog(self):
        state = {"playlists": [], "urls": [], "backlog": ["old1", "old2"]}
        new = [{"url": "https://youtu.be/new1", "video_id": "new1", "type": "youtube",
                "date": "2025-01-02", "user": "U1"}]
        add_urls_to_state(state, new)
        assert state["backlog"] == ["new1", "old1", "old2"]


class TestGetNewUrls:
    def test_filters_known_urls(self):
        existing = [{"url": "https://youtu.be/abc"}]
        candidates = [
            {"url": "https://youtu.be/abc"},
            {"url": "https://youtu.be/def"},
        ]
        new = get_new_urls(candidates, existing)
        assert len(new) == 1
        assert new[0]["url"] == "https://youtu.be/def"

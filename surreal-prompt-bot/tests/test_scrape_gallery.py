"""Tests for drawma gallery scraper."""
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helper factories for Slack message/file dicts
# ---------------------------------------------------------------------------


def _make_message(text="hello", ts="1700000000.000000", user="U123", files=None, bot_id=None, reply_count=0):
    msg = {"text": text, "ts": ts, "user": user, "type": "message"}
    if files:
        msg["files"] = files
    if bot_id:
        msg["bot_id"] = bot_id
    if reply_count:
        msg["reply_count"] = reply_count
    return msg


def _make_file(file_id="F001", name="drawing.png", mimetype="image/png"):
    return {
        "id": file_id,
        "name": name,
        "mimetype": mimetype,
        "url_private_download": f"https://files.slack.com/files-pri/{file_id}/{name}",
        "original_w": 800,
        "original_h": 600,
    }


# ---------------------------------------------------------------------------
# extract_images_from_messages
# ---------------------------------------------------------------------------


class TestExtractImagesFromMessages:
    """Tests for extracting image files from Slack messages."""

    def test_extracts_single_image(self):
        from scrape_gallery import extract_images_from_messages

        img_file = _make_file()
        messages = [_make_message(files=[img_file])]
        result = extract_images_from_messages(messages)

        assert len(result) == 1
        assert result[0]["file_id"] == "F001"
        assert result[0]["name"] == "drawing.png"
        assert result[0]["message_ts"] == "1700000000.000000"
        assert result[0]["user"] == "U123"

    def test_extracts_multiple_images_from_one_message(self):
        from scrape_gallery import extract_images_from_messages

        files = [
            _make_file(file_id="F001", name="one.png"),
            _make_file(file_id="F002", name="two.jpg", mimetype="image/jpeg"),
        ]
        messages = [_make_message(files=files)]
        result = extract_images_from_messages(messages)

        assert len(result) == 2
        ids = {r["file_id"] for r in result}
        assert ids == {"F001", "F002"}

    def test_extracts_images_from_multiple_messages(self):
        from scrape_gallery import extract_images_from_messages

        messages = [
            _make_message(ts="1700000001.000000", files=[_make_file(file_id="F001")]),
            _make_message(ts="1700000002.000000", files=[_make_file(file_id="F002")]),
        ]
        result = extract_images_from_messages(messages)

        assert len(result) == 2

    def test_ignores_non_image_files(self):
        from scrape_gallery import extract_images_from_messages

        files = [
            _make_file(file_id="F001", name="drawing.png", mimetype="image/png"),
            _make_file(file_id="F002", name="doc.pdf", mimetype="application/pdf"),
            _make_file(file_id="F003", name="notes.txt", mimetype="text/plain"),
        ]
        messages = [_make_message(files=files)]
        result = extract_images_from_messages(messages)

        assert len(result) == 1
        assert result[0]["file_id"] == "F001"

    def test_ignores_messages_without_files(self):
        from scrape_gallery import extract_images_from_messages

        messages = [
            _make_message(text="just text"),
            _make_message(text="more text"),
        ]
        result = extract_images_from_messages(messages)

        assert len(result) == 0

    def test_includes_url_and_dimensions(self):
        from scrape_gallery import extract_images_from_messages

        img_file = _make_file()
        messages = [_make_message(files=[img_file])]
        result = extract_images_from_messages(messages)

        assert result[0]["url"] == "https://files.slack.com/files-pri/F001/drawing.png"
        assert result[0]["width"] == 800
        assert result[0]["height"] == 600

    def test_handles_various_image_mimetypes(self):
        from scrape_gallery import extract_images_from_messages

        files = [
            _make_file(file_id="F001", name="a.gif", mimetype="image/gif"),
            _make_file(file_id="F002", name="b.webp", mimetype="image/webp"),
            _make_file(file_id="F003", name="c.heic", mimetype="image/heic"),
        ]
        messages = [_make_message(files=files)]
        result = extract_images_from_messages(messages)

        assert len(result) == 3


# ---------------------------------------------------------------------------
# associate_images_with_prompts
# ---------------------------------------------------------------------------


class TestAssociateImagesWithPrompts:
    """Tests for matching images to bot prompts by date."""

    def test_matches_image_to_prompt_same_day(self):
        from scrape_gallery import associate_images_with_prompts

        # Both at 2023-11-14 UTC (00:00 and 06:00)
        images = [
            {"file_id": "F001", "message_ts": "1699941600.000000", "user": "U123"},
        ]
        prompts = [
            {"text": "Draw a fish wearing a top hat", "ts": "1699920000.000000"},
        ]
        result = associate_images_with_prompts(images, prompts)

        assert len(result) == 1
        assert result[0]["prompt"] == "Draw a fish wearing a top hat"

    def test_no_match_different_day(self):
        from scrape_gallery import associate_images_with_prompts

        # Image on 2023-11-15 00:00 UTC, prompt on 2023-11-14 00:00 UTC
        images = [
            {"file_id": "F001", "message_ts": "1700006400.000000", "user": "U123"},
        ]
        prompts = [
            {"text": "Draw a fish", "ts": "1699920000.000000"},
        ]
        result = associate_images_with_prompts(images, prompts)

        assert len(result) == 1
        assert result[0]["prompt"] is None

    def test_multiple_prompts_picks_same_day(self):
        from scrape_gallery import associate_images_with_prompts

        # Image on 2023-11-14 06:00 UTC
        images = [
            {"file_id": "F001", "message_ts": "1699941600.000000", "user": "U123"},
        ]
        prompts = [
            {"text": "Old prompt", "ts": "1699800000.000000"},  # 2023-11-12
            {"text": "Today prompt", "ts": "1699920000.000000"},  # 2023-11-14
        ]
        result = associate_images_with_prompts(images, prompts)

        assert result[0]["prompt"] == "Today prompt"

    def test_image_keeps_existing_fields(self):
        from scrape_gallery import associate_images_with_prompts

        # Both on 2023-11-14 UTC
        images = [
            {"file_id": "F001", "message_ts": "1699941600.000000", "user": "U123", "name": "art.png"},
        ]
        prompts = [
            {"text": "Draw something", "ts": "1699920000.000000"},
        ]
        result = associate_images_with_prompts(images, prompts)

        assert result[0]["file_id"] == "F001"
        assert result[0]["name"] == "art.png"
        assert result[0]["user"] == "U123"


# ---------------------------------------------------------------------------
# filter_new_images
# ---------------------------------------------------------------------------


class TestFilterNewImages:
    """Tests for filtering out already-downloaded images."""

    def test_filters_out_existing_ids(self):
        from scrape_gallery import filter_new_images

        images = [
            {"file_id": "F001"},
            {"file_id": "F002"},
            {"file_id": "F003"},
        ]
        manifest = [
            {"id": "F001", "filename": "2023-11-14-F001.png"},
            {"id": "F003", "filename": "2023-11-14-F003.png"},
        ]
        result = filter_new_images(images, manifest)

        assert len(result) == 1
        assert result[0]["file_id"] == "F002"

    def test_returns_all_when_manifest_empty(self):
        from scrape_gallery import filter_new_images

        images = [
            {"file_id": "F001"},
            {"file_id": "F002"},
        ]
        result = filter_new_images(images, [])

        assert len(result) == 2

    def test_returns_empty_when_all_exist(self):
        from scrape_gallery import filter_new_images

        images = [
            {"file_id": "F001"},
        ]
        manifest = [
            {"id": "F001", "filename": "2023-11-14-F001.png"},
        ]
        result = filter_new_images(images, manifest)

        assert len(result) == 0


# ---------------------------------------------------------------------------
# download_image
# ---------------------------------------------------------------------------


def _fake_image_response(content=b"\x89PNG fake image data", content_type="image/jpeg"):
    """Create a mock response that looks like a successful image download."""
    resp = MagicMock()
    resp.status_code = 200
    resp.content = content
    resp.headers = {"Content-Type": content_type}
    return resp


def _fake_redirect_response(location):
    """Create a mock 302 redirect response."""
    resp = MagicMock()
    resp.status_code = 302
    resp.headers = {"Location": location}
    return resp


class TestDownloadWithAuth:
    """Tests for the redirect-preserving download helper."""

    def test_follows_redirect_with_auth(self):
        from scrape_gallery import _download_with_auth

        redirect = _fake_redirect_response("https://cdn.slack.com/actual-image.jpg")
        image_resp = _fake_image_response()

        with patch("scrape_gallery.requests.get", side_effect=[redirect, image_resp]) as mock_get:
            resp = _download_with_auth("https://files.slack.com/original", "xoxb-token")

        assert resp.content == b"\x89PNG fake image data"
        # Both calls should have the auth header
        assert mock_get.call_count == 2
        for call in mock_get.call_args_list:
            assert call[1]["headers"]["Authorization"] == "Bearer xoxb-token"
            assert call[1]["allow_redirects"] is False

    def test_direct_response_no_redirect(self):
        from scrape_gallery import _download_with_auth

        image_resp = _fake_image_response()

        with patch("scrape_gallery.requests.get", return_value=image_resp) as mock_get:
            resp = _download_with_auth("https://files.slack.com/image.jpg", "xoxb-token")

        assert mock_get.call_count == 1
        assert resp.content == b"\x89PNG fake image data"

    def test_too_many_redirects_raises(self):
        from scrape_gallery import _download_with_auth

        redirect = _fake_redirect_response("https://cdn.slack.com/loop")

        with patch("scrape_gallery.requests.get", return_value=redirect):
            with pytest.raises(Exception, match="Too many redirects"):
                _download_with_auth("https://files.slack.com/loop", "xoxb-token")


class TestDownloadImage:
    """Tests for downloading an image and producing a manifest entry."""

    def test_downloads_to_correct_path(self, tmp_path):
        from scrape_gallery import download_image

        image = {
            "file_id": "F07ABC123",
            "name": "cool_drawing.jpg",
            "url": "https://files.slack.com/files-pri/F07ABC123/cool_drawing.jpg",
            "message_ts": "1706918400.000000",  # 2024-02-03 UTC
            "width": 800,
            "height": 600,
            "prompt": "Draw a fish",
            "artist": "jake",
        }

        image_resp = _fake_image_response()

        with patch("scrape_gallery.requests.get", return_value=image_resp) as mock_get:
            entry = download_image(image, tmp_path, "xoxb-test-token")

        # Verify the file was written
        expected_filename = "2024-02-03-F07ABC123.jpg"
        expected_path = tmp_path / expected_filename
        assert expected_path.exists()
        assert expected_path.read_bytes() == b"\x89PNG fake image data"

        # Verify Bearer auth header and no auto-redirect
        mock_get.assert_called_once_with(
            "https://files.slack.com/files-pri/F07ABC123/cool_drawing.jpg",
            headers={"Authorization": "Bearer xoxb-test-token"},
            timeout=30,
            allow_redirects=False,
        )

    def test_returns_manifest_entry(self, tmp_path):
        from scrape_gallery import download_image

        image = {
            "file_id": "F07ABC123",
            "name": "cool_drawing.jpg",
            "url": "https://files.slack.com/files-pri/F07ABC123/cool_drawing.jpg",
            "message_ts": "1706918400.000000",  # 2024-02-03 UTC
            "width": 800,
            "height": 600,
            "prompt": "Draw a fish",
            "artist": "jake",
        }

        image_resp = _fake_image_response()

        with patch("scrape_gallery.requests.get", return_value=image_resp):
            entry = download_image(image, tmp_path, "xoxb-test-token")

        assert entry == {
            "id": "F07ABC123",
            "filename": "2024-02-03-F07ABC123.jpg",
            "date": "2024-02-03",
            "prompt": "Draw a fish",
            "artist": "jake",
            "width": 800,
            "height": 600,
        }

    def test_uses_file_extension_from_name(self, tmp_path):
        from scrape_gallery import download_image

        image = {
            "file_id": "F999",
            "name": "my_art.png",
            "url": "https://files.slack.com/files-pri/F999/my_art.png",
            "message_ts": "1706918400.000000",
            "width": 1024,
            "height": 768,
            "prompt": None,
            "artist": "someone",
        }

        image_resp = _fake_image_response(content=b"png data", content_type="image/png")

        with patch("scrape_gallery.requests.get", return_value=image_resp):
            entry = download_image(image, tmp_path, "xoxb-token")

        assert entry["filename"] == "2024-02-03-F999.png"
        assert (tmp_path / "2024-02-03-F999.png").exists()

    def test_handles_no_prompt(self, tmp_path):
        from scrape_gallery import download_image

        image = {
            "file_id": "F555",
            "name": "doodle.jpeg",
            "url": "https://files.slack.com/files-pri/F555/doodle.jpeg",
            "message_ts": "1706918400.000000",
            "width": 640,
            "height": 480,
            "prompt": None,
            "artist": "anon",
        }

        image_resp = _fake_image_response(content=b"jpeg data")

        with patch("scrape_gallery.requests.get", return_value=image_resp):
            entry = download_image(image, tmp_path, "xoxb-token")

        assert entry["prompt"] is None

    def test_rejects_html_response(self, tmp_path):
        from scrape_gallery import download_image

        image = {
            "file_id": "F666",
            "name": "broken.jpg",
            "url": "https://files.slack.com/files-pri/F666/broken.jpg",
            "message_ts": "1706918400.000000",
            "width": 800,
            "height": 600,
            "prompt": None,
            "artist": "anon",
        }

        html_resp = MagicMock()
        html_resp.status_code = 200
        html_resp.content = b"<!DOCTYPE html><html>login page</html>"
        html_resp.headers = {"Content-Type": "text/html; charset=utf-8"}

        with patch("scrape_gallery.requests.get", return_value=html_resp):
            with pytest.raises(ValueError, match="Expected image content"):
                download_image(image, tmp_path, "xoxb-token")

        # Verify no file was written
        assert not (tmp_path / "2024-02-03-F666.jpg").exists()


# ---------------------------------------------------------------------------
# get_slack_username
# ---------------------------------------------------------------------------


class TestGetSlackUsername:
    """Tests for resolving Slack user display names."""

    def test_returns_display_name(self):
        from scrape_gallery import get_slack_username

        mock_client = MagicMock()
        mock_client.users_info.return_value = {
            "user": {
                "profile": {
                    "display_name": "jake",
                    "real_name": "Jake Smith",
                }
            }
        }
        result = get_slack_username(mock_client, "U123")

        assert result == "jake"
        mock_client.users_info.assert_called_once_with(user="U123")

    def test_falls_back_to_real_name_when_display_name_empty(self):
        from scrape_gallery import get_slack_username

        mock_client = MagicMock()
        mock_client.users_info.return_value = {
            "user": {
                "profile": {
                    "display_name": "",
                    "real_name": "Jake Smith",
                }
            }
        }
        result = get_slack_username(mock_client, "U456")

        assert result == "Jake Smith"

    def test_returns_user_id_on_exception(self):
        from scrape_gallery import get_slack_username

        mock_client = MagicMock()
        mock_client.users_info.side_effect = Exception("user_not_found")

        result = get_slack_username(mock_client, "U789")

        assert result == "U789"


# ---------------------------------------------------------------------------
# main (integration)
# ---------------------------------------------------------------------------


class TestMain:
    """Integration test for the main() orchestrator."""

    def test_happy_path_downloads_new_images(self, tmp_path, monkeypatch):
        from scrape_gallery import main
        import scrape_gallery

        # Set up environment
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")

        # Point OUTPUT_DIR and MANIFEST_PATH to temp directory
        output_dir = tmp_path / "img" / "drawma"
        manifest_path = output_dir / "manifest.json"
        monkeypatch.setattr(scrape_gallery, "OUTPUT_DIR", output_dir)
        monkeypatch.setattr(scrape_gallery, "MANIFEST_PATH", manifest_path)

        # Build mock Slack client
        mock_client = MagicMock()

        # auth_test -> bot user id
        mock_client.auth_test.return_value = {"user_id": "UBOT"}

        # conversations_list -> one channel matching #drawma
        mock_client.conversations_list.return_value = {
            "channels": [{"name": "drawma", "id": "C001"}],
            "response_metadata": {"next_cursor": ""},
        }

        # conversations_history -> one bot prompt + one user image message
        bot_msg = _make_message(
            text="Draw a surreal fish",
            ts="1706918400.000000",  # 2024-02-03 UTC
            user="UBOT",
        )
        user_msg = _make_message(
            ts="1706918500.000000",  # same day
            user="U123",
            files=[_make_file(file_id="F001", name="fish.png")],
        )
        mock_client.conversations_history.return_value = {
            "messages": [bot_msg, user_msg],
            "response_metadata": {"next_cursor": ""},
        }

        # users_info -> display name for the artist
        mock_client.users_info.return_value = {
            "user": {"profile": {"display_name": "jake", "real_name": "Jake"}}
        }

        # Patch WebClient constructor to return our mock
        monkeypatch.setattr(scrape_gallery, "WebClient", lambda token: mock_client)

        # Patch requests.get to return fake image bytes
        fake_resp = _fake_image_response(content=b"fake png data", content_type="image/png")

        with patch("scrape_gallery.requests.get", return_value=fake_resp):
            exit_code = main()

        # Verify success
        assert exit_code == 0

        # Verify image was written
        expected_file = output_dir / "2024-02-03-F001.png"
        assert expected_file.exists()
        assert expected_file.read_bytes() == b"fake png data"

        # Verify manifest was created with correct entry
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert len(manifest) == 1
        assert manifest[0]["id"] == "F001"
        assert manifest[0]["filename"] == "2024-02-03-F001.png"
        assert manifest[0]["date"] == "2024-02-03"
        assert manifest[0]["prompt"] == "Draw a surreal fish"
        assert manifest[0]["artist"] == "jake"

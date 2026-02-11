"""Tests for URL extraction and classification."""

from urls import extract_urls, extract_video_id, classify_url


class TestExtractUrls:
    def test_single_youtube_url(self):
        text = "check this out https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_urls(text) == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]

    def test_youtu_be_shortlink(self):
        text = "here https://youtu.be/dQw4w9WgXcQ nice"
        assert extract_urls(text) == ["https://youtu.be/dQw4w9WgXcQ"]

    def test_multiple_urls(self):
        text = "https://youtube.com/watch?v=abc123 and https://soundcloud.com/foo"
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "https://youtube.com/watch?v=abc123" in urls
        assert "https://soundcloud.com/foo" in urls

    def test_no_urls(self):
        assert extract_urls("just some text") == []

    def test_slack_angle_bracket_urls(self):
        """Slack wraps URLs in angle brackets: <https://example.com>"""
        text = "look <https://youtube.com/watch?v=abc123>"
        assert extract_urls(text) == ["https://youtube.com/watch?v=abc123"]

    def test_url_with_timestamp(self):
        text = "https://www.youtube.com/watch?v=abc123&t=120"
        assert extract_urls(text) == ["https://www.youtube.com/watch?v=abc123&t=120"]

    def test_slack_url_with_label(self):
        """Slack formats labeled links as <url|label>"""
        text = "check <https://youtube.com/watch?v=abc123|this video>"
        assert extract_urls(text) == ["https://youtube.com/watch?v=abc123"]


class TestExtractVideoId:
    def test_standard_watch_url(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert extract_video_id("https://youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_live_url(self):
        assert extract_video_id("https://youtube.com/live/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_with_extra_params(self):
        assert extract_video_id("https://youtube.com/watch?v=abc123&t=120&list=PLxyz") == "abc123"

    def test_non_youtube_returns_none(self):
        assert extract_video_id("https://soundcloud.com/foo") is None

    def test_youtube_channel_no_video_id(self):
        assert extract_video_id("https://youtube.com/channel/UCabc") is None

    def test_youtube_playlist_url(self):
        assert extract_video_id("https://youtube.com/playlist?list=PLabc") is None

    def test_embed_url(self):
        assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_music_youtube(self):
        assert extract_video_id("https://music.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


class TestClassifyUrl:
    def test_youtube_watch(self):
        assert classify_url("https://youtube.com/watch?v=abc") == "youtube"

    def test_youtu_be(self):
        assert classify_url("https://youtu.be/abc") == "youtube"

    def test_music_youtube(self):
        assert classify_url("https://music.youtube.com/watch?v=abc") == "youtube"

    def test_soundcloud(self):
        assert classify_url("https://soundcloud.com/foo") == "other"

    def test_bandcamp(self):
        assert classify_url("https://foo.bandcamp.com/track/bar") == "other"

    def test_spotify(self):
        assert classify_url("https://open.spotify.com/track/abc") == "other"

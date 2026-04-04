"""Tests for browser session persistence in src/scraper/browser_session.py."""

from unittest.mock import patch

from src.scraper import browser_session


class TestSessionPath:
    def test_default_name(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path):
            path = browser_session.session_path()
            assert path == tmp_path / "default.json"

    def test_named_session(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path):
            path = browser_session.session_path("linkedin")
            assert path == tmp_path / "linkedin.json"

    def test_creates_directory(self, tmp_path):
        new_dir = tmp_path / "sessions"
        with patch.object(browser_session, "SESSION_DIR", new_dir):
            browser_session.session_path("test")
            assert new_dir.exists()


class TestHasSession:
    def test_no_session(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path):
            assert browser_session.has_session("linkedin") is False

    def test_empty_file(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path):
            (tmp_path / "linkedin.json").touch()
            assert browser_session.has_session("linkedin") is False

    def test_valid_session(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path):
            (tmp_path / "linkedin.json").write_text('{"cookies": []}')
            assert browser_session.has_session("linkedin") is True


class TestDeleteSession:
    def test_delete_existing(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path):
            (tmp_path / "linkedin.json").write_text('{"cookies": []}')
            assert browser_session.delete_session("linkedin") is True
            assert not (tmp_path / "linkedin.json").exists()

    def test_delete_nonexistent(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path):
            assert browser_session.delete_session("linkedin") is False


class TestListSessions:
    def test_empty_dir(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path):
            assert browser_session.list_sessions() == []

    def test_multiple_sessions(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path):
            (tmp_path / "linkedin.json").write_text('{"cookies": []}')
            (tmp_path / "indeed.json").write_text('{"cookies": []}')
            (tmp_path / "empty.json").touch()  # empty file, should not appear
            sessions = browser_session.list_sessions()
            assert "linkedin" in sessions
            assert "indeed" in sessions
            assert "empty" not in sessions

    def test_no_dir(self, tmp_path):
        with patch.object(browser_session, "SESSION_DIR", tmp_path / "nonexistent"):
            assert browser_session.list_sessions() == []

"""Tests for pause/resume functionality in the database and computer_use module."""

import json
from unittest.mock import patch

import pytest

from src.db.database import (
    clear_pause_state,
    get_application,
    get_pause_state,
    init_db,
    save_pause_state,
    save_job,
    update_application,
)


@pytest.fixture()
def job_in_db(tmp_db, sample_job_data):
    """A single job saved to the temp database."""
    with patch("src.db.database.DB_PATH", tmp_db):
        job_id = save_job(sample_job_data, "https://example.com/job1", "# Job")
        update_application(job_id, status="docs_generated")
        yield job_id


class TestSavePauseState:
    def test_saves_state(self, job_in_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            messages = [
                {"role": "user", "content": [{"type": "text", "text": "Fill form"}]},
                {"role": "assistant", "content": [{"type": "text", "text": "Filling..."}]},
            ]
            save_pause_state(job_in_db, step=5, messages=messages, screenshot="base64data")

            app = get_application(job_in_db)
            assert app["status"] == "paused"
            assert app["pause_step"] == 5

    def test_state_roundtrip(self, job_in_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            messages = [
                {"role": "user", "content": [{"type": "text", "text": "Start"}]},
                {"role": "assistant", "content": [{"type": "text", "text": "Done"}]},
            ]
            save_pause_state(job_in_db, step=3, messages=messages, screenshot="scr123")

            state = get_pause_state(job_in_db)
            assert state is not None
            assert state["step"] == 3
            assert len(state["messages"]) == 2
            assert state["messages"][0]["role"] == "user"
            assert state["screenshot"] == "scr123"


class TestGetPauseState:
    def test_returns_none_when_not_paused(self, job_in_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            state = get_pause_state(job_in_db)
            assert state is None

    def test_returns_none_for_nonexistent_job(self, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            state = get_pause_state(99999)
            assert state is None


class TestClearPauseState:
    def test_clears_state(self, job_in_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            save_pause_state(job_in_db, step=5, messages=[{"role": "user", "content": "x"}], screenshot="s")
            clear_pause_state(job_in_db)

            state = get_pause_state(job_in_db)
            assert state is None

            # Status should still be paused (clear only clears the state data)
            # Caller is responsible for updating status
            app = get_application(job_in_db)
            assert app["pause_step"] is None
            assert app["pause_messages"] is None


class TestPauseSignal:
    def test_request_and_check(self):
        from src.agent.computer_use import (
            clear_pause_signal,
            is_pause_requested,
            request_pause,
        )

        job_id = 42
        assert is_pause_requested(job_id) is False

        request_pause(job_id)
        assert is_pause_requested(job_id) is True

        clear_pause_signal(job_id)
        assert is_pause_requested(job_id) is False

    def test_independent_jobs(self):
        from src.agent.computer_use import (
            clear_pause_signal,
            is_pause_requested,
            request_pause,
        )

        request_pause(1)
        assert is_pause_requested(1) is True
        assert is_pause_requested(2) is False

        clear_pause_signal(1)


class TestStripImagesForStorage:
    def test_strips_base64_images(self):
        from src.agent.computer_use import _strip_images_for_storage

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": "HUGE_BASE64"},
                    },
                ],
            },
        ]
        stripped = _strip_images_for_storage(messages)
        assert len(stripped) == 1
        content = stripped[0]["content"]
        assert content[0] == {"type": "text", "text": "Hello"}
        assert content[1] == {"type": "text", "text": "[screenshot taken]"}
        # Verify the original base64 data is gone
        assert "HUGE_BASE64" not in json.dumps(stripped)

    def test_preserves_text_and_tool_use(self):
        from src.agent.computer_use import _strip_images_for_storage

        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Do something"}],
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "OK, clicking button"}],
            },
        ]
        stripped = _strip_images_for_storage(messages)
        assert len(stripped) == 2
        assert stripped[0]["content"][0]["text"] == "Do something"
        assert stripped[1]["content"][0]["text"] == "OK, clicking button"

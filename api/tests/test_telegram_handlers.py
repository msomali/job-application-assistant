"""Test Telegram command handler dispatch."""

from src.telegram.handlers import _md_escape


def test_md_escape_special_chars():
    assert _md_escape("hello_world") == "hello\\_world"
    assert _md_escape("*bold*") == "\\*bold\\*"
    assert _md_escape(None) == "N/A"
    assert _md_escape("normal text") == "normal text"

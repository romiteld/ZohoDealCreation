"""Tests for Teams command normalization helper."""

from app.api.teams.routes import normalize_command_text


def test_normalize_command_text_removes_invisible_characters():
    """Zero-width/formatting characters should be stripped."""
    weird_input = "\u200epreferences\u00A0"
    assert normalize_command_text(weird_input) == "preferences"


def test_normalize_command_text_collapses_whitespace():
    """Whitespace should be normalized and lowercased."""
    mixed_input = "\ufeff  Preferences   now  "
    assert normalize_command_text(mixed_input) == "preferences now"

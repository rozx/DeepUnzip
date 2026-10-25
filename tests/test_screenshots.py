"""README screenshots are rendered from a recorded demo run, deterministically."""

import pytest

from scripts import generate_screenshots as screenshots


@pytest.mark.parametrize("language, title", [("zh", "深度解压"), ("en", "DeepUnzip")])
def test_screenshots_are_deterministic(language, title):
    first = screenshots.render_svg(language)
    assert first == screenshots.render_svg(language)
    assert title in first and "Concert.7z" in first


def test_wide_characters_get_two_cells():
    svg = '<text textLength="24.4" x="0">中文</text>'
    assert screenshots._widen_wide_characters(svg) == (
        '<text textLength="48.8" x="0">中文</text>'
    )


def test_screenshots_never_show_the_recording_machine():
    fixture = screenshots.FIXTURE.read_text(encoding="utf-8")
    assert screenshots.DISPLAY_ROOT not in fixture  # replaced on replay
    for language in ("zh", "en"):
        svg = screenshots.render_svg(language)
        assert "temp.deepunzip-" not in svg and "AppData" not in svg

"""README screenshots are rendered from a recorded demo run, deterministically."""

import pytest

from deepunzip.modules import i18n
from scripts import generate_screenshots as screenshots


@pytest.mark.parametrize("language", i18n.LANGUAGES)
def test_screenshots_are_deterministic(language):
    first = screenshots.render_svg(language)
    assert first == screenshots.render_svg(language)
    i18n.set_language(language)
    assert i18n.t("product") in first and "Concert.7z" in first


def test_wide_characters_get_two_cells():
    svg = '<text textLength="24.4" x="0">中文</text>'
    assert screenshots._widen_wide_characters(svg) == (
        '<text textLength="48.8" x="0">中文</text>'
    )


def test_screenshots_never_show_the_recording_machine():
    fixture = screenshots.FIXTURE.read_text(encoding="utf-8")
    assert screenshots.DISPLAY_ROOT not in fixture  # replaced on replay
    for language in i18n.LANGUAGES:
        svg = screenshots.render_svg(language)
        assert "temp.deepunzip-" not in svg and "AppData" not in svg

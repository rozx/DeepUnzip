import string

import pytest

from deepunzip.modules import i18n


def _fields(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_key_has_both_languages_with_the_same_placeholders():
    for key, entry in i18n.CATALOG.items():
        assert {"en", "zh"} <= set(entry), key
        assert entry["en"].strip() and entry["zh"].strip(), key
        assert _fields(entry["en"]) == _fields(entry["zh"]), key


def test_translation_uses_the_selected_language(monkeypatch):
    monkeypatch.setitem(
        i18n.CATALOG, "test.hello", {"en": "Hi {name}", "zh": "你好 {name}"}
    )
    i18n.set_language("zh")
    assert i18n.t("test.hello", name="A") == "你好 A"
    i18n.set_language("en")
    assert i18n.t("test.hello", name="A") == "Hi A"


def test_missing_chinese_entry_falls_back_to_english(monkeypatch):
    monkeypatch.setitem(i18n.CATALOG, "test.only_en", {"en": "only english"})
    i18n.set_language("zh")
    assert i18n.t("test.only_en") == "only english"


@pytest.mark.parametrize(
    "env, ui, expected",
    [
        ({"DEEPUNZIP_LANG": "en"}, "zh", "en"),
        ({"DEEPUNZIP_LANG": "ZH"}, "en", "zh"),
        ({"DEEPUNZIP_LANG": "fr"}, "zh", "zh"),
        ({}, "zh", "zh"),
        ({}, "en", "en"),
        ({}, None, "en"),
    ],
)
def test_language_resolution_order(env, ui, expected):
    assert i18n.resolve_language(env=env, system_language=lambda: ui) == expected


@pytest.mark.parametrize(
    "env, expected",
    [
        ({"LC_ALL": "zh_CN.UTF-8"}, "zh"),
        ({"LC_MESSAGES": "zh_TW.UTF-8"}, "zh"),
        ({"LANG": "en_US.UTF-8"}, "en"),
        ({"LC_ALL": "C", "LANG": "zh_CN.UTF-8"}, "en"),
        ({}, None),
    ],
)
def test_posix_language_comes_from_locale_variables(env, expected):
    assert i18n.posix_language(env) == expected


@pytest.mark.parametrize(
    "langid, expected", [(0x0804, "zh"), (0x0404, "zh"), (0x0409, "en")]
)
def test_windows_ui_language_id(langid, expected):
    assert i18n.language_from_langid(langid) == expected


def test_entries_only_use_known_variants():
    for key, entry in i18n.CATALOG.items():
        assert set(entry) <= {"en", "zh", "en_one", "zh_one"}, key


def test_singular_variant_is_used_for_a_count_of_one(monkeypatch):
    monkeypatch.setitem(
        i18n.CATALOG, "test.files", {"en": "{count} files", "en_one": "1 file"}
    )
    assert i18n.t("test.files", count=1) == "1 file"
    assert i18n.t("test.files", count=0) == "0 files"
    assert i18n.t("test.files", count=2) == "2 files"

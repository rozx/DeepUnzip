import string

import pytest

from deepunzip.modules import i18n

ALL = ("en", "zh", "zh-TW", "ja", "ko")


def _fields(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_supported_languages():
    assert i18n.LANGUAGES == ALL


def test_every_key_has_all_languages_with_the_same_placeholders():
    for key, entry in i18n.CATALOG.items():
        assert set(ALL) <= set(entry), key
        for language in ALL:
            assert entry[language].strip(), (key, language)
            assert _fields(entry[language]) == _fields(entry["en"]), (key, language)


def test_entries_only_use_known_variants():
    known = set(ALL) | {f"{language}_one" for language in ALL}
    for key, entry in i18n.CATALOG.items():
        assert set(entry) <= known, key


def test_translation_uses_the_selected_language(monkeypatch):
    monkeypatch.setitem(
        i18n.CATALOG,
        "test.hello",
        {"en": "Hi {name}", "zh": "你好 {name}", "ja": "こんにちは {name}"},
    )
    i18n.set_language("ja")
    assert i18n.t("test.hello", name="A") == "こんにちは A"
    i18n.set_language("zh")
    assert i18n.t("test.hello", name="A") == "你好 A"
    i18n.set_language("en")
    assert i18n.t("test.hello", name="A") == "Hi A"


def test_missing_entry_falls_back_to_english(monkeypatch):
    monkeypatch.setitem(i18n.CATALOG, "test.only_en", {"en": "only english"})
    i18n.set_language("ko")
    assert i18n.t("test.only_en") == "only english"


def test_unknown_language_is_english():
    i18n.set_language("fr")
    assert i18n.get_language() == "en"


def test_singular_variant_is_used_for_a_count_of_one(monkeypatch):
    monkeypatch.setitem(
        i18n.CATALOG, "test.files", {"en": "{count} files", "en_one": "1 file"}
    )
    assert i18n.t("test.files", count=1) == "1 file"
    assert i18n.t("test.files", count=0) == "0 files"
    assert i18n.t("test.files", count=2) == "2 files"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("en", "en"),
        ("en-GB", "en"),
        ("ZH", "zh"),
        ("zh_CN.UTF-8", "zh"),
        ("zh-SG", "zh"),
        ("zh-Hans", "zh"),
        ("zh_TW.Big5", "zh-TW"),
        ("zh-HK", "zh-TW"),
        ("zh_MO", "zh-TW"),
        ("zh-Hant-TW", "zh-TW"),
        ("ja", "ja"),
        ("ja_JP.UTF-8", "ja"),
        ("ko-KR", "ko"),
        ("ko_KR.eucKR@euro", "ko"),
        ("fr", None),
        ("C", None),
        ("", None),
    ],
)
def test_language_names_are_normalized(value, expected):
    assert i18n.normalize_language(value) == expected


@pytest.mark.parametrize(
    "env, ui, expected",
    [
        ({"DEEPUNZIP_LANG": "en"}, "zh", "en"),
        ({"DEEPUNZIP_LANG": "ZH"}, "en", "zh"),
        ({"DEEPUNZIP_LANG": "zh-tw"}, "en", "zh-TW"),
        ({"DEEPUNZIP_LANG": "ja"}, "zh", "ja"),
        ({"DEEPUNZIP_LANG": "fr"}, "ko", "ko"),
        ({}, "zh-TW", "zh-TW"),
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
        ({"LC_MESSAGES": "zh_TW.UTF-8"}, "zh-TW"),
        ({"LANG": "ja_JP.UTF-8"}, "ja"),
        ({"LANG": "ko_KR.UTF-8"}, "ko"),
        ({"LANG": "en_US.UTF-8"}, "en"),
        ({"LANG": "fr_FR.UTF-8"}, "en"),
        ({"LC_ALL": "C", "LANG": "zh_CN.UTF-8"}, "en"),
        ({}, None),
    ],
)
def test_posix_language_comes_from_locale_variables(env, expected):
    assert i18n.posix_language(env) == expected


@pytest.mark.parametrize(
    "langid, expected",
    [
        (0x0804, "zh"),  # PRC
        (0x1004, "zh"),  # Singapore
        (0x0004, "zh"),  # zh-Hans
        (0x0404, "zh-TW"),  # Taiwan
        (0x0C04, "zh-TW"),  # Hong Kong
        (0x1404, "zh-TW"),  # Macau
        (0x7C04, "zh-TW"),  # zh-Hant
        (0x0411, "ja"),
        (0x0412, "ko"),
        (0x0409, "en"),
        (0x040C, "en"),  # French
    ],
)
def test_windows_ui_language_id(langid, expected):
    assert i18n.language_from_langid(langid) == expected

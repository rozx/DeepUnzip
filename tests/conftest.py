"""Shared test setup.

Output follows the system language, so tests pin English before the package
is imported; tests that need Chinese call i18n.set_language("zh").
"""

import os

import pytest

os.environ["DEEPUNZIP_LANG"] = "en"

from deepunzip.modules import i18n  # noqa: E402


@pytest.fixture(autouse=True)
def _english_output():
    i18n.set_language("en")
    yield
    i18n.set_language("en")

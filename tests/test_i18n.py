import ast
import string
from pathlib import Path

import pytest

from deathcounter import i18n
from deathcounter.i18n import N_, tr
from deathcounter.lang_en import EN

PACKAGE = Path(__file__).resolve().parent.parent / "deathcounter"


def source_texts() -> dict[str, str]:
    """Teksty z tr("…") i N_("…") w kodzie programu → miejsce pierwszego wystąpienia."""
    texts = {}
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("tr", "N_") and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                texts.setdefault(node.args[0].value, f"{path.name}:{node.lineno}")
    return texts


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


@pytest.fixture
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("pl")


def test_every_text_has_english_translation():
    missing = {text: where for text, where in source_texts().items() if text not in EN}
    assert not missing, "Brak tłumaczenia:\n" + "\n".join(f"{w}: {t!r}" for t, w in missing.items())


def test_translations_keep_fields():
    wrong = [text for text, english in EN.items() if fields(text) != fields(english)]
    assert not wrong, "Inne pola {…} w tłumaczeniu:\n" + "\n".join(map(repr, wrong))


def test_no_unused_translations():
    unused = set(EN) - set(source_texts())
    assert not unused, "Tłumaczenia bez tekstu w kodzie:\n" + "\n".join(map(repr, sorted(unused)))


def test_tr_uses_selected_language(english):
    assert tr("Śmierci: {deaths}", deaths=3) == EN["Śmierci: {deaths}"].format(deaths=3)
    assert tr("Tekst bez tłumaczenia") == "Tekst bez tłumaczenia"
    i18n.set_language("pl")
    assert tr("Śmierci: {deaths}", deaths=3) == "Śmierci: 3"
    assert N_("Okno na wierzchu") == "Okno na wierzchu"


def test_unknown_language_falls_back_to_polish():
    i18n.set_language("xx")
    assert i18n.language() == "pl"

"""Resolución del idioma efectivo (OZ-35, ADR-013), verificada headless.

La preferencia (`system`/`es`/`en`) más el locale del SO deciden qué catálogo cargar. La regla
es pura; la detección real del locale la hace el composition root.
"""

from __future__ import annotations

import pytest

from application.i18n import FALLBACK_LANGUAGE, resolve_language


@pytest.mark.parametrize("override", ["es", "en"])
def test_override_explicito_se_respeta(override: str) -> None:
    # Un override manual gana sobre el locale del sistema, sea cual sea.
    assert resolve_language(override, "de_DE") == override


@pytest.mark.parametrize(
    "locale, esperado",
    [
        ("es", "es"),
        ("es_CL", "es"),
        ("es-AR", "es"),
        ("en", "en"),
        ("en_US", "en"),
        ("fr_FR", FALLBACK_LANGUAGE),
        ("de", FALLBACK_LANGUAGE),
        ("", FALLBACK_LANGUAGE),
        (None, FALLBACK_LANGUAGE),
    ],
)
def test_system_sigue_el_locale_del_so(locale: str | None, esperado: str) -> None:
    assert resolve_language("system", locale) == esperado


def test_valor_desconocido_se_trata_como_system() -> None:
    # Robustez: un ajuste corrupto no debe romper el arranque; se comporta como 'system'.
    assert resolve_language("xx", "es_ES") == "es"
    assert resolve_language("xx", "ja_JP") == FALLBACK_LANGUAGE

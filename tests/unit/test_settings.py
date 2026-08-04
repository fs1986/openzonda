"""Modelo de settings y su contrato de versionado (diseño §18).

El diseño exige que el upgrade *preserve* los settings y que su migración sea versionada.
De ahí que el esquema lleve número y que un archivo escrito por una versión futura de la
aplicación no se pueda cargar a ciegas: hacerlo significaría perder silenciosamente
opciones que esta versión no entiende.
"""

from __future__ import annotations

import pytest

from application.settings import SETTINGS_SCHEMA_VERSION, AppSettings


def test_los_valores_por_defecto_son_utilizables() -> None:
    settings = AppSettings()

    assert settings.schema_version == SETTINGS_SCHEMA_VERSION
    assert settings.language == "system"  # por defecto se sigue el locale del SO (ADR-013)
    assert settings.log_level == "INFO"


def test_appsettings_es_inmutable() -> None:
    settings = AppSettings()

    with pytest.raises(AttributeError):
        settings.language = "en"  # type: ignore[misc]


def test_se_puede_derivar_una_copia_modificada() -> None:
    original = AppSettings()
    derivada = original.with_changes(language="en")

    assert derivada.language == "en"
    assert original.language == "system", "el original no debe mutar"
    assert derivada.schema_version == original.schema_version


def test_acepta_system_es_y_en_como_idioma() -> None:
    for idioma in ("system", "es", "en"):
        assert AppSettings(language=idioma).language == idioma


def test_rechaza_un_idioma_no_soportado() -> None:
    with pytest.raises(ValueError, match="idioma"):
        AppSettings(language="fr")


def test_rechaza_un_nivel_de_log_invalido() -> None:
    with pytest.raises(ValueError, match="nivel de log"):
        AppSettings(log_level="CHATTY")

"""Adaptador JSON de settings: round-trip, atomicidad y esquema (diseño §18).

Tres escenarios que un usuario real va a producir tarde o temprano:

1. Primer arranque: el archivo no existe.
2. Archivo corrupto (corte de luz a mitad de escritura, edición manual fallida).
3. Archivo escrito por una versión *más nueva* de OpenZonda, tras un downgrade.

Los tres deben dejar la aplicación arrancable. El tercero, además, no debe destruir la
configuración que no entendemos: el diseño §18 exige que el upgrade preserve settings.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from application.settings import SETTINGS_SCHEMA_VERSION, AppSettings
from persistence.settings_json import (
    JsonSettingsRepository,
    UnsupportedSettingsSchemaError,
)


def test_primer_arranque_devuelve_los_valores_por_defecto(tmp_path: Path) -> None:
    repo = JsonSettingsRepository(tmp_path / "settings.json")

    assert repo.load() == AppSettings()


def test_round_trip(tmp_path: Path) -> None:
    destino = tmp_path / "settings.json"
    repo = JsonSettingsRepository(destino)
    settings = AppSettings().with_changes(language="en", log_level="DEBUG")

    repo.save(settings)

    assert destino.exists()
    assert JsonSettingsRepository(destino).load() == settings


def test_crea_el_directorio_padre_si_falta(tmp_path: Path) -> None:
    destino = tmp_path / "no" / "existe" / "settings.json"

    JsonSettingsRepository(destino).save(AppSettings())

    assert destino.exists()


def test_un_archivo_corrupto_no_impide_arrancar(tmp_path: Path) -> None:
    destino = tmp_path / "settings.json"
    destino.write_text("{esto no es JSON", encoding="utf-8")

    assert JsonSettingsRepository(destino).load() == AppSettings()


def test_un_esquema_mas_nuevo_se_rechaza_en_vez_de_adivinarse(tmp_path: Path) -> None:
    destino = tmp_path / "settings.json"
    destino.write_text(
        json.dumps({"schema_version": SETTINGS_SCHEMA_VERSION + 1, "language": "en"}),
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedSettingsSchemaError):
        JsonSettingsRepository(destino).load()


def test_un_esquema_mas_nuevo_no_se_sobrescribe(tmp_path: Path) -> None:
    """Downgrade: preferimos arrancar con defaults antes que destruir configuración ajena."""
    destino = tmp_path / "settings.json"
    contenido_futuro = json.dumps(
        {"schema_version": SETTINGS_SCHEMA_VERSION + 1, "language": "en", "tema": "oscuro"}
    )
    destino.write_text(contenido_futuro, encoding="utf-8")
    repo = JsonSettingsRepository(destino)

    with pytest.raises(UnsupportedSettingsSchemaError):
        repo.load()

    assert destino.read_text(encoding="utf-8") == contenido_futuro


def test_la_escritura_es_atomica_y_no_deja_temporales(tmp_path: Path) -> None:
    destino = tmp_path / "settings.json"
    repo = JsonSettingsRepository(destino)

    repo.save(AppSettings())
    repo.save(AppSettings().with_changes(language="en"))

    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]


def test_las_claves_desconocidas_se_ignoran_sin_romper(tmp_path: Path) -> None:
    destino = tmp_path / "settings.json"
    destino.write_text(
        json.dumps({"schema_version": SETTINGS_SCHEMA_VERSION, "language": "en", "obsoleto": 42}),
        encoding="utf-8",
    )

    assert JsonSettingsRepository(destino).load().language == "en"


def test_un_valor_invalido_cae_a_defaults_en_vez_de_reventar(tmp_path: Path) -> None:
    destino = tmp_path / "settings.json"
    destino.write_text(
        json.dumps({"schema_version": SETTINGS_SCHEMA_VERSION, "language": "klingon"}),
        encoding="utf-8",
    )

    assert JsonSettingsRepository(destino).load() == AppSettings()

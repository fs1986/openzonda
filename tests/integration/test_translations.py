"""Instalación de catálogos de traducción (OZ-35, ADR-013), con Qt offscreen.

Verifica el mecanismo real: compilar un `.qm` con `pyside6-lrelease`, instalarlo sobre la
`QApplication` y comprobar que `tr()` devuelve la traducción. El empaquetado del `.qm` dentro
del `.exe` congelado es `[HW]` (se prueba desde el binario en la VM).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="la UI es un extra opcional (extra 'ui')")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from desktop.translations import (
    detect_system_language,
    effective_language,
    install_translators,
)

_LRELEASE = shutil.which("pyside6-lrelease")

_TS_EN = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en">
<context>
  <name>prueba</name>
  <message>
    <source>Guardar</source>
    <translation>Save</translation>
  </message>
</context>
</TS>
"""


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    yield app  # type: ignore[misc]


def _compilar_catalogo(destino_dir: Path) -> None:
    """Genera `openzonda_en.qm` en `destino_dir` a partir de un .ts mínimo."""
    ts = destino_dir / "openzonda_en.ts"
    ts.write_text(_TS_EN, encoding="utf-8")
    qm = destino_dir / "openzonda_en.qm"
    subprocess.run([_LRELEASE, str(ts), "-qm", str(qm)], check=True, capture_output=True)


def test_detect_system_language_devuelve_un_codigo(qt_app: QApplication) -> None:
    codigo = detect_system_language()
    assert isinstance(codigo, str) and codigo  # p. ej. "es_CL", "en_US", "C"


def test_effective_language_respeta_el_override() -> None:
    # No depende del SO: un override explícito gana.
    assert effective_language("es") == "es"
    assert effective_language("en") == "en"


@pytest.mark.skipif(_LRELEASE is None, reason="pyside6-lrelease no disponible")
def test_install_translators_traduce_los_strings_propios(
    qt_app: QApplication, tmp_path: Path
) -> None:
    _compilar_catalogo(tmp_path)

    translators = install_translators(qt_app, "en", tmp_path)

    try:
        assert translators, "debió instalar al menos el catálogo propio openzonda_en.qm"
        assert QCoreApplication.translate("prueba", "Guardar") == "Save"
    finally:
        for t in translators:
            qt_app.removeTranslator(t)


_REPO_TRANSLATIONS = Path(__file__).resolve().parents[2] / "translations"


def test_catalogo_real_en_traduce_los_strings_del_producto(qt_app: QApplication) -> None:
    """El `openzonda_en.qm` versionado traduce strings reales de la UI (no un fixture).

    Si falla, el `.qm` está desactualizado respecto del `.ts`: regenerar con
    `uv run python scripts/compile_translations.py`."""
    if not (_REPO_TRANSLATIONS / "openzonda_en.qm").is_file():
        pytest.skip("openzonda_en.qm no compilado; correr scripts/compile_translations.py")

    translators = install_translators(qt_app, "en", _REPO_TRANSLATIONS)
    try:
        assert QCoreApplication.translate("floorplan", "del archivo") == "from file"
        assert QCoreApplication.translate("floorplan", "sin calibrar") == "uncalibrated"
        assert QCoreApplication.translate("MainWindow", "&Nuevo") == "&New"
        assert QCoreApplication.translate("shell", "No se pudo abrir el proyecto") == (
            "Could not open the project"
        )
    finally:
        for t in translators:
            qt_app.removeTranslator(t)


def test_install_translators_sin_catalogo_propio_no_falla(
    qt_app: QApplication, tmp_path: Path
) -> None:
    # En español no hay openzonda_es.qm (el origen ya es español): no instalar nada propio es
    # correcto, no un error. Puede instalar el catálogo de Qt si está disponible.
    translators = install_translators(qt_app, "es", tmp_path)
    for t in translators:
        qt_app.removeTranslator(t)
    # El único invariante fuerte: no revienta y devuelve una lista (vacía o con qtbase).
    assert isinstance(translators, list)

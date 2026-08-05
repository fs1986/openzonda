"""Instalación de los catálogos de traducción de Qt (OZ-35, ADR-013).

El texto de la UI está escrito en **español** (es el idioma de origen de `tr()`). Traducir a
inglés = instalar el catálogo `openzonda_en.qm`; mostrar el español = no instalar nada propio.
Los botones estándar de Qt (`QMessageBox` etc.) vienen en inglés por defecto, así que el
español necesita además el catálogo del framework `qtbase_es.qm`.

Los translators se instalan sobre la `QApplication` **antes** de crear los widgets, y hay que
conservar sus referencias vivas: un `QTranslator` que se recolecta deja de traducir. Por eso
`install_translators` los devuelve y el llamante los retiene.

La detección del locale (Qt) vive acá; la *regla* de qué idioma efectivo usar es pura y está
en `application.i18n` (se prueba headless).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from application.i18n import resolve_language

APP_CATALOG = "openzonda"


def detect_system_language() -> str:
    """Código de locale del sistema, p. ej. ``"es_CL"`` o ``"en_US"`` (Qt)."""
    return QLocale.system().name()


def effective_language(setting: str) -> str:
    """Idioma efectivo (``"es"``/``"en"``) combinando la preferencia con el locale del SO."""
    return resolve_language(setting, detect_system_language())


def install_translators(
    app: QApplication, language: str, app_translations_dir: Path
) -> list[QTranslator]:
    """Instala los catálogos para `language` y devuelve los translators instalados.

    El llamante DEBE conservar la lista viva mientras la app corra. Cada catálogo se instala
    solo si su `.qm` carga: en español no hay `openzonda_es.qm` (el origen ya es español) y eso
    es correcto, no un error.
    """
    instalados: list[QTranslator] = []

    propio = QTranslator(app)
    if propio.load(f"{APP_CATALOG}_{language}", str(app_translations_dir)):
        app.installTranslator(propio)
        instalados.append(propio)

    qt = QTranslator(app)
    qt_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt.load(f"qtbase_{language}", qt_dir):
        app.installTranslator(qt)
        instalados.append(qt)

    return instalados

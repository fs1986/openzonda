"""Arranque de la aplicación Qt. Recibe sus dependencias ya construidas (ADR-008)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTranslator
from PySide6.QtWidgets import QApplication

from application.project_service import ProjectService
from application.settings import SettingsRepository
from desktop.main_window import MainWindow
from desktop.translations import effective_language, install_translators


def run_app(
    project_service: ProjectService,
    settings_repository: SettingsRepository,
    app_version: str,
    argv: list[str] | None = None,
    autoclose_ms: int | None = None,
    translations_dir: Path | None = None,
) -> int:
    """Arranca la aplicación y devuelve su código de salida.

    `autoclose_ms` cierra la ventana pasado ese tiempo. Lo usa el smoke test: así el
    arranque que se verifica es el real —event loop incluido— y no una simulación.

    `translations_dir` es la carpeta con los `.qm` propios; el idioma efectivo sale de los
    settings + el locale del SO. Los translators se instalan **antes** de crear la ventana y se
    retienen en una variable local viva durante todo `app.exec()` (si se recolectaran, dejarían
    de traducir).
    """
    app = QApplication.instance() or QApplication(argv or [])

    _translators: list[QTranslator] = []
    if translations_dir is not None:
        idioma = effective_language(settings_repository.load().language)
        _translators = install_translators(app, idioma, translations_dir)

    ventana = MainWindow(
        project_service=project_service,
        settings_repository=settings_repository,
        app_version=app_version,
    )
    ventana.show()

    if autoclose_ms is not None:
        QTimer.singleShot(autoclose_ms, ventana.close)

    return int(app.exec())  # type: ignore[union-attr]

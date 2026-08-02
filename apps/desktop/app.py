"""Arranque de la aplicación Qt. Recibe sus dependencias ya construidas (ADR-008)."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from application.settings import SettingsRepository
from desktop.main_window import MainWindow


def run_app(
    settings_repository: SettingsRepository,
    app_version: str,
    argv: list[str] | None = None,
    autoclose_ms: int | None = None,
) -> int:
    """Arranca la aplicación y devuelve su código de salida.

    `autoclose_ms` cierra la ventana pasado ese tiempo. Lo usa el smoke test: así el
    arranque que se verifica es el real —event loop incluido— y no una simulación.
    """
    app = QApplication.instance() or QApplication(argv or [])
    ventana = MainWindow(settings_repository=settings_repository, app_version=app_version)
    ventana.show()

    if autoclose_ms is not None:
        QTimer.singleShot(autoclose_ms, ventana.close)

    return int(app.exec())  # type: ignore[union-attr]

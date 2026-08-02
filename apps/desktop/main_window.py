"""Ventana principal — walking skeleton de F0.4.

Recibe el port de settings **por constructor**: no lo construye, no lo busca y no sabe si
detrás hay un archivo JSON, una base de datos o un doble de test (ADR-008). Esa es la
razón de que estos tests corran sin tocar el disco.

Anti-patrón declarado en el plan §3.1: no sobre-diseñar la UI en esta fase. El pulido
visual llega en F4, cuando haya heatmaps que mostrar.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from application.settings import SettingsRepository

DEFAULT_SIZE = (1024, 700)


class MainWindow(QMainWindow):
    def __init__(self, settings_repository: SettingsRepository, app_version: str) -> None:
        super().__init__()
        self._settings_repository = settings_repository
        self._settings = settings_repository.load()

        self.setWindowTitle(f"OpenZonda {app_version}")
        self._restaurar_geometria()
        self.setCentralWidget(self._construir_contenido(app_version))

    def _restaurar_geometria(self) -> None:
        geometria = self._settings.window_geometry
        if geometria is None:
            self.resize(*DEFAULT_SIZE)
            return
        x, y, ancho, alto = geometria
        self.setGeometry(x, y, ancho, alto)

    def _construir_contenido(self, app_version: str) -> QWidget:
        contenedor = QWidget(self)
        layout = QVBoxLayout(contenedor)
        layout.addWidget(QLabel(f"OpenZonda {app_version}", contenedor))
        layout.addWidget(
            QLabel(
                "Walking skeleton. La shell de proyecto llega en F1.",
                contenedor,
            )
        )
        layout.addStretch(1)
        return contenedor

    def closeEvent(self, event: object) -> None:
        rect = self.geometry()
        self._settings_repository.save(
            self._settings.with_changes(
                window_geometry=(rect.x(), rect.y(), rect.width(), rect.height())
            )
        )
        super().closeEvent(event)  # type: ignore[arg-type]

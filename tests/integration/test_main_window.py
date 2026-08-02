"""Walking skeleton de la UI (F0.4) y su contrato de inyección de dependencias.

Lo que se verifica aquí no es estética: es que la ventana **recibe** su repositorio de
settings en vez de construirlo. Esa es la diferencia entre una UI testeable sin disco y
una que arrastra infraestructura, y es la razón de ser de ADR-008.

Los tests corren con la plataforma Qt `offscreen`, así que no necesitan escritorio ni en
CI ni en la máquina del fundador.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from application.settings import AppSettings

pytest.importorskip("PySide6", reason="la UI es un extra opcional (extra 'ui')")

# Debe fijarse antes de instanciar QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from desktop.main_window import MainWindow


class RepositorioFalso:
    """Doble del port `SettingsRepository`. No toca el disco."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self.guardados: list[AppSettings] = []

    def load(self) -> AppSettings:
        return self.settings

    def save(self, settings: AppSettings) -> None:
        self.guardados.append(settings)


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    yield app  # type: ignore[misc]


def test_la_ventana_se_construye_sin_tocar_el_disco(qt_app: QApplication) -> None:
    repo = RepositorioFalso()

    ventana = MainWindow(settings_repository=repo, app_version="1.2.3")

    assert repo.guardados == []
    ventana.close()


def test_el_titulo_declara_la_version(qt_app: QApplication) -> None:
    ventana = MainWindow(settings_repository=RepositorioFalso(), app_version="1.2.3")

    assert "OpenZonda" in ventana.windowTitle()
    assert "1.2.3" in ventana.windowTitle()
    ventana.close()


def test_al_cerrar_persiste_los_settings(qt_app: QApplication) -> None:
    repo = RepositorioFalso()
    ventana = MainWindow(settings_repository=repo, app_version="1.2.3")

    ventana.close()

    assert len(repo.guardados) == 1, "cerrar la ventana debe persistir los settings"


def test_la_geometria_de_la_sesion_anterior_se_restaura(qt_app: QApplication) -> None:
    guardada = AppSettings().with_changes(window_geometry=(50, 60, 800, 600))
    ventana = MainWindow(settings_repository=RepositorioFalso(guardada), app_version="1.2.3")

    geometria = ventana.geometry()
    assert (geometria.width(), geometria.height()) == (800, 600)
    ventana.close()


def test_la_geometria_se_guarda_al_cerrar(qt_app: QApplication) -> None:
    repo = RepositorioFalso()
    ventana = MainWindow(settings_repository=repo, app_version="1.2.3")
    ventana.setGeometry(10, 20, 640, 480)

    ventana.close()

    assert repo.guardados[-1].window_geometry == (10, 20, 640, 480)

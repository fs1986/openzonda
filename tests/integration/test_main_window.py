"""Shell de proyectos (OZ-8) y su contrato de inyección de dependencias.

Lo que se verifica aquí no es estética: es que la ventana **recibe** sus puertos —settings y
servicio de proyecto— en vez de construirlos (ADR-008), que restaura/persiste geometría, y
que la vista central cambia de Inicio a Proyecto según el estado. La lógica fina del flujo
(dirty, recientes, guardar-como) se prueba sin Qt en `tests/unit/test_shell_viewmodel.py`.

Los tests corren con la plataforma Qt `offscreen`: no necesitan escritorio ni en CI ni en la
máquina del fundador.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from application.project_service import ProjectService, ProjectWorkspace
from application.settings import AppSettings

pytest.importorskip("PySide6", reason="la UI es un extra opcional (extra 'ui')")

# Debe fijarse antes de instanciar QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from desktop.main_window import MainWindow


@pytest.fixture(autouse=True)
def sin_dialogos_modales(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutraliza los diálogos modales: en `offscreen` nadie los responde y colgarían el
    test. Por defecto 'Descartar', que es lo que necesita cerrar una ventana con cambios."""
    monkeypatch.setattr(
        QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Discard, raising=False
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok),
        raising=False,
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")), raising=False
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")), raising=False
    )


class RepositorioFalso:
    """Doble del port `SettingsRepository`. No toca el disco."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self.guardados: list[AppSettings] = []

    def load(self) -> AppSettings:
        return self.settings

    def save(self, settings: AppSettings) -> None:
        self.guardados.append(settings)


class StoreFalso:
    """Doble del port `ProjectStore`. Crea working dirs de mentira; no serializa nada."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._n = 0

    def create_empty(self) -> ProjectWorkspace:
        self._n += 1
        d = self._root / f"ws{self._n}"
        d.mkdir(parents=True, exist_ok=True)
        return ProjectWorkspace(working_dir=d)

    def open(self, source: Path) -> tuple[ProjectWorkspace, object]:  # pragma: no cover
        raise NotImplementedError

    def save(self, workspace: ProjectWorkspace, project: object, destination: Path) -> None:
        pass

    def discard(self, workspace: ProjectWorkspace) -> None:
        pass

    def cleanup_orphans(self) -> int:
        return 0


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    yield app  # type: ignore[misc]


def _ventana(repo: RepositorioFalso, tmp_path: Path, *, version: str = "1.2.3") -> MainWindow:
    service = ProjectService(StoreFalso(tmp_path / "projects"), repo)
    return MainWindow(project_service=service, settings_repository=repo, app_version=version)


def test_la_ventana_se_construye_sin_tocar_el_disco(qt_app: QApplication, tmp_path: Path) -> None:
    repo = RepositorioFalso()

    ventana = _ventana(repo, tmp_path)

    assert repo.guardados == []
    ventana.close()


def test_el_titulo_sin_proyecto_es_la_app(qt_app: QApplication, tmp_path: Path) -> None:
    ventana = _ventana(RepositorioFalso(), tmp_path)

    assert ventana.windowTitle() == "OpenZonda"
    ventana.close()


def test_al_crear_un_proyecto_el_titulo_lo_refleja(qt_app: QApplication, tmp_path: Path) -> None:
    ventana = _ventana(RepositorioFalso(), tmp_path)

    ventana._vm.request_new()  # type: ignore[attr-defined]

    # Proyecto nuevo: sin guardar (dirty) → marca "•" y nombre en el título.
    assert ventana.windowTitle().startswith("• ")
    assert "Proyecto sin título" in ventana.windowTitle()
    ventana.close()


def test_al_crear_un_proyecto_se_muestra_la_vista_de_proyecto(
    qt_app: QApplication, tmp_path: Path
) -> None:
    ventana = _ventana(RepositorioFalso(), tmp_path)
    inicio = ventana._stack.currentWidget()  # type: ignore[attr-defined]

    ventana._vm.request_new()  # type: ignore[attr-defined]

    assert ventana._stack.currentWidget() is not inicio  # cambió de Inicio a Proyecto
    ventana.close()


def test_editar_el_nombre_sin_perder_foco_marca_dirty(qt_app: QApplication, tmp_path: Path) -> None:
    """Regresión (OZ-8, hallazgo del PO): editar el Nombre y cerrar con la X sin sacar el
    foco del campo debe quedar *dirty* — si no, se pierde la edición sin el diálogo de
    «¿guardar?». Antes se marcaba con `editingFinished` (solo al perder foco) y se perdía."""
    repo = RepositorioFalso()
    service = ProjectService(StoreFalso(tmp_path / "projects"), repo)
    service.new_project()
    service.save_as(tmp_path / "p.wifisurvey")  # deja el documento limpio (dirty = False)
    assert service.is_dirty is False
    ventana = MainWindow(project_service=service, settings_repository=repo, app_version="1.2.3")
    ventana.show()

    # Tecleo real en el campo Nombre, SIN disparar editingFinished (no se pierde el foco).
    campo = ventana._proyecto._nombre  # type: ignore[attr-defined]
    campo.setFocus()
    QTest.keyClicks(campo, "X")

    assert service.is_dirty is True, "editar el nombre debe marcar dirty aunque no se pierda foco"
    assert ventana.windowTitle().startswith("• ")
    ventana.close()


def test_al_cerrar_persiste_los_settings(qt_app: QApplication, tmp_path: Path) -> None:
    repo = RepositorioFalso()
    ventana = _ventana(repo, tmp_path)

    ventana.close()

    assert len(repo.guardados) == 1, "cerrar la ventana debe persistir los settings"


def test_la_geometria_de_la_sesion_anterior_se_restaura(
    qt_app: QApplication, tmp_path: Path
) -> None:
    guardada = AppSettings().with_changes(window_geometry=(50, 60, 800, 600))
    ventana = _ventana(RepositorioFalso(guardada), tmp_path)

    geometria = ventana.geometry()
    assert (geometria.width(), geometria.height()) == (800, 600)
    ventana.close()


def test_la_geometria_se_guarda_al_cerrar(qt_app: QApplication, tmp_path: Path) -> None:
    repo = RepositorioFalso()
    ventana = _ventana(repo, tmp_path)
    ventana.setGeometry(10, 20, 640, 480)

    ventana.close()

    assert repo.guardados[-1].window_geometry == (10, 20, 640, 480)

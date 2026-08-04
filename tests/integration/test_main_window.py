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

from PySide6.QtCore import QBuffer, QByteArray, QPointF
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from desktop.main_window import MainWindow, _Lienzo


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
        self.assets: dict[str, bytes] = {}

    def create_empty(self) -> ProjectWorkspace:
        self._n += 1
        d = self._root / f"ws{self._n}"
        d.mkdir(parents=True, exist_ok=True)
        return ProjectWorkspace(working_dir=d)

    def open(self, source: Path) -> tuple[ProjectWorkspace, object]:  # pragma: no cover
        raise NotImplementedError

    def save(self, workspace: ProjectWorkspace, project: object, destination: Path) -> None:
        pass

    def store_asset(self, workspace: ProjectWorkspace, data: bytes, extension: str) -> str:
        import hashlib

        sha = hashlib.sha256(data).hexdigest()
        self.assets[sha] = data
        return sha

    def read_asset(self, workspace: ProjectWorkspace, sha256: str) -> bytes:
        return self.assets[sha256]

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


def _png_minimo() -> bytes:
    import struct
    import zlib

    def chunk(tipo: bytes, datos: bytes) -> bytes:
        crc = zlib.crc32(tipo + datos) & 0xFFFFFFFF
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 640, 480, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )


def test_el_dock_del_arbol_muestra_el_resumen_honesto_del_plano(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Cableado extremo a extremo del dock (OZ-9a): agregar sitio+planta a través del servicio
    repinta el árbol, y el resumen de la planta muestra el DPI con su procedencia en texto —un
    PNG sin resolución embebida queda 'asumido', nunca presentado como medido (ADR-006)."""
    repo = RepositorioFalso()
    service = ProjectService(StoreFalso(tmp_path / "projects"), repo)
    ventana = MainWindow(project_service=service, settings_repository=repo, app_version="1.2.3")
    service.new_project()
    service.add_site("Sede central")
    sid = service.state().project.sites[0].id  # type: ignore[union-attr]
    plano = tmp_path / "planta.png"
    plano.write_bytes(_png_minimo())

    service.add_floor(sid, "Planta baja", 0, plano)

    arbol = ventana._arbol  # type: ignore[attr-defined]
    assert arbol._tree.topLevelItemCount() == 1, "el sitio debe aparecer en el árbol"
    site_item = arbol._tree.topLevelItem(0)
    assert site_item.childCount() == 1, "la planta debe colgar del sitio"

    arbol._tree.setCurrentItem(site_item.child(0))  # seleccionar la planta
    resumen = arbol._resumen.text()
    assert "640 x 480 px" in resumen
    assert "asumido" in resumen and "del archivo" not in resumen  # DPI honesto
    ventana.close()


def _png_real(w: int = 120, h: int = 80) -> bytes:
    """PNG realmente decodificable (vía QImage), para el visor: pasa read_plan_image Y QPixmap."""
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(0xFF8080)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def test_pixmap_desde_bytes_conserva_dimensiones(qt_app: QApplication) -> None:
    """C1: el visor arma el pixmap del plano desde los bytes del asset."""
    pm = QPixmap()
    assert pm.loadFromData(_png_real(120, 80))
    assert (pm.width(), pm.height()) == (120, 80)


def test_calibracion_captura_coordenadas_de_imagen_invariantes_al_zoom(
    qt_app: QApplication,
) -> None:
    """C3: los puntos de calibración se toman en píxeles de imagen (escena), no de pantalla:
    `mapToScene` recupera el mismo punto de imagen a cualquier zoom."""
    lienzo = _Lienzo(on_two_points=lambda a, b: None)
    pm = QPixmap()
    pm.loadFromData(_png_real(400, 300))
    lienzo.mostrar(pm, 0.0)
    lienzo.resize(200, 150)

    punto_imagen = QPointF(120.0, 90.0)
    recuperado_fit = lienzo.mapToScene(lienzo.mapFromScene(punto_imagen))
    lienzo.scale(4.0, 4.0)  # el usuario hace zoom
    recuperado_zoom = lienzo.mapToScene(lienzo.mapFromScene(punto_imagen))

    assert recuperado_fit.x() == pytest.approx(120.0, abs=1.0)
    assert recuperado_fit.y() == pytest.approx(90.0, abs=1.0)
    # Mismo punto de imagen tras el zoom: la escena sigue en píxeles de imagen.
    assert recuperado_zoom.x() == pytest.approx(120.0, abs=1.0)
    assert recuperado_zoom.y() == pytest.approx(90.0, abs=1.0)


def test_seleccionar_planta_muestra_el_plano_y_calibrar_actualiza_la_escala(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Cableado OZ-36: seleccionar una planta carga su plano en el visor; el resumen de escala
    muestra 'Sin calibrar' y, tras calibrar, la escala CON su incertidumbre (siempre)."""
    repo = RepositorioFalso()
    service = ProjectService(StoreFalso(tmp_path / "projects"), repo)
    ventana = MainWindow(project_service=service, settings_repository=repo, app_version="1.2.3")
    service.new_project()
    service.add_site("Sede")
    sid = service.state().project.sites[0].id  # type: ignore[union-attr]
    plano = tmp_path / "planta.png"
    plano.write_bytes(_png_real(400, 300))
    service.add_floor(sid, "Baja", 0, plano)
    fid = service.state().project.sites[0].floors[0].id  # type: ignore[union-attr]

    arbol = ventana._arbol  # type: ignore[attr-defined]
    site_item = arbol._tree.topLevelItem(0)
    arbol._tree.setCurrentItem(site_item.child(0))  # seleccionar la planta -> carga el plano

    escala = ventana._proyecto._visor._escala  # type: ignore[attr-defined]
    assert "Sin calibrar" in escala.text()

    service.set_floor_calibration(fid, (10.0, 10.0), (110.0, 10.0), 5.0)

    texto = ventana._proyecto._visor._escala.text()  # type: ignore[attr-defined]
    assert "Escala" in texto
    assert "±" in texto and "%" in texto, (
        "la incertidumbre debe mostrarse siempre, no solo si es alta"
    )
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

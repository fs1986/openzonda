"""Contrato del ciclo de vida del proyecto (OZ-8), verificado sin Qt ni infraestructura.

El servicio se prueba contra un `FakeProjectStore` en memoria: aquí importa la LÓGICA del
documento (dirty, recientes, orden de operaciones, manejo de errores por listener), no cómo
se serializa un `.wifisurvey` —eso lo cubre el test del adapter de `persistence`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from application.project_service import (
    DEFAULT_PROJECT_NAME,
    ProjectErrorKind,
    ProjectService,
    ProjectState,
    ProjectStoreError,
    ProjectWorkspace,
)
from application.settings import AppSettings
from domain.measurement import Provenance
from domain.project import Project


class FakeSettingsRepo:
    def __init__(self) -> None:
        self._settings = AppSettings()

    def load(self) -> AppSettings:
        return self._settings

    def save(self, settings: AppSettings) -> None:
        self._settings = settings


class FakeProjectStore:
    """Store en memoria. `save` toca el archivo destino para que `Path.exists()` (recientes
    rotos) refleje la realidad, pero el contenido del proyecto vive en un dict."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._n = 0
        self.saved: dict[Path, Project] = {}
        self.discarded: list[ProjectWorkspace] = []
        self.orphans_cleaned = 0
        self.assets: dict[str, bytes] = {}

    def create_empty(self) -> ProjectWorkspace:
        self._n += 1
        ws_dir = self._root / f"ws{self._n}"
        ws_dir.mkdir(parents=True, exist_ok=True)
        return ProjectWorkspace(working_dir=ws_dir)

    def open(self, source: Path) -> tuple[ProjectWorkspace, Project]:
        source = Path(source).resolve()
        if source not in self.saved:
            raise ProjectStoreError(ProjectErrorKind.CORRUPT, f"no legible: {source}")
        self._n += 1
        ws_dir = self._root / f"ws{self._n}"
        ws_dir.mkdir(parents=True, exist_ok=True)
        return ProjectWorkspace(working_dir=ws_dir), self.saved[source]

    def save(self, workspace: ProjectWorkspace, project: Project, destination: Path) -> None:
        destination = Path(destination).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fake-wifisurvey")
        self.saved[destination] = project

    def store_asset(self, workspace: ProjectWorkspace, data: bytes, extension: str) -> str:
        sha = hashlib.sha256(data).hexdigest()
        self.assets[sha] = data
        return sha

    def read_asset(self, workspace: ProjectWorkspace, sha256: str) -> bytes:
        if sha256 not in self.assets:
            raise ProjectStoreError(ProjectErrorKind.CORRUPT, f"asset ausente: {sha256}")
        return self.assets[sha256]

    def discard(self, workspace: ProjectWorkspace) -> None:
        self.discarded.append(workspace)

    def cleanup_orphans(self) -> int:
        return self.orphans_cleaned


class DeferredExecutor:
    """Executor de test que NO ejecuta en el acto: encola el trabajo y lo corre cuando el
    test llama `run_all()`. Simula el worker para verificar `busy` y la cancelación."""

    def __init__(self) -> None:
        self.pending: list[tuple] = []

    def submit(self, work, on_done, on_error) -> None:
        self.pending.append((work, on_done, on_error))

    def run_all(self) -> None:
        while self.pending:
            work, on_done, on_error = self.pending.pop(0)
            try:
                resultado = work()
            except Exception as error:
                on_error(error)
            else:
                on_done(resultado)


class CapturingListener:
    def __init__(self) -> None:
        self.states: list[ProjectState] = []
        self.errors: list[ProjectStoreError] = []

    def on_state(self, state: ProjectState) -> None:
        self.states.append(state)

    def on_error(self, error: ProjectStoreError) -> None:
        self.errors.append(error)


@pytest.fixture
def entorno(tmp_path: Path) -> tuple[ProjectService, FakeProjectStore, CapturingListener]:
    store = FakeProjectStore(tmp_path / "workspaces")
    service = ProjectService(store, FakeSettingsRepo())
    listener = CapturingListener()
    service.add_listener(listener)
    return service, store, listener


def test_proyecto_nuevo_queda_dirty_y_sin_ruta(entorno) -> None:
    service, _store, listener = entorno
    service.new_project()

    estado = service.state()
    assert estado.has_project is True
    assert estado.name == DEFAULT_PROJECT_NAME
    assert estado.path is None
    assert estado.dirty is True
    assert listener.states[-1] == estado  # el listener fue notificado


def test_add_listener_recibe_el_estado_inicial(entorno) -> None:
    _service, _store, listener = entorno
    assert listener.states[0].has_project is False  # sin proyecto al arrancar


def test_save_sin_ruta_es_error_de_programacion(entorno) -> None:
    service, _store, _listener = entorno
    service.new_project()
    with pytest.raises(ValueError):
        service.save()  # el ViewModel debe usar save_as() cuando no hay ruta


def test_guardar_como_persiste_y_limpia_dirty(entorno, tmp_path: Path) -> None:
    service, store, _listener = entorno
    service.new_project()
    destino = tmp_path / "estudio.wifisurvey"

    service.save_as(destino)

    estado = service.state()
    assert estado.dirty is False
    assert estado.path == destino
    assert store.saved[destino.resolve()].name == DEFAULT_PROJECT_NAME
    assert estado.recent[0].path == destino.resolve()
    assert estado.recent[0].available is True


def test_guardar_tras_guardar_como_usa_la_misma_ruta(entorno, tmp_path: Path) -> None:
    service, store, _listener = entorno
    service.new_project()
    destino = tmp_path / "estudio.wifisurvey"
    service.save_as(destino)

    service.rename("Torre Norte")
    assert service.is_dirty is True
    service.save()  # ya hay ruta: no debe requerir save_as

    assert service.is_dirty is False
    assert store.saved[destino.resolve()].name == "Torre Norte"


def test_abrir_proyecto_existente(entorno, tmp_path: Path) -> None:
    service, _store, _listener = entorno
    destino = tmp_path / "estudio.wifisurvey"
    service.new_project()
    service.rename("Planta Baja")
    service.save_as(destino)
    service.close_project()

    service.open_project(destino)

    estado = service.state()
    assert estado.has_project is True
    assert estado.name == "Planta Baja"
    assert estado.path == destino
    assert estado.dirty is False


def test_abrir_archivo_inexistente_emite_error_not_found(entorno, tmp_path: Path) -> None:
    service, _store, listener = entorno
    service.open_project(tmp_path / "no-existe.wifisurvey")

    assert listener.errors[-1].kind is ProjectErrorKind.NOT_FOUND
    assert service.has_project is False  # el estado no cambió


def test_abrir_archivo_corrupto_emite_error_sin_relanzar(entorno, tmp_path: Path) -> None:
    service, _store, listener = entorno
    corrupto = tmp_path / "roto.wifisurvey"
    corrupto.write_bytes(b"no soy un contenedor")

    service.open_project(corrupto)  # no debe lanzar

    assert listener.errors[-1].kind is ProjectErrorKind.CORRUPT
    assert service.has_project is False


def test_renombrar_marca_dirty(entorno) -> None:
    service, _store, _listener = entorno
    service.new_project()
    service.rename("Nuevo nombre")
    assert service.state().name == "Nuevo nombre"
    assert service.is_dirty is True


def test_cerrar_libera_el_workspace(entorno) -> None:
    service, store, _listener = entorno
    service.new_project()
    ws = service._current.workspace  # type: ignore[union-attr]
    service.close_project()

    assert ws in store.discarded
    assert service.has_project is False


def test_nuevo_proyecto_descarta_el_anterior(entorno) -> None:
    service, store, _listener = entorno
    service.new_project()
    primero = service._current.workspace  # type: ignore[union-attr]
    service.new_project()

    assert primero in store.discarded


def test_recientes_orden_dedup_y_limite(entorno, tmp_path: Path) -> None:
    service, _store, _listener = entorno
    # Guardar 12 proyectos distintos; recientes se limita a 10, más reciente primero.
    rutas = [tmp_path / f"p{i}.wifisurvey" for i in range(12)]
    for ruta in rutas:
        service.new_project()
        service.save_as(ruta)

    recientes = [e.path for e in service.state().recent]
    assert len(recientes) == 10
    assert recientes[0] == rutas[-1].resolve()  # el último guardado, primero
    assert rutas[0].resolve() not in recientes  # el más viejo se cayó del tope

    # Reabrir uno viejo lo mueve al frente sin duplicar.
    service.close_project()
    service.open_project(rutas[5])
    recientes = [e.path for e in service.state().recent]
    assert recientes[0] == rutas[5].resolve()
    assert recientes.count(rutas[5].resolve()) == 1


def test_reciente_roto_se_marca_no_disponible_no_se_borra(entorno, tmp_path: Path) -> None:
    service, _store, _listener = entorno
    ruta = tmp_path / "movido.wifisurvey"
    service.new_project()
    service.save_as(ruta)
    ruta.unlink()  # el usuario movió/borró el archivo

    recientes = service.state().recent
    assert recientes[0].path == ruta.resolve()
    assert recientes[0].available is False  # sigue en la lista, marcado no disponible


def test_remove_recent_es_explicito(entorno, tmp_path: Path) -> None:
    service, _store, _listener = entorno
    ruta = tmp_path / "quitar.wifisurvey"
    service.new_project()
    service.save_as(ruta)
    assert len(service.state().recent) == 1

    service.remove_recent(ruta)
    assert service.state().recent == ()


# -------------------------------------------------------- edición del árbol Site→Floor (OZ-9a)


def _png_valido(marca: bytes = b"x", *, width: int = 100, height: int = 80) -> bytes:
    """PNG mínimo válido sin pHYs (DPI se asume 96, ESTIMATED). `marca` varía el contenido."""
    import struct
    import zlib

    def chunk(tipo: bytes, datos: bytes) -> bytes:
        crc = zlib.crc32(tipo + datos) & 0xFFFFFFFF
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(marca)) + chunk(b"IEND", b"")


def _proyecto_abierto(entorno) -> ProjectService:
    service, _store, _listener = entorno
    service.new_project()
    return service


def test_add_site_agrega_y_marca_dirty(entorno) -> None:
    service = _proyecto_abierto(entorno)
    service.add_site("Sede central")

    sitios = service.state().project.sites
    assert [s.name for s in sitios] == ["Sede central"]
    assert service.is_dirty is True


def test_add_site_nombre_duplicado_emite_error_sin_cambiar(entorno) -> None:
    service, _store, listener = entorno
    service.new_project()
    service.add_site("Sede")
    service.add_site("Sede")  # duplicado

    assert listener.errors[-1].kind is ProjectErrorKind.INVALID_EDIT
    assert len(service.state().project.sites) == 1


def test_rename_y_remove_site(entorno) -> None:
    service = _proyecto_abierto(entorno)
    service.add_site("Vieja")
    sid = service.state().project.sites[0].id

    service.rename_site(sid, "Nueva")
    assert service.state().project.sites[0].name == "Nueva"

    service.remove_site(sid)
    assert service.state().project.sites == ()


def test_add_floor_carga_el_plano_con_dpi_honesto(entorno, tmp_path: Path) -> None:
    service, store, _listener = entorno
    service.new_project()
    service.add_site("Sede")
    sid = service.state().project.sites[0].id
    plano = tmp_path / "planta.png"
    datos = _png_valido(b"planta baja")
    plano.write_bytes(datos)

    service.add_floor(sid, "Planta baja", 0, plano)

    floors = service.state().project.sites[0].floors
    assert len(floors) == 1
    plan = floors[0].plan
    assert plan.width_px == 100 and plan.height_px == 80
    assert plan.dpi.provenance is Provenance.ESTIMATED  # PNG sin pHYs -> DPI asumido
    # El asset se almacenó content-addressed por el hash de su contenido.
    import hashlib

    assert plan.asset_sha256 == hashlib.sha256(datos).hexdigest()
    assert store.assets[plan.asset_sha256] == datos
    assert service.is_dirty is True


def test_add_floor_con_imagen_invalida_emite_invalid_plan(entorno, tmp_path: Path) -> None:
    service, _store, listener = entorno
    service.new_project()
    service.add_site("Sede")
    sid = service.state().project.sites[0].id
    no_imagen = tmp_path / "renombrado.png"
    no_imagen.write_bytes(b"esto no es una imagen")

    service.add_floor(sid, "Planta baja", 0, no_imagen)

    assert listener.errors[-1].kind is ProjectErrorKind.INVALID_PLAN
    assert service.state().project.sites[0].floors == ()  # no se creó la planta


def test_add_floor_nivel_duplicado_emite_error(entorno, tmp_path: Path) -> None:
    service, _store, listener = entorno
    service.new_project()
    service.add_site("Sede")
    sid = service.state().project.sites[0].id
    plano = tmp_path / "p.png"
    plano.write_bytes(_png_valido())

    service.add_floor(sid, "Baja", 0, plano)
    service.add_floor(sid, "Otra", 0, plano)  # mismo nivel

    assert listener.errors[-1].kind is ProjectErrorKind.INVALID_EDIT
    assert len(service.state().project.sites[0].floors) == 1


def test_set_floor_plan_reemplaza_el_plano(entorno, tmp_path: Path) -> None:
    service, _store, _listener = entorno
    service.new_project()
    service.add_site("Sede")
    sid = service.state().project.sites[0].id
    p1 = tmp_path / "p1.png"
    p1.write_bytes(_png_valido(b"primero"))
    service.add_floor(sid, "Baja", 0, p1)
    fid = service.state().project.sites[0].floors[0].id
    sha_original = service.state().project.sites[0].floors[0].plan.asset_sha256

    p2 = tmp_path / "p2.png"
    p2.write_bytes(_png_valido(b"segundo-distinto", width=200, height=150))
    service.set_floor_plan(fid, p2)

    plan = service.state().project.sites[0].floors[0].plan
    assert plan.asset_sha256 != sha_original
    assert (plan.width_px, plan.height_px) == (200, 150)


def test_rename_y_remove_floor(entorno, tmp_path: Path) -> None:
    service, _store, _listener = entorno
    service.new_project()
    service.add_site("Sede")
    sid = service.state().project.sites[0].id
    plano = tmp_path / "p.png"
    plano.write_bytes(_png_valido())
    service.add_floor(sid, "Baja", 0, plano)
    fid = service.state().project.sites[0].floors[0].id

    service.rename_floor(fid, "Planta técnica")
    assert service.state().project.sites[0].floors[0].name == "Planta técnica"

    service.remove_floor(fid)
    assert service.state().project.sites[0].floors == ()


# ---------------------------------------------------------- worker / cancelación (OZ-34)


def _servicio_diferido(tmp_path: Path) -> tuple[ProjectService, FakeProjectStore, DeferredExecutor]:
    store = FakeProjectStore(tmp_path / "workspaces")
    executor = DeferredExecutor()
    service = ProjectService(store, FakeSettingsRepo(), executor=executor)
    return service, store, executor


def test_abrir_marca_busy_hasta_que_el_worker_termina(tmp_path: Path) -> None:
    service, store, executor = _servicio_diferido(tmp_path)
    destino = tmp_path / "p.wifisurvey"
    # Sembrar un proyecto que el store pueda abrir.
    ws = store.create_empty()
    store.save(ws, Project(name="Sembrado"), destino)

    service.open_project(destino)
    assert service.is_busy is True  # el worker aún no corrió
    assert service.state().busy is True

    executor.run_all()
    assert service.is_busy is False
    assert service.has_project is True
    assert service.state().name == "Sembrado"


def test_cerrar_durante_una_apertura_descarta_el_resultado(tmp_path: Path) -> None:
    service, store, executor = _servicio_diferido(tmp_path)
    destino = tmp_path / "p.wifisurvey"
    ws = store.create_empty()
    store.save(ws, Project(name="Sembrado"), destino)

    service.open_project(destino)  # encolado, no corrió
    service.close_project()  # cancela: la generación avanza
    executor.run_all()  # el worker termina tarde

    assert service.has_project is False, "el resultado obsoleto no debe abrir el proyecto"
    assert service.is_busy is False
    # El working dir que abrió la operación obsoleta se limpió (no se filtra).
    assert len(store.discarded) >= 1


def test_abrir_otro_mientras_abre_descarta_el_primero(tmp_path: Path) -> None:
    service, store, executor = _servicio_diferido(tmp_path)
    a = tmp_path / "a.wifisurvey"
    b = tmp_path / "b.wifisurvey"
    ws = store.create_empty()
    store.save(ws, Project(name="A"), a)
    ws2 = store.create_empty()
    store.save(ws2, Project(name="B"), b)

    service.open_project(a)
    service.open_project(b)  # segunda apertura: la primera queda obsoleta
    executor.run_all()

    assert service.has_project is True
    assert service.state().name == "B", "debe quedar la última apertura, no la obsoleta"


def test_guardar_corre_en_el_worker_y_marca_busy(tmp_path: Path) -> None:
    service, _store, executor = _servicio_diferido(tmp_path)
    service.new_project()  # síncrono (rápido)
    service.rename("Editado")
    assert service.is_dirty is True

    service.save_as(tmp_path / "x.wifisurvey")
    assert service.is_busy is True  # el guardado está encolado en el worker
    executor.run_all()

    assert service.is_busy is False
    assert service.is_dirty is False

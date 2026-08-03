"""ViewModel de la shell, verificado headless (sin QApplication) — DoD de OZ-8.

Se comprueba la lógica de presentación: título con marca de *dirty*, el flujo de cambios sin
guardar (preguntar → guardar/descartar/cancelar), la derivación a *guardar como* cuando no
hay ruta, y que los errores del servicio se muestran. No se instancia ningún widget.
"""

from __future__ import annotations

from pathlib import Path

from application.project_service import ProjectErrorKind, ProjectState, ProjectStoreError
from desktop.shell_viewmodel import DiscardChoice, ShellViewModel


class FakeService:
    """Servicio de proyecto espía: registra llamadas y notifica al listener como el real."""

    def __init__(self, state: ProjectState | None = None) -> None:
        self._state = state or ProjectState(False, None, None, False)
        self.calls: list[object] = []
        self._listener = None

    # API que consume el ViewModel
    def add_listener(self, listener) -> None:
        self._listener = listener
        listener.on_state(self._state)

    def state(self) -> ProjectState:
        return self._state

    @property
    def is_dirty(self) -> bool:
        return self._state.dirty

    def new_project(self) -> None:
        self.calls.append("new")
        self._emit(ProjectState(True, "Proyecto sin título", None, True))

    def open_project(self, path: Path) -> None:
        self.calls.append(("open", path))
        self._emit(ProjectState(True, "Abierto", path, False))

    def save(self) -> None:
        self.calls.append("save")
        self._emit(ProjectState(True, self._state.name, self._state.path, False))

    def save_as(self, path: Path) -> None:
        self.calls.append(("save_as", path))
        self._emit(ProjectState(True, self._state.name or "Nuevo", path, False))

    def close_project(self) -> None:
        self.calls.append("close")
        self._emit(ProjectState(False, None, None, False))

    def rename(self, name: str) -> None:
        self.calls.append(("rename", name))
        self._emit(ProjectState(True, name, self._state.path, True))

    def remove_recent(self, path: Path) -> None:
        self.calls.append(("remove_recent", path))

    # helpers de test
    def emit_error(self, kind: ProjectErrorKind, message: str) -> None:
        assert self._listener is not None
        self._listener.on_error(ProjectStoreError(kind, message))

    def _emit(self, state: ProjectState) -> None:
        self._state = state
        assert self._listener is not None
        self._listener.on_state(state)


class Espia:
    """Fábrica de callbacks que registran invocaciones y devuelven un valor programado."""

    def __init__(self, retorno=None) -> None:
        self.retorno = retorno
        self.llamadas = 0

    def __call__(self, *args):
        self.llamadas += 1
        return self.retorno


def _vm(
    service: FakeService,
    *,
    open_path=None,
    save_path=None,
    discard=DiscardChoice.DISCARD,
    on_error=None,
) -> tuple[ShellViewModel, dict[str, Espia]]:
    espias = {
        "open": Espia(open_path),
        "save": Espia(save_path),
        "discard": Espia(discard),
        "error": on_error or Espia(),
    }
    vm = ShellViewModel(
        service,
        ask_open_path=espias["open"],
        ask_save_path=espias["save"],
        confirm_discard=espias["discard"],
        show_error=espias["error"],
    )
    return vm, espias


def test_nuevo_sin_cambios_no_pregunta(tmp_path: Path) -> None:
    service = FakeService()
    vm, espias = _vm(service)
    vm.request_new()
    assert "new" in service.calls
    assert espias["discard"].llamadas == 0


def test_titulo_marca_dirty(tmp_path: Path) -> None:
    service = FakeService()
    vm, _ = _vm(service)
    vm.request_new()  # queda dirty
    assert vm.window_title.startswith("• ")
    assert "Proyecto sin título" in vm.window_title


def test_titulo_sin_proyecto_es_solo_la_app() -> None:
    vm, _ = _vm(FakeService())
    assert vm.window_title == "OpenZonda"


def test_nuevo_con_cambios_y_cancelar_no_hace_nada() -> None:
    service = FakeService(ProjectState(True, "Actual", None, True))
    vm, espias = _vm(service, discard=DiscardChoice.CANCEL)
    vm.request_new()
    assert espias["discard"].llamadas == 1
    assert "new" not in service.calls  # se abortó


def test_nuevo_con_cambios_y_descartar_procede() -> None:
    service = FakeService(ProjectState(True, "Actual", None, True))
    vm, _ = _vm(service, discard=DiscardChoice.DISCARD)
    vm.request_new()
    assert "new" in service.calls


def test_guardar_sin_ruta_deriva_a_guardar_como(tmp_path: Path) -> None:
    service = FakeService(ProjectState(True, "Actual", None, True))
    destino = tmp_path / "x.wifisurvey"
    vm, espias = _vm(service, save_path=destino)
    assert vm.request_save() is True
    assert ("save_as", destino) in service.calls
    assert espias["save"].llamadas == 1


def test_guardar_como_cancelado_no_guarda() -> None:
    service = FakeService(ProjectState(True, "Actual", None, True))
    vm, _ = _vm(service, save_path=None)  # el diálogo se cancela
    assert vm.request_save() is False
    assert "save" not in service.calls
    assert not any(isinstance(c, tuple) and c[0] == "save_as" for c in service.calls)


def test_guardar_con_ruta_usa_save_directo(tmp_path: Path) -> None:
    ruta = tmp_path / "y.wifisurvey"
    service = FakeService(ProjectState(True, "Actual", ruta, True))
    vm, _ = _vm(service)
    assert vm.request_save() is True
    assert "save" in service.calls


def test_abrir_con_ruta_no_usa_dialogo(tmp_path: Path) -> None:
    ruta = tmp_path / "z.wifisurvey"
    service = FakeService()
    vm, espias = _vm(service)
    vm.request_open(ruta)
    assert ("open", ruta) in service.calls
    assert espias["open"].llamadas == 0


def test_abrir_sin_ruta_pregunta_al_dialogo(tmp_path: Path) -> None:
    ruta = tmp_path / "elegido.wifisurvey"
    service = FakeService()
    vm, espias = _vm(service, open_path=ruta)
    vm.request_open()
    assert espias["open"].llamadas == 1
    assert ("open", ruta) in service.calls


def test_abrir_con_cambios_pendientes_pregunta_primero() -> None:
    service = FakeService(ProjectState(True, "Actual", None, True))
    vm, espias = _vm(service, open_path=Path("a.wifisurvey"), discard=DiscardChoice.CANCEL)
    vm.request_open()
    assert espias["discard"].llamadas == 1
    assert not any(isinstance(c, tuple) and c[0] == "open" for c in service.calls)


def test_error_del_servicio_se_muestra() -> None:
    service = FakeService()
    errores: list[tuple[str, str]] = []
    _vm(service, on_error=lambda t, m: errores.append((t, m)))  # el vm se registra solo
    service.emit_error(ProjectErrorKind.CORRUPT, "archivo dañado")
    assert errores and "dañado" in errores[0][1]


def test_can_close_window_respeta_cancelar() -> None:
    service = FakeService(ProjectState(True, "Actual", None, True))
    vm, _ = _vm(service, discard=DiscardChoice.CANCEL)
    assert vm.can_close_window() is False


def test_can_close_window_descarta_si_el_usuario_lo_elige() -> None:
    service = FakeService(ProjectState(True, "Actual", None, True))
    vm, _ = _vm(service, discard=DiscardChoice.DISCARD)
    assert vm.can_close_window() is True


def test_set_on_changed_recibe_estado_actual_y_actualizaciones() -> None:
    service = FakeService()
    vm, _ = _vm(service)
    vistos: list[ProjectState] = []
    vm.set_on_changed(vistos.append)
    assert len(vistos) == 1  # estado inicial
    vm.request_new()
    assert vistos[-1].has_project is True


def test_renombrar_delega_en_el_servicio() -> None:
    service = FakeService(ProjectState(True, "Actual", None, False))
    vm, _ = _vm(service)
    vm.request_rename("Torre Sur")
    assert ("rename", "Torre Sur") in service.calls

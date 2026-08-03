"""ViewModel de la shell de proyectos (OZ-8). El estado de UI vive aquí, no en los widgets.

Se prueba **headless**, sin `QApplication`: el ViewModel no importa Qt. Las interacciones que
sí son de la vista —elegir un archivo, confirmar que se descartan cambios, mostrar un error—
se inyectan como callbacks, así el flujo (dirty → preguntar → guardar/descartar/cancelar,
guardar-como cuando no hay ruta, recientes) se verifica sin pantalla.

La ventana Qt (`main_window.py`) provee los callbacks reales (`QFileDialog`, `QMessageBox`) y
se suscribe a `on_changed` para repintarse. Ningún callback bloquea el modelo: cuando el I/O
se mueva a un worker (deuda OZ-34), el ViewModel no cambia.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto
from pathlib import Path

from application.project_service import (
    ProjectErrorKind,
    ProjectService,
    ProjectState,
    ProjectStoreError,
)

APP_NAME = "OpenZonda"

_ERROR_TITLES = {
    ProjectErrorKind.INVALID_PLAN: "No se pudo cargar el plano",
    ProjectErrorKind.INVALID_EDIT: "No se pudo editar el proyecto",
}
_ERROR_TITLE_DEFAULT = "No se pudo abrir el proyecto"


class DiscardChoice(Enum):
    """Respuesta del usuario ante cambios sin guardar."""

    SAVE = auto()
    DISCARD = auto()
    CANCEL = auto()


class ShellViewModel:
    """Traduce las acciones de la shell en operaciones del `ProjectService` y expone el
    estado que la vista pinta. Implementa `ProjectServiceListener`."""

    def __init__(
        self,
        service: ProjectService,
        *,
        ask_open_path: Callable[[], Path | None],
        ask_save_path: Callable[[], Path | None],
        confirm_discard: Callable[[], DiscardChoice],
        show_error: Callable[[str, str], None],
    ) -> None:
        self._service = service
        self._ask_open_path = ask_open_path
        self._ask_save_path = ask_save_path
        self._confirm_discard = confirm_discard
        self._show_error = show_error
        self._state: ProjectState = service.state()
        self._on_changed: Callable[[ProjectState], None] | None = None
        service.add_listener(self)

    # ------------------------------------------------------------- observador de la vista

    def set_on_changed(self, callback: Callable[[ProjectState], None]) -> None:
        self._on_changed = callback
        callback(self._state)

    @property
    def state(self) -> ProjectState:
        return self._state

    @property
    def window_title(self) -> str:
        s = self._state
        if not s.has_project:
            return APP_NAME
        marca = "• " if s.dirty else ""
        return f"{marca}{s.name} — {APP_NAME}"

    # --------------------------------------------------------- ProjectServiceListener

    def on_state(self, state: ProjectState) -> None:
        self._state = state
        if self._on_changed is not None:
            self._on_changed(state)

    def on_error(self, error: ProjectStoreError) -> None:
        titulo = _ERROR_TITLES.get(error.kind, _ERROR_TITLE_DEFAULT)
        self._show_error(titulo, error.message)

    # --------------------------------------------------------------------- comandos

    def request_new(self) -> None:
        if not self._resolver_cambios_pendientes():
            return
        self._service.new_project()

    def request_open(self, path: Path | None = None) -> None:
        if not self._resolver_cambios_pendientes():
            return
        if path is None:
            path = self._ask_open_path()
            if path is None:
                return
        self._service.open_project(Path(path))

    def request_save(self) -> bool:
        """Guarda; si el documento no tiene ruta, deriva a *guardar como*. Devuelve si guardó."""
        if not self._state.has_project:
            return False
        if self._state.path is None:
            return self.request_save_as()
        self._service.save()
        return True

    def request_save_as(self) -> bool:
        if not self._state.has_project:
            return False
        destino = self._ask_save_path()
        if destino is None:
            return False
        self._service.save_as(Path(destino))
        return True

    def request_close_project(self) -> None:
        if not self._resolver_cambios_pendientes():
            return
        self._service.close_project()

    def request_rename(self, name: str) -> None:
        if name.strip():
            self._service.rename(name)

    def request_remove_recent(self, path: Path) -> None:
        self._service.remove_recent(Path(path))

    def can_close_window(self) -> bool:
        """Para el `closeEvent`: `False` = el usuario canceló el cierre."""
        return self._resolver_cambios_pendientes()

    # --------------------------------------------------------------------- internos

    def _resolver_cambios_pendientes(self) -> bool:
        """Si hay cambios sin guardar, pregunta. Devuelve `False` solo si el usuario cancela."""
        if not self._service.is_dirty:
            return True
        eleccion = self._confirm_discard()
        if eleccion is DiscardChoice.CANCEL:
            return False
        if eleccion is DiscardChoice.SAVE:
            return self.request_save()  # si el guardado se cancela, se aborta la acción
        return True  # DISCARD

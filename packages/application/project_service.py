"""Ciclo de vida del proyecto como documento (caso de uso F1.4, OZ-8).

Modelo **documento** (ADR-010): el `.wifisurvey` es el archivo del usuario. Abrir lo extrae
a un working dir de trabajo; guardar re-empaqueta atómicamente sobre el destino. Este módulo
es la lógica pura del ciclo de vida —nuevo/abrir/guardar/cerrar, estado *dirty*, recientes—
sin Qt ni infraestructura: se prueba headless (`tests/unit/test_project_service.py`).

## Preparado para mover el I/O a un worker sin rediseño (deuda OZ-34)

Hoy el I/O de archivo corre en el hilo que llama. Cuando entre plano/captura (payloads
grandes) habrá que moverlo a un worker con cancelación. Para que ese cambio **no** obligue a
rediseñar ni el servicio ni los ViewModels, las operaciones (`new_project`, `open_project`,
`save`, …) **no devuelven el documento**: devuelven `None` y el resultado se comunica a los
listeners (`on_state` / `on_error`). Meter el worker solo cambia *cuándo* se emite la
notificación, no la firma que la UI consume. Ningún llamante asume sincronía en el retorno.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Protocol

from application.settings import SettingsRepository
from domain.project import Project

DEFAULT_PROJECT_NAME = "Proyecto sin título"
RECENT_LIMIT = 10


# --------------------------------------------------------------------------- puerto


@dataclass(frozen=True, slots=True)
class ProjectWorkspace:
    """Handle opaco de un proyecto abierto. Para la UI es opaco; el store sabe qué hay
    detrás (un working dir con la base extraída). Se pasa de vuelta al store tal cual."""

    working_dir: Path


class ProjectErrorKind(Enum):
    """Por qué falló abrir un `.wifisurvey`. Determina qué puede hacer el usuario."""

    NOT_A_PROJECT = auto()  # no es un contenedor OpenZonda
    TOO_NEW = auto()  # lo escribió una versión más nueva
    CORRUPT = auto()  # archivo dañado
    HOSTILE = auto()  # construido para atacar
    NOT_FOUND = auto()  # el archivo ya no existe (reciente roto)
    IO = auto()  # cualquier otro fallo de E/S


class ProjectStoreError(Exception):
    """Fallo de una operación del store, con causa clasificada y mensaje para el usuario."""

    def __init__(self, kind: ProjectErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


class ProjectStore(Protocol):
    """Port de persistencia del documento de proyecto. Su adaptador (`persistence`) usa el
    contenedor `.wifisurvey` y SQLite; el caso de uso solo ve dominio y rutas.

    Síncrono a propósito: cuando el I/O se mueva a un worker, el worker envolverá estas
    llamadas sin cambiar su firma (ver docstring del módulo).
    """

    def create_empty(self) -> ProjectWorkspace:
        """Crea un working dir con una base nueva ya migrada (proyecto aún en memoria)."""
        ...

    def open(self, source: Path) -> tuple[ProjectWorkspace, Project]:
        """Extrae y valida `source`, carga su proyecto. Lanza `ProjectStoreError`."""
        ...

    def save(self, workspace: ProjectWorkspace, project: Project, destination: Path) -> None:
        """Persiste `project` en el working dir y re-empaqueta atómico sobre `destination`."""
        ...

    def discard(self, workspace: ProjectWorkspace) -> None:
        """Cierra el proyecto y borra su working dir. Idempotente."""
        ...

    def cleanup_orphans(self) -> int:
        """Barre working dirs de sesiones muertas. Devuelve cuántos limpió."""
        ...


# ----------------------------------------------------------------------- estado UI


@dataclass(frozen=True, slots=True)
class RecentEntry:
    """Un proyecto reciente. `available=False` = el archivo ya no está donde estaba.

    No se borra solo de la lista: el usuario debe *ver* que lo movió, no que la entrada
    desaparezca sin explicación. La UI lo marca con ícono + texto (nunca solo color).
    """

    path: Path
    available: bool


@dataclass(frozen=True, slots=True)
class ProjectState:
    """Foto inmutable del documento actual, para que la UI la pinte. El estado de UI vive
    en el ViewModel que consume esto; nunca en variables globales (CLAUDE.md)."""

    has_project: bool
    name: str | None
    path: Path | None
    dirty: bool
    recent: tuple[RecentEntry, ...] = ()


class ProjectServiceListener(Protocol):
    """Consumidor de los cambios del servicio. El ViewModel lo implementa."""

    def on_state(self, state: ProjectState) -> None: ...

    def on_error(self, error: ProjectStoreError) -> None: ...


# --------------------------------------------------------------------------- servicio


@dataclass
class _OpenProject:
    project: Project
    workspace: ProjectWorkspace
    path: Path | None  # None = nuevo sin guardar
    dirty: bool


class ProjectService:
    """Orquesta el ciclo de vida del documento. Puro: sin Qt, sin infraestructura."""

    def __init__(
        self,
        store: ProjectStore,
        settings_repository: SettingsRepository,
        *,
        default_name: str = DEFAULT_PROJECT_NAME,
    ) -> None:
        self._store = store
        self._settings = settings_repository
        self._default_name = default_name
        self._current: _OpenProject | None = None
        self._listeners: list[ProjectServiceListener] = []

    # ----------------------------------------------------------------- observabilidad

    def add_listener(self, listener: ProjectServiceListener) -> None:
        self._listeners.append(listener)
        listener.on_state(self.state())

    @property
    def is_dirty(self) -> bool:
        return self._current is not None and self._current.dirty

    @property
    def has_project(self) -> bool:
        return self._current is not None

    def state(self) -> ProjectState:
        actual = self._current
        return ProjectState(
            has_project=actual is not None,
            name=actual.project.name if actual else None,
            path=actual.path if actual else None,
            dirty=actual.dirty if actual else False,
            recent=self._recent_entries(),
        )

    # ------------------------------------------------------------------- operaciones

    def new_project(self) -> None:
        """Crea un proyecto vacío en un working dir nuevo. Queda *dirty* (sin guardar)."""
        self._discard_current()
        workspace = self._store.create_empty()
        proyecto = Project(name=self._default_name)
        self._current = _OpenProject(proyecto, workspace, path=None, dirty=True)
        self._emit_state()

    def open_project(self, source: Path) -> None:
        """Abre un `.wifisurvey`. En caso de fallo emite `on_error`, no relanza."""
        source = Path(source)
        if not source.exists():
            self._emit_error(
                ProjectStoreError(
                    ProjectErrorKind.NOT_FOUND,
                    f"El archivo ya no existe:\n{source}",
                )
            )
            return
        try:
            workspace, proyecto = self._store.open(source)
        except ProjectStoreError as error:
            self._emit_error(error)
            return
        self._discard_current()
        self._current = _OpenProject(proyecto, workspace, path=source, dirty=False)
        self._push_recent(source)
        self._emit_state()

    def save(self) -> None:
        """Guarda sobre la ruta actual. Requiere que ya haya una (si no, `save_as`)."""
        actual = self._require_open()
        if actual.path is None:
            raise ValueError("save() sin ruta asociada; el llamante debe usar save_as().")
        self._save_to(actual.path)

    def save_as(self, destination: Path) -> None:
        """Guarda a `destination` y la adopta como ruta del documento."""
        self._require_open()
        self._save_to(Path(destination))

    def close_project(self) -> None:
        """Cierra el documento y libera su working dir."""
        self._discard_current()
        self._emit_state()

    def rename(self, name: str) -> None:
        """Renombra el proyecto en memoria. Lo marca *dirty*; persiste al guardar."""
        actual = self._require_open()
        actual.project = actual.project.with_changes(name=name)
        actual.dirty = True
        self._emit_state()

    # ---------------------------------------------------------------------- internos

    def _save_to(self, destination: Path) -> None:
        actual = self._require_open()
        try:
            self._store.save(actual.workspace, actual.project, destination)
        except ProjectStoreError as error:
            self._emit_error(error)
            return
        actual.path = destination
        actual.dirty = False
        self._push_recent(destination)
        self._emit_state()

    def _require_open(self) -> _OpenProject:
        if self._current is None:
            raise ValueError("No hay ningún proyecto abierto.")
        return self._current

    def _discard_current(self) -> None:
        if self._current is not None:
            self._store.discard(self._current.workspace)
            self._current = None

    # -------------------------------------------------------------------- recientes

    def _recent_paths(self) -> list[Path]:
        crudos = getattr(self._settings.load(), "recent_projects", ())
        return [Path(p) for p in crudos]

    def _recent_entries(self) -> tuple[RecentEntry, ...]:
        return tuple(RecentEntry(path=p, available=p.exists()) for p in self._recent_paths())

    def _push_recent(self, path: Path) -> None:
        resuelto = self._resolve(path)
        anteriores = [self._resolve(p) for p in self._recent_paths()]
        nuevos = [resuelto] + [p for p in anteriores if p != resuelto]
        self._store_recent(nuevos[:RECENT_LIMIT])

    def remove_recent(self, path: Path) -> None:
        """Quita una entrada de recientes (acción explícita del usuario, nunca automática)."""
        objetivo = self._resolve(path)
        restantes = [p for p in (self._resolve(q) for q in self._recent_paths()) if p != objetivo]
        self._store_recent(restantes)
        self._emit_state()

    def _store_recent(self, paths: Sequence[Path]) -> None:
        # load fresco antes de guardar: la ventana persiste geometría por su lado con el
        # mismo patrón, así ninguno pisa el campo del otro (settings.save reemplaza todo).
        settings = self._settings.load()
        self._settings.save(settings.with_changes(recent_projects=tuple(str(p) for p in paths)))

    @staticmethod
    def _resolve(path: Path) -> Path:
        try:
            return Path(path).resolve()
        except OSError:
            return Path(path).absolute()

    # ------------------------------------------------------------------ notificación

    def _emit_state(self) -> None:
        estado = self.state()
        for listener in self._listeners:
            listener.on_state(estado)

    def _emit_error(self, error: ProjectStoreError) -> None:
        for listener in self._listeners:
            listener.on_error(error)

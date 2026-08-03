"""Ciclo de vida del proyecto como documento (caso de uso F1.4/OZ-8; worker en OZ-34).

Modelo **documento** (ADR-010): el `.wifisurvey` es el archivo del usuario. Abrir lo extrae
a un working dir de trabajo; guardar re-empaqueta atómicamente sobre el destino. Este módulo
es la lógica pura del ciclo de vida —nuevo/abrir/guardar/cerrar, estado *dirty*, recientes—
sin Qt ni infraestructura: se prueba headless (`tests/unit/test_project_service.py`).

## I/O fuera del hilo de la UI (OZ-34)

Abrir y guardar hacen I/O que puede tardar (extraer/empaquetar el contenedor con un plano
embebido). Se ejecutan a través de un `TaskExecutor` inyectado: inline en tests
(`SyncTaskExecutor`), en un worker de Qt en la app. Las operaciones **no devuelven el
documento**: el resultado se comunica por listener (`on_state` / `on_error`), así que mover
el I/O a un worker no cambió ninguna firma que la UI consuma.

**Cancelación (lógica, no aborta el I/O):** cada operación async lleva una *generación*. Si
el usuario cierra o cambia de proyecto mientras una corre, la generación avanza y el
resultado que llega tarde se **descarta** (y se limpia el working dir que hubiera abierto).
No se aborta el I/O a mitad —eso obligaría a re-tocar el contenedor endurecido de OZ-7—.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import Enum, auto
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from application.plan_image import PlanImageError, read_plan_image
from application.settings import SettingsRepository
from application.task_executor import SyncTaskExecutor, TaskExecutor
from domain.project import Floor, FloorPlan, Project, Site

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
    INVALID_PLAN = auto()  # el archivo de plano no es una imagen válida/aceptable (OZ-9a)
    INVALID_EDIT = auto()  # una edición del árbol viola una regla de dominio (OZ-9a)


class ProjectStoreError(Exception):
    """Fallo de una operación del store, con causa clasificada y mensaje para el usuario."""

    def __init__(self, kind: ProjectErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


class ProjectStore(Protocol):
    """Port de persistencia del documento de proyecto. Su adaptador (`persistence`) usa el
    contenedor `.wifisurvey` y SQLite; el caso de uso solo ve dominio y rutas.

    Síncrono a propósito: el worker (OZ-34) envuelve estas llamadas sin cambiar su firma.
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

    def store_asset(self, workspace: ProjectWorkspace, data: bytes, extension: str) -> str:
        """Guarda `data` en el working dir *content-addressed* (`assets/<sha256>.<ext>`) y
        devuelve su sha256. Dedup por hash: el mismo contenido no se reescribe. La extensión
        la fija el llamante a partir del formato detectado por contenido, no del nombre del
        archivo del usuario (OZ-9a)."""
        ...

    def read_asset(self, workspace: ProjectWorkspace, sha256: str) -> bytes:
        """Devuelve los bytes del asset por su hash. Lanza `ProjectStoreError` si no está:
        un plano referenciado que falta es un documento corrupto, no un caso normal."""
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
    busy: bool = False
    """Hay una operación de I/O (abrir/guardar) en curso: la UI deshabilita acciones."""
    project: Project | None = None
    """El proyecto abierto, para que la vista pinte su árbol Site→Floor y el resumen del
    plano (OZ-9a). Es `frozen`, así que exponerlo aquí es de solo lectura: la UI no puede
    mutarlo, solo pedir ediciones al servicio. `None` cuando no hay proyecto."""


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
        executor: TaskExecutor | None = None,
        default_name: str = DEFAULT_PROJECT_NAME,
    ) -> None:
        self._store = store
        self._settings = settings_repository
        self._executor = executor or SyncTaskExecutor()
        self._default_name = default_name
        self._current: _OpenProject | None = None
        self._listeners: list[ProjectServiceListener] = []
        # Cancelación lógica: cada op async lleva una generación; si avanza, su resultado
        # tardío se descarta. `_pending` es la generación de la op vigente (o None).
        self._generation = 0
        self._pending: int | None = None

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

    @property
    def is_busy(self) -> bool:
        return self._pending is not None

    def state(self) -> ProjectState:
        actual = self._current
        return ProjectState(
            has_project=actual is not None,
            name=actual.project.name if actual else None,
            path=actual.path if actual else None,
            dirty=actual.dirty if actual else False,
            recent=self._recent_entries(),
            busy=self._pending is not None,
            project=actual.project if actual else None,
        )

    # ------------------------------------------------------------------- operaciones

    def new_project(self) -> None:
        """Crea un proyecto vacío en un working dir nuevo. Queda *dirty* (sin guardar).

        Es rápido (base vacía), así que corre inline; cancela cualquier op async pendiente."""
        self._cancel_pending()
        self._discard_current()
        workspace = self._store.create_empty()
        proyecto = Project(name=self._default_name)
        self._current = _OpenProject(proyecto, workspace, path=None, dirty=True)
        self._emit_state()

    def open_project(self, source: Path) -> None:
        """Abre un `.wifisurvey` en el worker. En caso de fallo emite `on_error`."""
        source = Path(source)
        if not source.exists():
            self._emit_error(
                ProjectStoreError(ProjectErrorKind.NOT_FOUND, f"El archivo ya no existe:\n{source}")
            )
            return
        gen = self._start_async()

        def trabajo() -> object:
            return self._store.open(source)

        def hecho(resultado: object) -> None:
            workspace, proyecto = cast(tuple[ProjectWorkspace, Project], resultado)
            if self._is_stale(gen):
                self._store.discard(workspace)  # op obsoleta: no filtrar el working dir
                return
            self._discard_current()
            self._current = _OpenProject(proyecto, workspace, path=source, dirty=False)
            self._push_recent(source)
            self._finish_async(gen)

        self._executor.submit(trabajo, hecho, lambda e: self._async_error(gen, e))

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
        """Cierra el documento y libera su working dir. Cancela una op pendiente."""
        self._cancel_pending()
        self._discard_current()
        self._emit_state()

    def rename(self, name: str) -> None:
        """Renombra el proyecto en memoria. Lo marca *dirty*; persiste al guardar."""
        actual = self._require_open()
        actual.project = actual.project.with_changes(name=name)
        actual.dirty = True
        self._emit_state()

    # ------------------------------------------------------------- edición del árbol (OZ-9a)

    def add_site(self, name: str) -> None:
        """Agrega un sitio al proyecto. Nombre duplicado -> error por listener, sin cambio."""
        self._apply_edit(lambda p: p.with_changes(sites=(*p.sites, Site(name=name))))

    def rename_site(self, site_id: UUID, name: str) -> None:
        self._apply_edit(lambda p: _map_site(p, site_id, lambda s: replace(s, name=name)))

    def remove_site(self, site_id: UUID) -> None:
        self._apply_edit(
            lambda p: p.with_changes(sites=tuple(s for s in p.sites if s.id != site_id))
        )

    def rename_floor(self, floor_id: UUID, name: str) -> None:
        self._apply_edit(lambda p: _map_floor(p, floor_id, lambda f: replace(f, name=name)))

    def remove_floor(self, floor_id: UUID) -> None:
        self._apply_edit(lambda p: _remove_floor(p, floor_id))

    def add_floor(self, site_id: UUID, name: str, level: int, source: Path) -> None:
        """Agrega una planta a un sitio cargando su plano desde `source` (imagen PNG/JPG).

        El plano es obligatorio (decisión OZ-9a): la planta y su plano se crean juntos, no
        existe una planta a medias. La lectura+parseo+almacenado del plano corre en el worker
        (puede tardar con imágenes grandes); las validaciones baratas (sitio existe, nivel
        libre, nombre no vacío) se hacen antes de encolar para no dejar un asset huérfano si
        la edición era inválida de entrada.
        """
        self._cargar_plano_async(
            site_id=site_id, name=name, level=level, floor_id=None, source=Path(source)
        )

    def set_floor_plan(self, floor_id: UUID, source: Path) -> None:
        """Reemplaza el plano de una planta existente (cargar un plano nuevo en la planta)."""
        self._cargar_plano_async(
            site_id=None, name=None, level=None, floor_id=floor_id, source=Path(source)
        )

    def _apply_edit(self, mutate: Callable[[Project], Project]) -> None:
        """Aplica una edición pura del árbol. Si viola una regla de dominio (nombre o nivel
        duplicado, nombre vacío), emite el error por listener en vez de propagarlo: el slot
        de Qt no debe morir por una entrada inválida del usuario."""
        actual = self._require_open()
        try:
            nuevo = mutate(actual.project)
        except ValueError as e:
            self._emit_error(ProjectStoreError(ProjectErrorKind.INVALID_EDIT, str(e)))
            return
        actual.project = nuevo
        actual.dirty = True
        self._emit_state()

    def _cargar_plano_async(
        self,
        *,
        site_id: UUID | None,
        name: str | None,
        level: int | None,
        floor_id: UUID | None,
        source: Path,
    ) -> None:
        actual = self._require_open()
        error = self._validar_carga_de_plano(actual.project, site_id, name, level, floor_id)
        if error is not None:
            self._emit_error(ProjectStoreError(ProjectErrorKind.INVALID_EDIT, error))
            return

        workspace = actual.workspace
        gen = self._start_async()

        def trabajo() -> object:
            data = source.read_bytes()
            imagen = read_plan_image(data)  # lanza PlanImageError si no valida
            sha = self._store.store_asset(workspace, data, imagen.format.value)
            return (imagen, sha)

        def hecho(resultado: object) -> None:
            imagen, sha = cast(tuple[object, str], resultado)
            if self._is_stale(gen) or self._current is None:
                return
            plan = FloorPlan(
                asset_sha256=sha,
                width_px=imagen.width_px,  # type: ignore[attr-defined]
                height_px=imagen.height_px,  # type: ignore[attr-defined]
                dpi=imagen.dpi,  # type: ignore[attr-defined]
            )
            try:
                nuevo = self._aplicar_plano(
                    self._current.project, plan, site_id, name, level, floor_id
                )
            except ValueError as e:
                self._async_error(gen, ProjectStoreError(ProjectErrorKind.INVALID_EDIT, str(e)))
                return
            self._current.project = nuevo
            self._current.dirty = True
            self._finish_async(gen)

        self._executor.submit(trabajo, hecho, lambda e: self._async_error(gen, e))

    @staticmethod
    def _validar_carga_de_plano(
        project: Project,
        site_id: UUID | None,
        name: str | None,
        level: int | None,
        floor_id: UUID | None,
    ) -> str | None:
        """Chequeos baratos antes del I/O. Devuelve el mensaje de error o `None` si es válido."""
        if floor_id is not None:  # reemplazo de plano
            if _find_floor(project, floor_id) is None:
                return "La planta que se quiere actualizar ya no existe."
            return None
        assert site_id is not None and name is not None and level is not None
        if not name.strip():
            return "El nombre de la planta no puede estar vacío."
        site = _find_site(project, site_id)
        if site is None:
            return "El sitio donde se quiere agregar la planta ya no existe."
        if any(f.level == level for f in site.floors):
            return f"El sitio ya tiene una planta en el nivel {level}."
        return None

    @staticmethod
    def _aplicar_plano(
        project: Project,
        plan: FloorPlan,
        site_id: UUID | None,
        name: str | None,
        level: int | None,
        floor_id: UUID | None,
    ) -> Project:
        if floor_id is not None:
            return _map_floor(project, floor_id, lambda f: replace(f, plan=plan))
        assert site_id is not None and name is not None and level is not None
        floor = Floor(name=name, level=level, plan=plan)
        return _map_site(project, site_id, lambda s: replace(s, floors=(*s.floors, floor)))

    # ---------------------------------------------------------------------- internos

    def _save_to(self, destination: Path) -> None:
        actual = self._require_open()
        workspace = actual.workspace
        project = actual.project
        gen = self._start_async()

        def trabajo() -> object:
            self._store.save(workspace, project, destination)
            return None

        def hecho(_resultado: object) -> None:
            if self._is_stale(gen) or self._current is None:
                return  # op obsoleta o proyecto cerrado mientras guardaba
            self._current.path = destination
            self._current.dirty = False
            self._push_recent(destination)
            self._finish_async(gen)

        self._executor.submit(trabajo, hecho, lambda e: self._async_error(gen, e))

    def _require_open(self) -> _OpenProject:
        if self._current is None:
            raise ValueError("No hay ningún proyecto abierto.")
        return self._current

    def _discard_current(self) -> None:
        if self._current is not None:
            self._store.discard(self._current.workspace)
            self._current = None

    # --------------------------------------------------------------- async / generación

    def _start_async(self) -> int:
        """Marca el inicio de una op async: nueva generación, estado ocupado, notifica."""
        self._generation += 1
        self._pending = self._generation
        self._emit_state()
        return self._generation

    def _finish_async(self, gen: int) -> None:
        if self._pending == gen:
            self._pending = None
        self._emit_state()

    def _cancel_pending(self) -> None:
        """Invalida la op pendiente (su resultado tardío se descartará) y libera 'ocupado'."""
        self._generation += 1
        self._pending = None

    def _is_stale(self, gen: int) -> bool:
        return gen != self._generation

    def _async_error(self, gen: int, error: Exception) -> None:
        if self._is_stale(gen):
            return
        self._pending = None
        if isinstance(error, ProjectStoreError):
            self._emit_error(error)
        elif isinstance(error, PlanImageError):
            # El mensaje ya distingue px/bytes/no-imagen y es apto para el usuario.
            self._emit_error(ProjectStoreError(ProjectErrorKind.INVALID_PLAN, error.message))
        else:
            self._emit_error(ProjectStoreError(ProjectErrorKind.IO, str(error)))
        self._emit_state()

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


# ------------------------------------------------- edición pura del árbol (frozen -> frozen)
#
# Las entidades son inmutables: "editar" es derivar un árbol nuevo conservando las
# identidades (`id`) que no cambian. Estas funciones reconstruyen la rama tocada y dejan el
# resto por referencia; si la reconstrucción viola una regla de dominio (nombre o nivel
# duplicado), el `__post_init__` de la entidad lanza `ValueError`, que el servicio traduce a
# un error para el usuario.


def _find_site(project: Project, site_id: UUID) -> Site | None:
    return next((s for s in project.sites if s.id == site_id), None)


def _find_floor(project: Project, floor_id: UUID) -> Floor | None:
    for site in project.sites:
        floor = next((f for f in site.floors if f.id == floor_id), None)
        if floor is not None:
            return floor
    return None


def _map_site(project: Project, site_id: UUID, fn: Callable[[Site], Site]) -> Project:
    sites = tuple(fn(s) if s.id == site_id else s for s in project.sites)
    return project.with_changes(sites=sites)


def _map_floor(project: Project, floor_id: UUID, fn: Callable[[Floor], Floor]) -> Project:
    def en_sitio(site: Site) -> Site:
        if not any(f.id == floor_id for f in site.floors):
            return site
        floors = tuple(fn(f) if f.id == floor_id else f for f in site.floors)
        return replace(site, floors=floors)

    return project.with_changes(sites=tuple(en_sitio(s) for s in project.sites))


def _remove_floor(project: Project, floor_id: UUID) -> Project:
    sites = tuple(
        replace(s, floors=tuple(f for f in s.floors if f.id != floor_id)) for s in project.sites
    )
    return project.with_changes(sites=sites)

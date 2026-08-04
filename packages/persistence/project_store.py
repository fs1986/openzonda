"""Adaptador del port `ProjectStore`: proyecto como documento `.wifisurvey` (OZ-8).

Este es el *pegamento* que hasta ahora faltaba (deuda de OZ-6/OZ-7): une el contenedor
(`container.py`), la base SQLite (`database.py`) y el repositorio de dominio
(`project_repository.py`) en el ciclo de vida de un documento.

Modelo **documento** (ADR-010):

- **abrir** = `read_container` a un *working dir* bajo `cache_dir/projects/` → `open_database`
  sobre la base extraída → `repo.load`.
- **guardar** = `repo.save` en la base del working dir → `wal_checkpoint(TRUNCATE)` (para que
  el `.sqlite` sea un único archivo consistente, sin `-wal`) → `write_container` **atómico**
  (temporal + `os.replace`) sobre el `.wifisurvey` de destino. Un crash a mitad nunca destruye
  el archivo original del usuario.

El I/O corre en el hilo que llama; moverlo a un worker es la deuda OZ-34. El servicio
(`application`) ya está diseñado para que ese cambio no lo afecte.

## Working dirs huérfanos

Un crash deja el working dir en `cache_dir/projects/`. Se barren al arrancar
(`cleanup_orphans`), de forma **conservadora**: cada working dir vivo mantiene abierto un
`session.lock`. En Windows —el objetivo— un archivo abierto no se puede borrar, así que
`cleanup_orphans` que no logra retirar el lock deduce que otra instancia lo tiene vivo y no
toca ese directorio. En POSIX (dev/CI) el borrado de un archivo abierto sí está permitido,
pero ahí no hay escenario multiusuario de instancias en paralelo; el barrido sigue siendo
seguro para los propios working dirs, que se saltan por estar registrados en memoria.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import IO
from uuid import uuid4

from application.project_service import (
    ProjectErrorKind,
    ProjectStoreError,
    ProjectWorkspace,
)
from domain.project import Project
from persistence.container import (
    DATABASE_ENTRY,
    ContainerTooNewError,
    CorruptContainerError,
    HostileContainerError,
    NotAContainerError,
    read_container,
    write_container,
)
from persistence.database import (
    SCHEMA_VERSION,
    CorruptDatabaseError,
    SchemaTooNewError,
    open_database,
)
from persistence.project_repository import SQLiteProjectRepository

LOCK_NAME = "session.lock"
ASSETS_DIRNAME = "assets"
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class WifiSurveyProjectStore:
    """Implementación del port `ProjectStore` sobre el contenedor `.wifisurvey`."""

    def __init__(self, workspaces_root: Path, app_version: str) -> None:
        self._root = Path(workspaces_root)
        self._app_version = app_version
        self._locks: dict[Path, IO[str]] = {}

    # ------------------------------------------------------------------- operaciones

    def create_empty(self) -> ProjectWorkspace:
        ws_dir = self._nuevo_working_dir()
        self._acquire_lock(ws_dir)
        # Abrir la base la crea y la migra; cerrar deja el archivo listo para usarse.
        with open_database(self._db_path(ws_dir)):
            pass
        return ProjectWorkspace(working_dir=ws_dir)

    def open(self, source: Path) -> tuple[ProjectWorkspace, Project]:
        source = Path(source)
        ws_dir = self._nuevo_working_dir(create=False)
        try:
            read_container(source, ws_dir)
        except NotAContainerError as e:
            self._descartar_dir(ws_dir)
            raise ProjectStoreError(ProjectErrorKind.NOT_A_PROJECT, str(e)) from e
        except ContainerTooNewError as e:
            self._descartar_dir(ws_dir)
            raise ProjectStoreError(ProjectErrorKind.TOO_NEW, str(e)) from e
        except HostileContainerError as e:
            self._descartar_dir(ws_dir)
            raise ProjectStoreError(ProjectErrorKind.HOSTILE, str(e)) from e
        except CorruptContainerError as e:
            self._descartar_dir(ws_dir)
            raise ProjectStoreError(ProjectErrorKind.CORRUPT, str(e)) from e
        except OSError as e:
            self._descartar_dir(ws_dir)
            raise ProjectStoreError(ProjectErrorKind.IO, str(e)) from e

        self._acquire_lock(ws_dir)
        proyecto = self._cargar_proyecto(ws_dir, source)
        return ProjectWorkspace(working_dir=ws_dir), proyecto

    def save(
        self,
        workspace: ProjectWorkspace,
        project: Project,
        destination: Path,
        *,
        _before_rename: Callable[[Path], None] | None = None,
    ) -> None:
        db = self._db_path(workspace.working_dir)
        try:
            with open_database(db) as conn:
                SQLiteProjectRepository(conn).save(project)
                # Colapsar el WAL en el .sqlite: el contenedor empaqueta un único archivo,
                # y un -wal separado dejaría cambios fuera del guardado.
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            write_container(
                destination,
                database=db,
                assets=self._recoger_assets(workspace.working_dir, _hashes_referenciados(project)),
                app_version=self._app_version,
                schema_version=SCHEMA_VERSION,
                _before_rename=_before_rename,
            )
        except (CorruptDatabaseError, SchemaTooNewError) as e:
            raise ProjectStoreError(ProjectErrorKind.CORRUPT, str(e)) from e
        except OSError as e:
            raise ProjectStoreError(ProjectErrorKind.IO, str(e)) from e

    # ------------------------------------------------------------------------- assets

    def store_asset(self, workspace: ProjectWorkspace, data: bytes, extension: str) -> str:
        """Guarda un asset *content-addressed* y devuelve su sha256.

        El nombre en disco es `assets/<sha256>.<ext>`: el hash del **contenido** identifica el
        archivo, así que dos cargas del mismo plano (aunque el usuario los renombre distinto)
        colapsan en una sola entrada. La extensión la fija el llamante desde el formato
        detectado por magic bytes, nunca desde el nombre del archivo de origen (OZ-9a).
        """
        sha = hashlib.sha256(data).hexdigest()
        ext = "".join(c for c in extension.lower() if c.isalnum())
        assets_dir = workspace.working_dir / ASSETS_DIRNAME
        assets_dir.mkdir(parents=True, exist_ok=True)
        destino = assets_dir / f"{sha}.{ext}"
        if not destino.exists():  # dedup: mismo contenido -> mismo nombre -> no reescribir
            # Escritura vía temporal + replace: un corte a mitad no deja un asset truncado
            # con el nombre de su hash (que luego se creería íntegro).
            temporal = assets_dir / f".{sha}.{uuid4().hex}.tmp"
            temporal.write_bytes(data)
            os.replace(temporal, destino)
        return sha

    def read_asset(self, workspace: ProjectWorkspace, sha256: str) -> bytes:
        """Devuelve los bytes del asset por su hash. Falta = documento corrupto."""
        if not _SHA256_HEX.match(sha256):
            raise ProjectStoreError(
                ProjectErrorKind.CORRUPT, f"Hash de asset inválido: {sha256!r}."
            )
        assets_dir = workspace.working_dir / ASSETS_DIRNAME
        if assets_dir.is_dir():
            for entrada in assets_dir.glob(f"{sha256}.*"):
                if entrada.is_file():
                    return entrada.read_bytes()
        raise ProjectStoreError(
            ProjectErrorKind.CORRUPT,
            f"El plano {sha256[:12]}… no está embebido en el proyecto.",
        )

    def _recoger_assets(self, ws_dir: Path, referenciados: frozenset[str]) -> dict[str, Path]:
        """Mapa `nombre -> ruta` de los assets del working dir a empaquetar.

        Solo se empacan los assets que el proyecto **referencia** (por `asset_sha256`). Un
        `set_floor_plan` deja el plano anterior en el working dir sin borrarlo; empacarlo
        también lo dejaría embebido en el `.wifisurvey` para siempre, engordando el archivo con
        cada reemplazo. El nombre del archivo es `<sha256>.<ext>`, así que su *stem* es el hash.
        Se ignoran además los temporales de un `store_asset` que muriera a mitad.
        """
        assets_dir = ws_dir / ASSETS_DIRNAME
        if not assets_dir.is_dir():
            return {}
        return {
            p.name: p
            for p in sorted(assets_dir.iterdir())
            if p.is_file() and not p.name.endswith(".tmp") and p.stem in referenciados
        }

    def discard(self, workspace: ProjectWorkspace) -> None:
        self._descartar_dir(workspace.working_dir)

    def cleanup_orphans(self) -> int:
        if not self._root.exists():
            return 0
        limpiados = 0
        for entrada in self._root.iterdir():
            if not entrada.is_dir() or entrada in self._locks:
                continue
            lock = entrada / LOCK_NAME
            try:
                if lock.exists():
                    # En Windows falla si otra instancia viva lo tiene abierto: entonces no
                    # tocamos nada de ese directorio (un borrado parcial romperia su sesion).
                    os.remove(lock)
            except OSError:
                continue
            shutil.rmtree(entrada, ignore_errors=True)
            limpiados += 1
        return limpiados

    # ---------------------------------------------------------------------- internos

    def _cargar_proyecto(self, ws_dir: Path, source: Path) -> Project:
        try:
            with open_database(self._db_path(ws_dir)) as conn:
                repo = SQLiteProjectRepository(conn)
                ids = repo.list_ids()
                if not ids:
                    self._descartar_dir(ws_dir)
                    raise ProjectStoreError(
                        ProjectErrorKind.CORRUPT,
                        f"{source} no contiene ningún proyecto.",
                    )
                proyecto = repo.load(ids[0])
        except SchemaTooNewError as e:
            self._descartar_dir(ws_dir)
            raise ProjectStoreError(ProjectErrorKind.TOO_NEW, str(e)) from e
        except CorruptDatabaseError as e:
            self._descartar_dir(ws_dir)
            raise ProjectStoreError(ProjectErrorKind.CORRUPT, str(e)) from e

        if proyecto is None:  # pragma: no cover - list_ids no vacío garantiza carga
            self._descartar_dir(ws_dir)
            raise ProjectStoreError(ProjectErrorKind.CORRUPT, f"{source} está dañado.")
        return proyecto

    def _nuevo_working_dir(self, *, create: bool = True) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        ws_dir = self._root / uuid4().hex
        if create:
            ws_dir.mkdir(parents=True, exist_ok=False)
        return ws_dir

    def _db_path(self, ws_dir: Path) -> Path:
        return ws_dir / DATABASE_ENTRY

    def _acquire_lock(self, ws_dir: Path) -> None:
        ws_dir.mkdir(parents=True, exist_ok=True)
        # Se mantiene abierto a propósito toda la sesión: es el lock que impide que otra
        # instancia (o el barrido de huérfanos) borre este working dir mientras está vivo.
        handle = open(ws_dir / LOCK_NAME, "w", encoding="utf-8")  # noqa: SIM115
        handle.write(str(os.getpid()))
        handle.flush()
        self._locks[ws_dir] = handle

    def _descartar_dir(self, ws_dir: Path) -> None:
        handle = self._locks.pop(ws_dir, None)
        if handle is not None:
            handle.close()
        shutil.rmtree(ws_dir, ignore_errors=True)


def _hashes_referenciados(project: Project) -> frozenset[str]:
    """Los `asset_sha256` que el proyecto usa hoy: los planos de todas sus plantas."""
    return frozenset(floor.plan.asset_sha256 for site in project.sites for floor in site.floors)

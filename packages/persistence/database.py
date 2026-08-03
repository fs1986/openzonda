"""Apertura de la base de datos del proyecto, en modo defensivo (diseño §8.2, §17.3).

Un archivo `.wifisurvey` puede venir de un tercero: un colega que comparte un survey, un
adjunto de correo. El modelo de amenazas §17.3 lo trata como **entrada hostil**, y esta es
la puerta por la que entra.

Tres decisiones que se aplican siempre, sin opción de desactivarlas:

- **`trusted_schema = OFF`** — impide que un esquema controlado por el atacante ejecute
  funciones desde vistas, triggers, índices o expresiones `DEFAULT`. Es la mitigación que
  §17.3 nombra para el «SQLite hostil».
- **`foreign_keys = ON`** — SQLite las trae desactivadas por compatibilidad histórica. Sin
  esto, las relaciones del esquema son documentación, no restricciones.
- **`journal_mode = WAL`** — lectura concurrente con la escritura, que es lo que permite a
  la UI dibujar mientras se captura sin bloquearse.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from persistence.migrations import Migration, apply_migrations, discover_migrations

SCHEMA_VERSION = max(m.version for m in discover_migrations())
"""Versión de esquema que esta compilación entiende. Sale de la última migración."""


class DatabaseError(RuntimeError):
    """Raíz de los fallos de apertura de un proyecto."""


class SchemaTooNewError(DatabaseError):
    """El proyecto lo escribió una versión más nueva de OpenZonda."""


class CorruptDatabaseError(DatabaseError):
    """El archivo no es una base de datos SQLite legible."""


def _preparar_conexion(connection: sqlite3.Connection, path: Path) -> int:
    """Aplica los PRAGMAs defensivos y devuelve la versión de esquema del archivo.

    Va todo junto porque comparten el mismo modo de fallo: sobre un archivo que no es
    SQLite, el primer PRAGMA ya revienta, y el usuario merece un mensaje que diga eso y
    no un `DatabaseError` crudo.
    """
    try:
        # El orden importa: trusted_schema se apaga antes de tocar nada del esquema,
        # porque su propósito es justamente que leerlo no ejecute nada.
        connection.execute("PRAGMA trusted_schema = OFF")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return int(connection.execute("PRAGMA user_version").fetchone()[0])
    except sqlite3.DatabaseError as error:
        raise CorruptDatabaseError(
            f"{path} no es una base de datos SQLite legible: {error}"
        ) from error


@contextmanager
def open_database(
    path: Path,
    *,
    migrate: bool = True,
    migrations: tuple[Migration, ...] | None = None,
) -> Iterator[sqlite3.Connection]:
    """Abre el proyecto aplicando los PRAGMAs defensivos y, si procede, las migraciones.

    Falla —sin tocar el archivo— si lo escribió una versión más nueva. El diseño §8.2 lo
    llama *forward-incompatible explícito*: preferimos no abrir un proyecto antes que
    interpretarlo a medias y guardarlo perdiendo lo que no entendemos.
    """
    disponibles = discover_migrations() if migrations is None else migrations
    objetivo = max((m.version for m in disponibles), default=0)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None deja el control de transacciones en manos del código, que es
    # lo que necesitan tanto el runner de migraciones como el repositorio: ambos abren y
    # cierran transacciones explícitas y no quieren que el driver intercale las suyas.
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        version = _preparar_conexion(connection, path)
        if version > objetivo:
            raise SchemaTooNewError(
                f"{path} declara la versión de esquema {version}, pero esta versión de "
                f"OpenZonda entiende hasta la {objetivo}. Actualiza OpenZonda para "
                f"abrir este proyecto; no se modificará el archivo."
            )

        if migrate:
            try:
                apply_migrations(connection, disponibles)
            except sqlite3.DatabaseError as error:
                raise CorruptDatabaseError(
                    f"No se pudo migrar {path}: {error}. El archivo no se ha modificado."
                ) from error

        yield connection
    finally:
        connection.close()

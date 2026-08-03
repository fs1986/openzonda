"""Runner de migraciones minimalista (plan F1.2, diseño §8.2).

Numeración lineal (`0001_init.sql`, `0002_...`), aplicadas al abrir el proyecto **cada una
dentro de su propia transacción**, y `user_version` de SQLite reflejando el número de la
última que completó.

Por qué una transacción por migración y no una para todas: si la número 5 falla, las 1 a 4
ya están confirmadas y `user_version` vale 4, así que reabrir el proyecto reintenta solo
desde la 5. Con una única transacción global, un fallo tardío obligaría a rehacer todo el
trabajo cada vez, y con bases grandes eso convierte un error recuperable en uno que
bloquea el proyecto.

Lo que **no** hace este runner, a propósito: migraciones hacia atrás. Un downgrade sobre
datos de campo es una pérdida de información silenciosa; el diseño §8.2 prefiere fallar al
abrir (ver :class:`~persistence.database.SchemaTooNewError`).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from functools import total_ordering
from importlib import resources
from pathlib import Path

_NOMBRE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


@total_ordering
@dataclass(frozen=True, slots=True)
class Migration:
    """Una migración: su número, su nombre y su SQL."""

    version: int
    name: str
    sql: str

    def __lt__(self, other: Migration) -> bool:
        """Orden **numérico**, no alfabético: `0010` va después de `0009`."""
        return self.version < other.version


def discover_migrations(directory: Path | None = None) -> tuple[Migration, ...]:
    """Descubre las migraciones, ordenadas por número.

    Sin argumento lee las del propio paquete vía `importlib.resources`, que funciona
    igual desde el árbol de fuentes y desde un bundle congelado.
    """
    if directory is not None:
        archivos = [(p.name, p.read_text(encoding="utf-8")) for p in directory.iterdir()]
    else:
        raiz = resources.files(__package__)
        archivos = [(r.name, r.read_text(encoding="utf-8")) for r in raiz.iterdir() if r.is_file()]

    migraciones = []
    for nombre, sql in archivos:
        coincidencia = _NOMBRE.match(nombre)
        if coincidencia is None:
            continue
        migraciones.append(Migration(version=int(coincidencia.group(1)), name=nombre[:-4], sql=sql))

    ordenadas = tuple(sorted(migraciones))
    _exigir_numeracion_lineal(ordenadas)
    return ordenadas


def _exigir_numeracion_lineal(migraciones: tuple[Migration, ...]) -> None:
    """Sin huecos ni duplicados: un hueco significa una migración perdida en un merge."""
    esperado = [i + 1 for i in range(len(migraciones))]
    encontrado = [m.version for m in migraciones]
    if encontrado != esperado:
        raise ValueError(
            f"La numeración de migraciones no es lineal: {encontrado}. "
            f"Se esperaba {esperado}. Un hueco suele significar que un merge perdió una."
        )


def apply_migrations(connection: sqlite3.Connection, migrations: tuple[Migration, ...]) -> int:
    """Aplica las migraciones pendientes y devuelve la versión resultante.

    Cada una va en su propia transacción: si falla, se revierte **entera** y
    `user_version` no avanza. Una migración a medias dejaría un proyecto irrecuperable
    para el usuario, y un proyecto contiene trabajo de campo irrepetible.
    """
    actual = int(connection.execute("PRAGMA user_version").fetchone()[0])

    for migracion in migrations:
        if migracion.version <= actual:
            continue

        # El control de transacción va DENTRO del script, no alrededor: `executescript`
        # hace un COMMIT implícito de cualquier transacción pendiente antes de empezar,
        # así que un `BEGIN` externo quedaría anulado y la migración correría sin
        # protección. Se descubrió al ver fallar el test de rollback.
        #
        # `user_version` no admite parámetros ligados, pero el valor sale del nombre de
        # archivo ya validado contra `_NOMBRE`: son cuatro dígitos, no entrada de usuario.
        script = f"BEGIN;\n{migracion.sql}\nPRAGMA user_version = {migracion.version:d};\nCOMMIT;"
        try:
            connection.executescript(script)
        except sqlite3.Error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        actual = migracion.version

    return actual

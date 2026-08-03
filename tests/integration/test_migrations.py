"""Runner de migraciones y apertura defensiva de SQLite (plan F1.2, diseño §8.2, §17.3).

Tres propiedades que un proyecto de survey necesita y que no son negociables:

1. **Atomicidad.** Una migración que falla a mitad deja la base **exactamente** como estaba.
   Un proyecto medio migrado no es recuperable por el usuario, y contiene meses de trabajo
   de campo irrepetible.
2. **Forward-incompatibilidad explícita.** Abrir un proyecto escrito por una versión más
   nueva **falla con mensaje claro** en vez de leerlo a medias. El diseño §8.2 lo exige.
3. **Apertura defensiva.** Un `.wifisurvey` puede venir de un tercero. El modelo de amenazas
   §17.3 lo trata como entrada hostil: `trusted_schema=OFF` y `foreign_keys=ON`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from persistence.database import (
    SCHEMA_VERSION,
    CorruptDatabaseError,
    SchemaTooNewError,
    open_database,
)
from persistence.migrations import Migration, apply_migrations, discover_migrations


def user_version(path: Path) -> int:
    with sqlite3.connect(path) as conn:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])


def tablas(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        filas = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {f[0] for f in filas}


class TestDescubrimiento:
    def test_las_migraciones_del_paquete_se_descubren(self) -> None:
        migraciones = discover_migrations()

        assert len(migraciones) >= 1
        assert migraciones[0].version == 1

    def test_se_ordenan_por_numero_no_alfabeticamente(self) -> None:
        """`0010` debe ir después de `0009`, no antes de `0002` como haría el orden
        alfabético de nombres de archivo."""
        migraciones = [
            Migration(version=10, name="0010_diez", sql="SELECT 1"),
            Migration(version=2, name="0002_dos", sql="SELECT 1"),
            Migration(version=1, name="0001_uno", sql="SELECT 1"),
        ]

        assert [m.version for m in sorted(migraciones)] == [1, 2, 10]

    def test_la_version_del_esquema_es_la_ultima_migracion(self) -> None:
        assert max(m.version for m in discover_migrations()) == SCHEMA_VERSION


class TestPrimeraApertura:
    def test_una_base_nueva_queda_migrada(self, tmp_path: Path) -> None:
        destino = tmp_path / "proyecto.db"

        with open_database(destino):
            pass

        assert user_version(destino) == SCHEMA_VERSION

    def test_crea_las_tablas_del_diseno(self, tmp_path: Path) -> None:
        destino = tmp_path / "proyecto.db"

        with open_database(destino):
            pass

        creadas = tablas(destino)
        for esperada in ("project", "site", "floor", "survey_session", "measurement", "bss"):
            assert esperada in creadas, f"falta la tabla {esperada} del diseño §8.2"

    def test_reabrir_no_reaplica_migraciones(self, tmp_path: Path) -> None:
        destino = tmp_path / "proyecto.db"
        with open_database(destino) as conn:
            conn.execute(
                "INSERT INTO project (id, name, schema_version) VALUES (?,?,?)",
                ("id-1", "Proyecto", SCHEMA_VERSION),
            )
            conn.commit()

        with open_database(destino) as conn:
            filas = conn.execute("SELECT COUNT(*) FROM project").fetchone()[0]

        assert filas == 1, "reaplicar 0001 habría borrado los datos"


class TestAtomicidad:
    def test_una_migracion_que_falla_no_deja_rastro(self, tmp_path: Path) -> None:
        """El requisito central: migración parcial hace rollback completo."""
        destino = tmp_path / "proyecto.db"
        rota = (
            Migration(version=1, name="0001_ok", sql="CREATE TABLE buena (id INTEGER);"),
            Migration(
                version=2,
                name="0002_rota",
                sql="CREATE TABLE a_medias (id INTEGER); ESTO NO ES SQL;",
            ),
        )

        with sqlite3.connect(destino) as conn, pytest.raises(sqlite3.Error):
            apply_migrations(conn, rota)

        assert "a_medias" not in tablas(destino), (
            "la tabla de la migración fallida sobrevivió: no hubo rollback"
        )

    def test_tras_un_fallo_la_version_no_avanza(self, tmp_path: Path) -> None:
        destino = tmp_path / "proyecto.db"
        rota = (Migration(version=1, name="0001_rota", sql="ESTO NO ES SQL;"),)

        with sqlite3.connect(destino) as conn, pytest.raises(sqlite3.Error):
            apply_migrations(conn, rota)

        assert user_version(destino) == 0, (
            "user_version avanzó pese al fallo: una reapertura creería que ya migró"
        )

    def test_una_migracion_posterior_rota_conserva_las_anteriores(self, tmp_path: Path) -> None:
        """Cada migración es su propia transacción: lo ya aplicado y confirmado permanece."""
        destino = tmp_path / "proyecto.db"
        migraciones = (
            Migration(version=1, name="0001_ok", sql="CREATE TABLE buena (id INTEGER);"),
            Migration(version=2, name="0002_rota", sql="NO SOY SQL;"),
        )

        with sqlite3.connect(destino) as conn, pytest.raises(sqlite3.Error):
            apply_migrations(conn, migraciones)

        assert "buena" in tablas(destino)
        assert user_version(destino) == 1, "debe quedar en la última migración que sí completó"


class TestForwardIncompatible:
    def test_una_version_futura_falla_con_mensaje_claro(self, tmp_path: Path) -> None:
        destino = tmp_path / "futuro.db"
        with sqlite3.connect(destino) as conn:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")

        with pytest.raises(SchemaTooNewError) as error, open_database(destino):
            pass

        mensaje = str(error.value)
        assert str(SCHEMA_VERSION + 1) in mensaje, "el mensaje debe decir qué versión trae"
        assert str(SCHEMA_VERSION) in mensaje, "y cuál es la que entendemos"

    def test_una_version_futura_no_modifica_el_archivo(self, tmp_path: Path) -> None:
        """Downgrade: no tocamos un proyecto que no sabemos interpretar."""
        destino = tmp_path / "futuro.db"
        with sqlite3.connect(destino) as conn:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 5}")
            conn.execute("CREATE TABLE del_futuro (id INTEGER)")

        with pytest.raises(SchemaTooNewError), open_database(destino):
            pass

        assert tablas(destino) == {"del_futuro"}, "se modificó un proyecto ilegible"
        assert user_version(destino) == SCHEMA_VERSION + 5


class TestAperturaDefensiva:
    """Modelo de amenazas §17.3: un .wifisurvey puede venir de un tercero."""

    def test_foreign_keys_activadas(self, tmp_path: Path) -> None:
        with open_database(tmp_path / "p.db") as conn:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    def test_trusted_schema_desactivado(self, tmp_path: Path) -> None:
        """Impide que un esquema hostil ejecute funciones desde vistas o triggers."""
        with open_database(tmp_path / "p.db") as conn:
            assert conn.execute("PRAGMA trusted_schema").fetchone()[0] == 0

    def test_journal_en_modo_wal(self, tmp_path: Path) -> None:
        with open_database(tmp_path / "p.db") as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"

    def test_las_foreign_keys_se_aplican_de_verdad(self, tmp_path: Path) -> None:
        """El PRAGMA no basta: hay que comprobar que rechaza una violación real."""
        with (
            open_database(tmp_path / "p.db") as conn,
            pytest.raises(sqlite3.IntegrityError),
        ):
            conn.execute(
                "INSERT INTO site (id, project_id, name) VALUES (?,?,?)",
                ("s-1", "proyecto-que-no-existe", "Sede"),
            )

    def test_un_archivo_que_no_es_sqlite_falla_claro(self, tmp_path: Path) -> None:
        basura = tmp_path / "hostil.db"
        basura.write_bytes(b"esto no es una base de datos, es basura" * 100)

        with pytest.raises(CorruptDatabaseError) as error, open_database(basura):
            pass

        assert "no es una base de datos" in str(error.value).lower()

    def test_un_archivo_vacio_falla_claro(self, tmp_path: Path) -> None:
        """Un archivo de 0 bytes es SQLite válido y vacío: debe migrarse, no reventar."""
        vacio = tmp_path / "vacio.db"
        vacio.touch()

        with open_database(vacio):
            pass

        assert user_version(vacio) == SCHEMA_VERSION


def _base_con_vista_trampa(destino: Path) -> None:
    """Fixture hostil: una vista del esquema que invoca una función de la aplicación.

    Modela la amenaza real de §17.3. El atacante no puede ejecutar código directamente,
    pero **sí controla el esquema** del `.wifisurvey` que te envía. Si la aplicación
    registra funciones propias —y OpenZonda las registrará—, una vista puede invocarlas
    en cuanto alguien consulte esa tabla.

    No se usa `load_extension` a propósito: Python lo bloquea siempre, así que un test
    basado en él pasaría con `trusted_schema` encendido o apagado y no probaría nada.
    """
    conn = sqlite3.connect(destino)
    conn.execute("CREATE TABLE datos (v TEXT)")
    conn.execute("INSERT INTO datos VALUES ('x')")
    conn.execute("CREATE VIEW trampa AS SELECT efecto_lateral(v) FROM datos")
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    conn.close()


class TestEsquemaHostil:
    """§17.3: 'SQLite hostil'. Los dos tests son un par — el primero demuestra que el
    ataque funciona sin la mitigación, el segundo que con ella no."""

    def test_control_sin_la_mitigacion_el_esquema_ejecuta_codigo(self, tmp_path: Path) -> None:
        """Si este test dejara de pasar, el de abajo ya no probaría nada."""
        hostil = tmp_path / "hostil.db"
        _base_con_vista_trampa(hostil)
        ejecutada: list[str] = []

        conn = sqlite3.connect(hostil)
        conn.create_function("efecto_lateral", 1, lambda v: ejecutada.append(v) or "ok")
        conn.execute("PRAGMA trusted_schema = ON")
        conn.execute("SELECT * FROM trampa").fetchall()
        conn.close()

        assert ejecutada == ["x"], "sin la mitigación, la vista hostil debería ejecutarse"

    def test_con_apertura_defensiva_el_esquema_no_ejecuta_nada(self, tmp_path: Path) -> None:
        hostil = tmp_path / "hostil.db"
        _base_con_vista_trampa(hostil)
        ejecutada: list[str] = []

        with open_database(hostil, migrate=False) as conn:
            conn.create_function("efecto_lateral", 1, lambda v: ejecutada.append(v) or "ok")
            with pytest.raises(sqlite3.OperationalError, match="unsafe use"):
                conn.execute("SELECT * FROM trampa").fetchall()

        assert ejecutada == [], "la función embebida en el esquema llegó a ejecutarse"

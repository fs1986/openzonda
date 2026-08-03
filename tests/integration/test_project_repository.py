"""Repositorio SQLite de proyectos (plan F1.2).

Lo que se prueba es una sola propiedad, pero es la que sostiene todo lo demás: **guardar y
reabrir devuelve exactamente el mismo proyecto**. Un survey es trabajo de campo
irrepetible; si la ida y vuelta pierde un decimal de la calibración, todas las distancias
del informe cambian sin que nadie se entere.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from domain.calibration import Calibration
from domain.measurement import Measured, Provenance
from domain.project import Floor, FloorPlan, Project, Site
from domain.units import Meters, Pixels
from persistence.database import open_database
from persistence.project_repository import SQLiteProjectRepository


@pytest.fixture
def repositorio(tmp_path: Path) -> Iterator[SQLiteProjectRepository]:
    with open_database(tmp_path / "proyecto.db") as conn:
        yield SQLiteProjectRepository(conn)


def plano(calibrado: bool = False) -> FloorPlan:
    calibracion = None
    if calibrado:
        calibracion = Calibration.from_two_points(
            first=(Pixels(0.0), Pixels(0.0)),
            second=(Pixels(137.0), Pixels(0.0)),
            real_distance=Meters(12.3),
        )
    return FloorPlan(
        asset_sha256="b" * 64,
        width_px=1920,
        height_px=1080,
        dpi=Measured(96.0, Provenance.ESTIMATED),
        rotation_degrees=1.5,
        calibration=calibracion,
    )


def proyecto_completo() -> Project:
    return Project(
        name="Cliente X",
        sites=(
            Site(
                name="Sede Santiago",
                floors=(
                    Floor(name="Sótano", level=-1, plan=plano()),
                    Floor(name="Baja", level=0, plan=plano(calibrado=True), height=Meters(3.2)),
                ),
            ),
            Site(name="Sede Valparaíso"),
        ),
    )


class TestRoundTrip:
    def test_un_proyecto_vacio_sobrevive(self, repositorio: SQLiteProjectRepository) -> None:
        original = Project(name="Vacío")

        repositorio.save(original)

        assert repositorio.load(original.id) == original

    def test_un_proyecto_completo_sobrevive(self, repositorio: SQLiteProjectRepository) -> None:
        original = proyecto_completo()

        repositorio.save(original)

        assert repositorio.load(original.id) == original

    def test_la_calibracion_sobrevive_sin_perder_precision(
        self, repositorio: SQLiteProjectRepository
    ) -> None:
        """Si la escala pierde precisión, todas las distancias del informe cambian."""
        original = proyecto_completo()
        repositorio.save(original)

        recuperado = repositorio.load(original.id)

        assert recuperado is not None
        cal_original = original.sites[0].floors[1].plan.calibration
        cal_recuperada = recuperado.sites[0].floors[1].plan.calibration
        assert cal_original is not None and cal_recuperada is not None
        assert cal_recuperada.meters_per_pixel == cal_original.meters_per_pixel
        assert cal_recuperada.relative_error == cal_original.relative_error

    def test_un_plano_sin_calibrar_sigue_sin_calibrar(
        self, repositorio: SQLiteProjectRepository
    ) -> None:
        """`None` debe volver como `None`, no como una escala de 0."""
        original = proyecto_completo()
        repositorio.save(original)

        recuperado = repositorio.load(original.id)

        assert recuperado is not None
        assert recuperado.sites[0].floors[0].plan.calibration is None

    def test_la_procedencia_del_dpi_sobrevive(self, repositorio: SQLiteProjectRepository) -> None:
        """Un DPI observado (del EXIF) no debe volver como asumido: el repo persiste la
        procedencia, no se apoya en el default 'estimated' de la columna (ADR-006)."""
        plan_observado = FloorPlan(
            asset_sha256="c" * 64,
            width_px=800,
            height_px=600,
            dpi=Measured(300.0, Provenance.OBSERVED),
        )
        original = Project(
            name="Con DPI del archivo",
            sites=(Site(name="Sede", floors=(Floor(name="Baja", level=0, plan=plan_observado),)),),
        )
        repositorio.save(original)

        recuperado = repositorio.load(original.id)

        assert recuperado is not None
        dpi = recuperado.sites[0].floors[0].plan.dpi
        assert dpi.value == 300.0
        assert dpi.provenance is Provenance.OBSERVED  # no degradado a ESTIMATED

    def test_el_orden_de_plantas_y_sitios_se_conserva(
        self, repositorio: SQLiteProjectRepository
    ) -> None:
        original = proyecto_completo()
        repositorio.save(original)

        recuperado = repositorio.load(original.id)

        assert recuperado is not None
        assert [s.name for s in recuperado.sites] == [s.name for s in original.sites]
        assert [f.level for f in recuperado.sites[0].floors] == [-1, 0]

    def test_las_identidades_se_conservan(self, repositorio: SQLiteProjectRepository) -> None:
        """Renombrar una sede no la convierte en otra: su id es su identidad."""
        original = proyecto_completo()
        repositorio.save(original)

        recuperado = repositorio.load(original.id)

        assert recuperado is not None
        assert recuperado.sites[0].id == original.sites[0].id
        assert recuperado.sites[0].floors[0].id == original.sites[0].floors[0].id


class TestConsultas:
    def test_un_proyecto_inexistente_devuelve_none(
        self, repositorio: SQLiteProjectRepository
    ) -> None:
        assert repositorio.load(uuid4()) is None

    def test_se_pueden_listar_los_proyectos_guardados(
        self, repositorio: SQLiteProjectRepository
    ) -> None:
        uno, dos = Project(name="Uno"), Project(name="Dos")
        repositorio.save(uno)
        repositorio.save(dos)

        assert set(repositorio.list_ids()) == {uno.id, dos.id}


class TestActualizacion:
    def test_guardar_dos_veces_no_duplica(self, repositorio: SQLiteProjectRepository) -> None:
        original = proyecto_completo()
        repositorio.save(original)
        repositorio.save(original)

        assert len(repositorio.list_ids()) == 1

    def test_guardar_una_version_modificada_reemplaza(
        self, repositorio: SQLiteProjectRepository
    ) -> None:
        original = proyecto_completo()
        repositorio.save(original)

        renombrado = original.with_changes(name="Cliente Y")
        repositorio.save(renombrado)

        recuperado = repositorio.load(original.id)
        assert recuperado is not None
        assert recuperado.name == "Cliente Y"
        assert len(repositorio.list_ids()) == 1

    def test_quitar_un_sitio_lo_elimina_de_verdad(
        self, repositorio: SQLiteProjectRepository
    ) -> None:
        """Guardar es reemplazar el estado completo, no acumular."""
        original = proyecto_completo()
        repositorio.save(original)

        podado = original.with_changes(sites=original.sites[:1])
        repositorio.save(podado)

        recuperado = repositorio.load(original.id)
        assert recuperado is not None
        assert len(recuperado.sites) == 1


class TestPersistenciaReal:
    def test_los_datos_sobreviven_a_cerrar_y_reabrir(self, tmp_path: Path) -> None:
        """El round-trip anterior usa la misma conexión; este cierra el archivo."""
        destino = tmp_path / "proyecto.db"
        original = proyecto_completo()

        with open_database(destino) as conn:
            SQLiteProjectRepository(conn).save(original)

        with open_database(destino) as conn:
            recuperado = SQLiteProjectRepository(conn).load(original.id)

        assert recuperado == original

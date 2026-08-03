"""Entidades de proyecto: Project, Site, Floor, FloorPlan (plan F1.1, diseño §8.1).

Todas ``frozen``. Un proyecto de survey es un registro de lo que se midió un día concreto
con un equipo concreto; mutarlo en sitio haría imposible saber a qué corresponde un dato
histórico. Cambiar algo significa derivar una versión nueva, explícitamente.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from domain.project import Floor, FloorPlan, Project, Site
from domain.units import Meters


def plano() -> FloorPlan:
    return FloorPlan(
        asset_sha256="a" * 64,
        width_px=1920,
        height_px=1080,
        dpi=96.0,
    )


class TestProject:
    def test_lleva_version_de_esquema(self) -> None:
        """Abrir un proyecto de una versión futura debe poder detectarse (diseño §8.2)."""
        proyecto = Project(name="Oficina central")

        assert proyecto.schema_version >= 1

    def test_recibe_un_identificador_estable(self) -> None:
        proyecto = Project(name="Oficina central")

        assert isinstance(proyecto.id, UUID)

    def test_dos_proyectos_no_comparten_identificador(self) -> None:
        assert Project(name="A").id != Project(name="B").id

    def test_el_nombre_no_puede_estar_vacio(self) -> None:
        with pytest.raises(ValueError, match="nombre"):
            Project(name="   ")

    def test_es_inmutable(self) -> None:
        proyecto = Project(name="Oficina central")
        with pytest.raises(AttributeError):
            proyecto.name = "Otro"  # type: ignore[misc]


class TestFloor:
    def test_el_nivel_ordena_las_plantas(self) -> None:
        """Los sótanos son negativos; la planta baja es 0."""
        sotano = Floor(name="Sótano", level=-1, plan=plano())
        baja = Floor(name="Planta baja", level=0, plan=plano())
        primera = Floor(name="Primera", level=1, plan=plano())

        assert sorted([primera, baja, sotano], key=lambda f: f.level) == [
            sotano,
            baja,
            primera,
        ]

    def test_guarda_la_altura_para_atenuacion_entre_plantas(self) -> None:
        """El diseño §8.1 la reserva para la atenuación inter-piso futura."""
        planta = Floor(name="Primera", level=1, plan=plano(), height=Meters(3.2))

        assert planta.height == Meters(3.2)

    def test_la_altura_es_opcional(self) -> None:
        assert Floor(name="Primera", level=1, plan=plano()).height is None

    def test_el_nombre_no_puede_estar_vacio(self) -> None:
        with pytest.raises(ValueError, match="nombre"):
            Floor(name="", level=0, plan=plano())


class TestFloorPlan:
    def test_guarda_el_hash_del_asset(self) -> None:
        """El diseño §8.1 lo exige: permite detectar que el plano cambió bajo los pies."""
        assert plano().asset_sha256 == "a" * 64

    def test_rechaza_un_hash_que_no_es_sha256(self) -> None:
        with pytest.raises(ValueError, match=r"sha256|hash"):
            FloorPlan(asset_sha256="corto", width_px=100, height_px=100, dpi=96.0)

    def test_rechaza_dimensiones_no_positivas(self) -> None:
        with pytest.raises(ValueError, match="positiv"):
            FloorPlan(asset_sha256="a" * 64, width_px=0, height_px=100, dpi=96.0)

    def test_sin_calibracion_no_hay_escala(self) -> None:
        """Un plano recién cargado no sabe cuánto mide nada: es un estado legítimo."""
        assert plano().calibration is None


class TestSite:
    def test_agrupa_plantas(self) -> None:
        sitio = Site(
            name="Sede Santiago",
            floors=(Floor(name="Baja", level=0, plan=plano()),),
        )

        assert len(sitio.floors) == 1

    def test_las_plantas_no_pueden_repetir_nivel(self) -> None:
        """Dos plantas en el mismo nivel harían ambigua la ubicación de una muestra."""
        with pytest.raises(ValueError, match="nivel"):
            Site(
                name="Sede",
                floors=(
                    Floor(name="Baja", level=0, plan=plano()),
                    Floor(name="Otra baja", level=0, plan=plano()),
                ),
            )

    def test_un_sitio_puede_no_tener_plantas_todavia(self) -> None:
        assert Site(name="Sede").floors == ()

    def test_la_coleccion_de_plantas_no_es_mutable(self) -> None:
        sitio = Site(name="Sede", floors=(Floor(name="Baja", level=0, plan=plano()),))

        assert isinstance(sitio.floors, tuple), (
            "una lista permitiría mutar el sitio por la puerta de atrás"
        )


class TestComposicion:
    def test_un_proyecto_agrupa_sitios(self) -> None:
        proyecto = Project(name="Cliente X", sites=(Site(name="Sede A"),))

        assert len(proyecto.sites) == 1

    def test_los_sitios_no_pueden_repetir_nombre(self) -> None:
        with pytest.raises(ValueError, match="nombre"):
            Project(name="Cliente X", sites=(Site(name="Sede A"), Site(name="Sede A")))

    def test_se_puede_derivar_una_copia_modificada(self) -> None:
        original = Project(name="Cliente X")
        derivado = original.with_changes(name="Cliente Y")

        assert derivado.name == "Cliente Y"
        assert original.name == "Cliente X"
        assert derivado.id == original.id, "derivar no crea un proyecto distinto"


class TestIdentidad:
    def test_dos_entidades_con_el_mismo_id_son_la_misma(self) -> None:
        identificador = uuid4()
        a = Site(name="Sede", id=identificador)
        b = Site(name="Sede renombrada", id=identificador)

        assert a.same_entity_as(b), (
            "la identidad de una entidad es su id, no el valor de sus campos"
        )

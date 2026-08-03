"""Entidades de proyecto: Project, Site, Floor, FloorPlan (plan F1.1, diseño §8.1).

Todas ``frozen``. Un proyecto de survey es el registro de lo que se midió un día concreto
con un equipo concreto; mutarlo en sitio haría imposible saber a qué corresponde un dato
histórico. Cambiar algo significa derivar una versión nueva, y eso deja rastro.

La identidad de una entidad es su ``id``, no el valor de sus campos: renombrar una sede no
la convierte en otra sede.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

from domain.calibration import Calibration
from domain.measurement import Measured
from domain.units import Meters

PROJECT_SCHEMA_VERSION = 1
"""Versión del esquema del proyecto (diseño §8.2).

Abrir un proyecto de versión mayor que la soportada debe fallar con un mensaje claro, no
degradarse en silencio: un proyecto futuro puede contener datos que esta versión no sabe
interpretar y sobrescribiría.
"""

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _exigir_nombre(valor: str, que: str) -> None:
    if not valor.strip():
        raise ValueError(f"El nombre de {que} no puede estar vacío.")


@dataclass(frozen=True, slots=True)
class Entity:
    """Base de las entidades con identidad propia."""

    id: UUID = field(default_factory=uuid4, kw_only=True)

    def same_entity_as(self, other: Entity) -> bool:
        """Dos entidades son la misma si comparten identificador, aunque difieran."""
        return type(self) is type(other) and self.id == other.id


@dataclass(frozen=True, slots=True)
class FloorPlan:
    """Imagen del plano y su transformación al mundo real.

    El hash del asset permite detectar que el plano cambió bajo los pies: si alguien
    sustituye la imagen, las coordenadas de las muestras dejan de significar lo mismo.
    """

    asset_sha256: str
    width_px: int
    height_px: int
    dpi: Measured[float]
    """DPI del plano con su procedencia. `OBSERVED` si vino del archivo (EXIF), `ESTIMATED`
    si se asumió un valor por defecto. Es `Measured`, no `float`, a propósito: el número no
    existe crudo, así que nadie puede usar un DPI asumido como si fuera medido (ADR-006)."""
    rotation_degrees: float = 0.0
    calibration: Calibration | None = None

    def __post_init__(self) -> None:
        if not _SHA256_HEX.match(self.asset_sha256):
            raise ValueError(
                f"El hash del plano debe ser sha256 en hexadecimal minúsculo de 64 "
                f"caracteres, no {self.asset_sha256!r}."
            )
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError(
                f"Las dimensiones del plano deben ser positivas, no "
                f"{self.width_px}x{self.height_px}."
            )
        if self.dpi.value <= 0.0:
            raise ValueError(f"El DPI debe ser positivo, no {self.dpi.value}.")

    @property
    def is_calibrated(self) -> bool:
        """Un plano recién cargado no sabe cuánto mide nada. Es un estado legítimo."""
        return self.calibration is not None


@dataclass(frozen=True, slots=True)
class Floor(Entity):
    """Una planta. El nivel la ordena: los sótanos son negativos, la baja es 0."""

    name: str
    level: int
    plan: FloorPlan
    height: Meters | None = None
    """Altura de la planta. Reservada para la atenuación entre pisos (diseño §8.1)."""

    def __post_init__(self) -> None:
        _exigir_nombre(self.name, "la planta")


@dataclass(frozen=True, slots=True)
class Site(Entity):
    """Ubicación física que agrupa plantas."""

    name: str
    floors: tuple[Floor, ...] = ()

    def __post_init__(self) -> None:
        _exigir_nombre(self.name, "el sitio")
        niveles = [f.level for f in self.floors]
        if len(niveles) != len(set(niveles)):
            raise ValueError(
                "Dos plantas comparten nivel en el mismo sitio: la ubicación de una "
                "muestra sería ambigua."
            )


@dataclass(frozen=True, slots=True)
class Project(Entity):
    """Contenedor raíz de un survey (diseño §8.1)."""

    name: str
    sites: tuple[Site, ...] = ()
    schema_version: int = PROJECT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _exigir_nombre(self.name, "el proyecto")
        nombres = [s.name for s in self.sites]
        if len(nombres) != len(set(nombres)):
            raise ValueError("Dos sitios comparten nombre dentro del mismo proyecto.")

    def with_changes(self, **cambios: object) -> Project:
        """Deriva una copia modificada **conservando la identidad**."""
        return replace(self, **cambios)  # type: ignore[arg-type]

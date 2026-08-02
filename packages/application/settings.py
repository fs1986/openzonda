"""Settings de aplicación y su port de persistencia.

Vive en `application` —no en `persistence`— porque el *contrato* pertenece al caso de uso:
la UI necesita saber que existe algo capaz de cargar y guardar settings, pero no debe
saber que detrás hay un archivo JSON (ADR-003, ADR-008).

El esquema lleva versión porque el diseño §18 exige que el upgrade preserve los settings
y que su migración sea versionada.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

SETTINGS_SCHEMA_VERSION = 1

SUPPORTED_LANGUAGES = frozenset({"es", "en"})
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Preferencias de usuario. Inmutable: derivar copias con `with_changes`."""

    schema_version: int = SETTINGS_SCHEMA_VERSION
    language: str = "es"
    log_level: str = "INFO"
    window_geometry: tuple[int, int, int, int] | None = None

    def __post_init__(self) -> None:
        if self.language not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"idioma no soportado: {self.language!r} "
                f"(soportados: {sorted(SUPPORTED_LANGUAGES)})"
            )
        if self.log_level not in VALID_LOG_LEVELS:
            raise ValueError(
                f"nivel de log inválido: {self.log_level!r} (válidos: {sorted(VALID_LOG_LEVELS)})"
            )

    def with_changes(self, **cambios: object) -> AppSettings:
        return replace(self, **cambios)  # type: ignore[arg-type]


class SettingsRepository(Protocol):
    """Port de persistencia de settings. Su implementación vive en `persistence`."""

    def load(self) -> AppSettings:
        """Devuelve los settings almacenados, o los valores por defecto si no hay."""
        ...

    def save(self, settings: AppSettings) -> None:
        """Persiste los settings de forma atómica."""
        ...

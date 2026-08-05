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

# v2 (OZ-8): añade `recent_projects`. v3 (OZ-35): `language` admite el sentinela `"system"`
# (seguir el locale del SO) y pasa a ser el valor por defecto (ADR-013). Las migraciones son
# aditivas —un settings más viejo trae un `language` explícito ("es"/"en") que sigue siendo un
# override válido—, así que preservan todo sin pedirle nada al usuario. Un binario viejo que lea
# un settings más nuevo lo rechaza por "esquema más nuevo" (JsonSettingsRepository) y arranca con
# defaults sin sobrescribir: degrada, no crashea.
SETTINGS_SCHEMA_VERSION = 3

SUPPORTED_LANGUAGES = frozenset({"es", "en"})
"""Idiomas de UI seleccionables. `"system"` NO está aquí: es un ajuste, no un idioma."""

LANGUAGE_SYSTEM = "system"
"""Valor de `AppSettings.language` que significa «seguir el locale del sistema» (ADR-013)."""

_VALID_LANGUAGE_SETTINGS = SUPPORTED_LANGUAGES | {LANGUAGE_SYSTEM}
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Preferencias de usuario. Inmutable: derivar copias con `with_changes`."""

    schema_version: int = SETTINGS_SCHEMA_VERSION
    language: str = LANGUAGE_SYSTEM
    """`"system"` (default, seguir el SO), o `"es"`/`"en"` como override. El idioma *efectivo*
    lo resuelve `application.i18n.resolve_language`; este campo es la preferencia, no el
    resultado."""
    log_level: str = "INFO"
    window_geometry: tuple[int, int, int, int] | None = None
    recent_projects: tuple[str, ...] = ()
    """Rutas de proyectos abiertos recientemente, más reciente primero (OZ-8)."""

    def __post_init__(self) -> None:
        if self.language not in _VALID_LANGUAGE_SETTINGS:
            raise ValueError(
                f"idioma no soportado: {self.language!r} "
                f"(válidos: {sorted(_VALID_LANGUAGE_SETTINGS)})"
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

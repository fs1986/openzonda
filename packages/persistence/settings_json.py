"""Adaptador JSON del port `SettingsRepository`.

Criterio de robustez: **un settings roto nunca debe impedir arrancar la aplicación**. Un
usuario que no puede abrir el programa por un archivo de preferencias corrupto no tiene
forma de arreglarlo desde dentro del programa.

La única excepción es un esquema *más nuevo* que el que esta versión entiende: ahí sí se
falla, porque cargarlo a ciegas y volver a guardarlo destruiría opciones que no sabemos
interpretar. El diseño §18 exige que el upgrade preserve los settings; el downgrade merece
la misma cortesía.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from application.settings import SETTINGS_SCHEMA_VERSION, AppSettings


class UnsupportedSettingsSchemaError(RuntimeError):
    """El archivo lo escribió una versión más nueva de OpenZonda."""


class JsonSettingsRepository:
    """Persiste `AppSettings` como JSON, con escritura atómica."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppSettings:
        try:
            crudo = self._path.read_text(encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            return AppSettings()
        except OSError:
            # Permisos, disco, ruta imposible: arrancar con defaults es mejor que no
            # arrancar. El composition root deja constancia en el log.
            return AppSettings()

        try:
            datos = json.loads(crudo)
        except json.JSONDecodeError:
            return AppSettings()

        if not isinstance(datos, dict):
            return AppSettings()

        version = datos.get("schema_version", SETTINGS_SCHEMA_VERSION)
        if isinstance(version, int) and version > SETTINGS_SCHEMA_VERSION:
            raise UnsupportedSettingsSchemaError(
                f"{self._path} declara schema_version={version}, pero esta versión de "
                f"OpenZonda entiende hasta {SETTINGS_SCHEMA_VERSION}. No se sobrescribirá."
            )

        return self._desde_dict(datos)

    def save(self, settings: AppSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SETTINGS_SCHEMA_VERSION,
            "language": settings.language,
            "log_level": settings.log_level,
            "window_geometry": (
                list(settings.window_geometry) if settings.window_geometry else None
            ),
            "recent_projects": list(settings.recent_projects),
        }

        # Escritura atómica: un corte de luz deja el archivo anterior intacto, nunca uno
        # a medias. os.replace es atómico dentro del mismo volumen.
        temporal = self._path.with_name(self._path.name + ".tmp")
        temporal.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(temporal, self._path)

    @staticmethod
    def _desde_dict(datos: dict[str, Any]) -> AppSettings:
        # Migración v1→v2 (aditiva): un settings v1 no trae `recent_projects`; `_recientes`
        # lo resuelve a `()` sin perder los demás campos ni pedirle nada al usuario.
        try:
            return AppSettings(
                schema_version=SETTINGS_SCHEMA_VERSION,
                language=datos.get("language", "system"),
                log_level=datos.get("log_level", "INFO"),
                window_geometry=_geometria(datos.get("window_geometry")),
                recent_projects=_recientes(datos.get("recent_projects")),
            )
        except (ValueError, TypeError):
            # Valor fuera de rango o de tipo inesperado: defaults antes que un crash.
            return AppSettings()


def _geometria(valor: object) -> tuple[int, int, int, int] | None:
    es_cuaterna = isinstance(valor, list | tuple) and len(valor) == 4
    # `bool` es subclase de `int`: sin excluirlo, [true, false, true, false] pasaría.
    if es_cuaterna and all(isinstance(v, int) and not isinstance(v, bool) for v in valor):
        x, y, ancho, alto = valor  # type: ignore[misc]
        return (x, y, ancho, alto)
    return None


def _recientes(valor: object) -> tuple[str, ...]:
    """Lista de rutas recientes. Ignora lo que no sea texto en vez de reventar: un settings
    manipulado a mano no debe impedir arrancar."""
    if not isinstance(valor, list | tuple):
        return ()
    return tuple(v for v in valor if isinstance(v, str))

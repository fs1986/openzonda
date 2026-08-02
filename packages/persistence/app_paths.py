"""Resolución de rutas de aplicación y modo portable (diseño §18).

Dos modos excluyentes:

- **Instalado**: `%APPDATA%\\OpenZonda\\settings.json` y
  `%LOCALAPPDATA%\\OpenZonda\\{logs,cache}\\`.
- **Portable**: detectado por `portable.marker` junto al ejecutable. Config, logs y caché
  viven junto a la app y **nada** se escribe en el perfil del usuario — que es
  precisamente lo que se busca al usar un portable en una máquina ajena.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "OpenZonda"
PORTABLE_MARKER = "portable.marker"


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Rutas resueltas para esta ejecución. Absolutas siempre."""

    portable: bool
    settings_file: Path
    logs_dir: Path
    cache_dir: Path


def resolve_app_paths(app_dir: Path, env: Mapping[str, str] | None = None) -> AppPaths:
    """Resuelve dónde viven settings, logs y caché.

    `env` se inyecta para poder testear ambos modos sin tocar el entorno real del proceso.
    """
    entorno: Mapping[str, str] = os.environ if env is None else env
    base_app = Path(app_dir).absolute()

    if (base_app / PORTABLE_MARKER).exists():
        return AppPaths(
            portable=True,
            settings_file=base_app / "settings.json",
            logs_dir=base_app / "logs",
            cache_dir=base_app / "cache",
        )

    roaming = entorno.get("APPDATA")
    local = entorno.get("LOCALAPPDATA")
    if roaming and local:
        base_config = Path(roaming).absolute() / APP_NAME
        base_datos = Path(local).absolute() / APP_NAME
    else:
        # Fuera de Windows (CI en Linux, desarrollo) seguimos una disposición tipo XDG.
        home = Path(entorno.get("HOME") or entorno.get("USERPROFILE") or Path.home())
        base_config = home.absolute() / ".config" / APP_NAME
        base_datos = home.absolute() / ".local" / "share" / APP_NAME

    return AppPaths(
        portable=False,
        settings_file=base_config / "settings.json",
        logs_dir=base_datos / "logs",
        cache_dir=base_datos / "cache",
    )

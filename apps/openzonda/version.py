"""Versión de la aplicación, resuelta en tiempo de ejecución.

Tres fuentes, en orden de fiabilidad decreciente:

1. `_build_info.py`, generado por el spec de PyInstaller desde el tag de git. Es la única
   fuente válida dentro de un bundle congelado.
2. Metadatos del paquete instalado, en desarrollo.
3. Un marcador explícito de desarrollo. Nunca se inventa un número que parezca un release.
"""

from __future__ import annotations

DEV_VERSION = "0.0.0+dev"


def app_version() -> str:
    try:
        from openzonda._build_info import VERSION  # type: ignore[import-not-found]
    except ImportError:
        pass
    else:
        return str(VERSION)

    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - stdlib presente en 3.13
        return DEV_VERSION

    try:
        return version("openzonda")
    except PackageNotFoundError:
        return DEV_VERSION

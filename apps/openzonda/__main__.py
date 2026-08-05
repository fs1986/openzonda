"""Punto de entrada de OpenZonda. Cablea adaptadores y lanza la shell (ADR-008)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from application.project_service import ProjectService
from application.settings import AppSettings, SettingsRepository
from openzonda.baseline import enforce_baseline
from openzonda.logging_setup import setup_logging
from openzonda.version import app_version
from persistence.app_paths import AppPaths, resolve_app_paths
from persistence.project_store import WifiSurveyProjectStore
from persistence.settings_json import (
    JsonSettingsRepository,
    UnsupportedSettingsSchemaError,
)

WORKSPACES_DIRNAME = "projects"


class ReadOnlySettingsRepository:
    """Envoltorio que descarta las escrituras y deja constancia.

    Se usa cuando el `settings.json` en disco lo escribió una versión más nueva de
    OpenZonda: arrancamos con valores por defecto, pero **no** pisamos configuración que
    no sabemos interpretar. La UI no se entera; para ella sigue siendo un
    `SettingsRepository` cualquiera, que es el punto de ADR-008.
    """

    def __init__(self, settings: AppSettings, logger: logging.Logger) -> None:
        self._settings = settings
        self._logger = logger

    def load(self) -> AppSettings:
        return self._settings

    def save(self, settings: AppSettings) -> None:
        self._logger.warning(
            "settings no guardados: el archivo en disco pertenece a una versión más "
            "nueva de OpenZonda y sobrescribirlo perdería opciones desconocidas"
        )


def application_dir() -> Path:
    """Carpeta donde vive el ejecutable (bundle) o la raíz del repo (desarrollo)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def build_settings_repository(
    paths: AppPaths, logger: logging.Logger
) -> tuple[SettingsRepository, AppSettings]:
    repositorio = JsonSettingsRepository(paths.settings_file)
    try:
        return repositorio, repositorio.load()
    except UnsupportedSettingsSchemaError as error:
        logger.warning("%s", error)
        por_defecto = AppSettings()
        return ReadOnlySettingsRepository(por_defecto, logger), por_defecto


# Código de salida cuando el SO está por debajo del baseline de ADR-001 (OZ-33). Distinto
# de 1 para que el instalador/scripts puedan distinguir "SO no soportado" de un fallo genérico.
EXIT_UNSUPPORTED_WINDOWS = 3

SMOKE_FLAG = "--smoke"
SMOKE_DEFAULT_MS = 1500


def _autoclose_ms(argv: list[str]) -> int | None:
    """Lee `--smoke [ms]`, usado por `scripts/smoke_local.ps1`.

    Se resuelve a mano en lugar de con argparse porque el resto de argumentos son de Qt y
    argparse los rechazaría.
    """
    if SMOKE_FLAG not in argv:
        return None
    indice = argv.index(SMOKE_FLAG)
    siguiente = argv[indice + 1] if indice + 1 < len(argv) else ""
    return int(siguiente) if siguiente.isdigit() else SMOKE_DEFAULT_MS


def main(argv: list[str] | None = None) -> int:
    argumentos = list(argv if argv is not None else sys.argv)
    paths = resolve_app_paths(application_dir())

    # El nivel definitivo sale de los settings, pero necesitamos logger antes de leerlos
    # para poder registrar los problemas de esa misma lectura.
    logger = setup_logging(paths.logs_dir)
    version = app_version()
    logger.info(
        "OpenZonda %s arrancando (modo %s, settings en %s)",
        version,
        "portable" if paths.portable else "instalado",
        paths.settings_file,
    )

    # Guard de baseline (OZ-33): negarse a arrancar por debajo del build soportado, leyendo
    # la versión por una vía que no miente. También cubre el modo portable, que no pasa por
    # el preflight del instalador.
    if not enforce_baseline(logger):
        return EXIT_UNSUPPORTED_WINDOWS

    repositorio, settings = build_settings_repository(paths, logger)
    logger.setLevel(settings.log_level)

    # Adaptador de proyecto (OZ-8). Los working dirs de proyectos abiertos viven bajo la
    # caché; barrer los huérfanos de sesiones muertas al arrancar libera espacio sin tocar
    # los de otra instancia viva.
    store = WifiSurveyProjectStore(paths.cache_dir / WORKSPACES_DIRNAME, version)
    huerfanos = store.cleanup_orphans()
    if huerfanos:
        logger.info("Limpiados %d working dirs de proyectos huérfanos", huerfanos)

    # El I/O de abrir/guardar corre en un worker de Qt para no congelar la UI (OZ-34). El
    # import es diferido, como el de la shell, para no cargar Qt antes del guard de baseline.
    from desktop.app import run_app
    from desktop.qt_executor import QtTaskExecutor

    project_service = ProjectService(store, repositorio, executor=QtTaskExecutor())

    try:
        return run_app(
            project_service,
            repositorio,
            version,
            argumentos,
            autoclose_ms=_autoclose_ms(argumentos),
            translations_dir=application_dir() / "translations",
        )
    except Exception:
        logger.exception("OpenZonda terminó por un error no controlado")
        raise
    finally:
        logger.info("OpenZonda finalizado")


if __name__ == "__main__":
    raise SystemExit(main())

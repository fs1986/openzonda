"""Adaptador `WifiSurveyProjectStore`: el glue documento↔repositorio↔contenedor (OZ-8).

Cierra las verificaciones diferidas de OZ-6/OZ-7:
- **Round-trip real** proyecto → `.wifisurvey` → proyecto, por igualdad de datos de dominio.
- **Guardado atómico** a nivel del store: matar el proceso a mitad no destruye el archivo
  original (kill-test análogo al de OZ-7, ahora sobre `store.save`).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from application.project_service import ProjectErrorKind, ProjectStoreError
from domain.project import Floor, FloorPlan, Project, Site
from persistence.container import (
    CONTAINER_FORMAT_VERSION,
    DATABASE_ENTRY,
    write_container,
)
from persistence.project_store import LOCK_NAME, WifiSurveyProjectStore


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _store(tmp_path: Path, *, app_version: str = "0.0.3") -> WifiSurveyProjectStore:
    return WifiSurveyProjectStore(tmp_path / "projects", app_version)


def _proyecto_con_estructura() -> Project:
    plan = FloorPlan(asset_sha256="a" * 64, width_px=1200, height_px=800, dpi=96.0)
    floor = Floor(name="Planta baja", level=0, plan=plan)
    site = Site(name="Sede central", floors=(floor,))
    return Project(name="Estudio de cobertura", sites=(site,))


# ------------------------------------------------------------------------ round-trip


def test_round_trip_proyecto_vacio(tmp_path: Path) -> None:
    store = _store(tmp_path)
    destino = tmp_path / "vacio.wifisurvey"

    ws = store.create_empty()
    proyecto = Project(name="Sin sitios aún")
    store.save(ws, proyecto, destino)
    store.discard(ws)

    _ws2, recuperado = _store(tmp_path).open(destino)
    assert recuperado == proyecto  # igualdad de dominio, id incluido


def test_round_trip_con_sitios_plantas_y_plano(tmp_path: Path) -> None:
    store = _store(tmp_path)
    destino = tmp_path / "estudio.wifisurvey"
    proyecto = _proyecto_con_estructura()

    ws = store.create_empty()
    store.save(ws, proyecto, destino)
    store.discard(ws)

    _ws2, recuperado = _store(tmp_path).open(destino)
    assert recuperado == proyecto


def test_reguardar_tras_editar_persiste_el_cambio(tmp_path: Path) -> None:
    store = _store(tmp_path)
    destino = tmp_path / "estudio.wifisurvey"

    ws = store.create_empty()
    proyecto = Project(name="Primero")
    store.save(ws, proyecto, destino)
    store.save(ws, proyecto.with_changes(name="Renombrado"), destino)
    store.discard(ws)

    _ws2, recuperado = _store(tmp_path).open(destino)
    assert recuperado.name == "Renombrado"
    assert recuperado.id == proyecto.id  # sigue siendo el mismo proyecto


# ----------------------------------------------------------------------- guardado atómico


def test_matar_el_proceso_durante_guardar_conserva_el_archivo(tmp_path: Path) -> None:
    """Kill-test a nivel del store: un crash a mitad de `save` no destruye el .wifisurvey."""
    destino = tmp_path / "trabajo.wifisurvey"
    store = _store(tmp_path)
    ws = store.create_empty()
    store.save(ws, Project(name="Trabajo de campo"), destino)
    hash_original = _sha256(destino)

    script = tmp_path / "suicida.py"
    script.write_text(
        "import os, sys\n"
        "from pathlib import Path\n"
        "from domain.project import Project\n"
        "from persistence.project_store import WifiSurveyProjectStore\n"
        "store = WifiSurveyProjectStore(Path(sys.argv[1]), '9.9.9')\n"
        "ws = store.create_empty()\n"
        "store.save(\n"
        "    ws, Project(name='Version que no debe cuajar'), Path(sys.argv[2]),\n"
        "    _before_rename=lambda _t: os._exit(137),\n"
        ")\n",
        encoding="utf-8",
    )

    resultado = subprocess.run(
        [sys.executable, str(script), str(tmp_path / "projects2"), str(destino)],
        capture_output=True,
        check=False,
    )

    assert resultado.returncode == 137, "el proceso debía morir antes del rename"
    assert _sha256(destino) == hash_original, (
        "matar el proceso durante el guardado destruyó el proyecto anterior"
    )
    # Y sigue siendo el proyecto viejo, legible, no una mezcla.
    _ws, recuperado = _store(tmp_path).open(destino)
    assert recuperado.name == "Trabajo de campo"


# ----------------------------------------------------------------------------- errores


def test_abrir_algo_que_no_es_contenedor(tmp_path: Path) -> None:
    basura = tmp_path / "foto.wifisurvey"
    basura.write_bytes(b"esto no es un ZIP")

    with pytest.raises(ProjectStoreError) as exc:
        _store(tmp_path).open(basura)
    assert exc.value.kind is ProjectErrorKind.NOT_A_PROJECT


def test_abrir_contenedor_de_version_futura(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ws = store.create_empty()
    db = ws.working_dir / DATABASE_ENTRY
    futuro = tmp_path / "futuro.wifisurvey"
    write_container(
        futuro,
        database=db,
        assets={},
        app_version="99.0.0",
        schema_version=1,
        _format_version=CONTAINER_FORMAT_VERSION + 1,
    )
    store.discard(ws)

    with pytest.raises(ProjectStoreError) as exc:
        _store(tmp_path).open(futuro)
    assert exc.value.kind is ProjectErrorKind.TOO_NEW


# ------------------------------------------------------------------- huérfanos


def test_cleanup_borra_working_dirs_huerfanos(tmp_path: Path) -> None:
    store = _store(tmp_path)
    root = tmp_path / "projects"
    root.mkdir(parents=True, exist_ok=True)
    # Huérfano de un crash: dir con lock cerrado (nadie lo tiene abierto).
    huerfano = root / "muerto"
    huerfano.mkdir()
    (huerfano / LOCK_NAME).write_text("999999", encoding="utf-8")
    (huerfano / "data").mkdir()

    limpiados = store.cleanup_orphans()

    assert limpiados >= 1
    assert not huerfano.exists()


def test_cleanup_respeta_los_working_dirs_vivos_de_esta_instancia(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ws = store.create_empty()  # vivo: lock abierto y registrado

    store.cleanup_orphans()

    assert ws.working_dir.exists(), "no debe barrer un working dir vivo de esta instancia"
    store.discard(ws)

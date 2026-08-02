"""Tests de la barrera de capas (ADR-003).

`lint-imports` ya corre en CI, pero eso solo demuestra que el comando existe y
termina en 0. Estos tests demuestran lo que de verdad importa: que los contratos
declarados en `pyproject.toml` *rechazan* una violación real.

Sin ellos, un contrato mal escrito —un `source_modules` que apunta a un paquete
inexistente, un paquete ausente de `root_packages`, un `include_external_packages`
que se cae— pasaría en verde para siempre. Ese es exactamente el fallo silencioso
que ADR-003 quiere evitar: una barrera que parece estar puesta y no lo está.

Cada test inyecta temporalmente un módulo que viola una capa, ejecuta el linter
real contra el árbol real y comprueba que el contrato correspondiente sale como
BROKEN.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Nombre deliberadamente descriptivo: si un test muere sin limpiar (SIGKILL,
# corte de luz), el fichero huérfano se identifica de un vistazo en `git status`.
PROBE_NAME = "_probe_violacion_de_capas.py"

CONTRATO_CAPAS = "Capas: Composition root -> UI -> Application -> Domain"
CONTRATO_DOMINIO = "Pureza del dominio (solo stdlib + NumPy)"
CONTRATO_UI = "La UI no accede a infraestructura ni a Windows"
CONTRATO_APPLICATION = "Application declara ports, no conoce adaptadores"


def _argv_lint_imports() -> list[str]:
    """Invocación del linter que no depende del PATH del runner."""
    script = shutil.which("lint-imports")
    if script:
        return [script]
    return [
        sys.executable,
        "-c",
        "from importlinter.cli import lint_imports_command; lint_imports_command()",
    ]


def _ejecutar_lint_imports() -> subprocess.CompletedProcess[str]:
    """Corre el linter en subproceso, igual que lo hace CI.

    `--no-cache` es obligatorio: con la caché activa, un grafo antiguo podría
    ocultar el módulo infractor y el test pasaría por la razón equivocada.
    """
    return subprocess.run(
        [*_argv_lint_imports(), "--no-cache"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # NO_COLOR/COLUMNS evitan que rich meta códigos ANSI o parta los
        # nombres de contrato en varias líneas y rompa las aserciones.
        env={**os.environ, "NO_COLOR": "1", "COLUMNS": "200"},
        check=False,
    )


@contextmanager
def modulo_infractor(paquete: Path, import_ilegal: str) -> Iterator[None]:
    """Coloca un módulo que viola las capas y lo retira pase lo que pase."""
    sonda = paquete / PROBE_NAME
    sonda.write_text(
        '"""Módulo temporal de los tests de capas. Si lo ves versionado, bórralo."""\n\n'
        f"{import_ilegal}\n",
        encoding="utf-8",
    )
    importlib.invalidate_caches()
    try:
        yield
    finally:
        sonda.unlink(missing_ok=True)
        importlib.invalidate_caches()


def test_el_arbol_limpio_cumple_los_contratos() -> None:
    """Canario: si esto falla, las aserciones de los demás tests no prueban nada."""
    resultado = _ejecutar_lint_imports()
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


@pytest.mark.parametrize(
    ("paquete", "import_ilegal", "contrato"),
    [
        pytest.param(
            "packages/domain",
            "import persistence",
            CONTRATO_DOMINIO,
            id="dominio-importa-persistencia",
        ),
        pytest.param(
            "packages/domain",
            "import application",
            CONTRATO_CAPAS,
            id="dominio-importa-application",
        ),
        pytest.param(
            "apps/desktop",
            "import persistence",
            CONTRATO_UI,
            id="ui-importa-persistencia",
        ),
        pytest.param(
            "apps/desktop",
            "import ctypes",
            CONTRATO_UI,
            id="ui-importa-ctypes",
        ),
        pytest.param(
            "packages/application",
            "import persistence",
            CONTRATO_APPLICATION,
            id="application-importa-un-adaptador",
        ),
        pytest.param(
            "apps/desktop",
            "import openzonda",
            CONTRATO_CAPAS,
            id="ui-importa-el-composition-root",
        ),
    ],
)
def test_un_import_ilegal_rompe_los_contratos(
    paquete: str, import_ilegal: str, contrato: str
) -> None:
    with modulo_infractor(REPO_ROOT / paquete, import_ilegal):
        resultado = _ejecutar_lint_imports()

    salida = resultado.stdout + resultado.stderr
    assert resultado.returncode != 0, f"lint-imports pasó pese a «{import_ilegal}»:\n{salida}"
    assert f"{contrato} BROKEN" in salida, salida


def test_la_sonda_no_sobrevive_al_contexto() -> None:
    """La limpieza es parte del contrato: no se versiona basura de tests."""
    sonda = REPO_ROOT / "packages/domain" / PROBE_NAME
    with modulo_infractor(REPO_ROOT / "packages/domain", "import persistence"):
        assert sonda.exists()
    assert not sonda.exists()

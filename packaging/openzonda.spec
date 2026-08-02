# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller — bundle onedir de OpenZonda (F0.5).

`onedir` y no `onefile` a propósito: `onefile` se descomprime en un temporal en cada
arranque, lo que penaliza el tiempo de inicio y complica el modo portable, donde el
usuario espera ver la carpeta y su `portable.marker`.

La versión se resuelve desde el tag de git y se congela en `openzonda/_build_info.py`.
Dentro del bundle no hay metadatos de paquete ni repositorio, así que esta es la única
fuente fiable de versión en tiempo de ejecución.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(SPECPATH).parent
BUILD_INFO = REPO_ROOT / "apps" / "openzonda" / "_build_info.py"


def resolver_version() -> str:
    """Versión desde el tag de git; sin repo o sin tags, marcador de desarrollo."""
    try:
        salida = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "0.0.0+dev"
    descripcion = salida.stdout.strip()
    if salida.returncode != 0 or not descripcion:
        return "0.0.0+dev"
    return descripcion.removeprefix("v")


VERSION = resolver_version()
BUILD_INFO.write_text(
    '"""Generado por packaging/openzonda.spec. No editar ni versionar."""\n\n'
    f'VERSION = "{VERSION}"\n',
    encoding="utf-8",
)

# Módulos Qt que OpenZonda no usa. Sin estas exclusiones el bundle se va muy por encima
# del presupuesto de 180 MB del DoD: QtWebEngine por sí solo pesa más de 100 MB.
QT_NO_USADOS = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]

# Dependencias de desarrollo y de fases futuras que no deben viajar en el bundle de F0.
NO_DISTRIBUIBLES = [
    "pytest",
    "hypothesis",
    "mypy",
    "ruff",
    "importlinter",
    "grimp",
    "coverage",
    "tkinter",
    "matplotlib",
    "scipy",
    "PIL",
]

a = Analysis(
    [str(REPO_ROOT / "apps" / "openzonda" / "__main__.py")],
    pathex=[
        str(REPO_ROOT / "apps"),
        str(REPO_ROOT / "packages"),
    ],
    binaries=[],
    datas=[],
    hiddenimports=["desktop.app", "desktop.main_window"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=QT_NO_USADOS + NO_DISTRIBUIBLES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OpenZonda",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="OpenZonda",
)

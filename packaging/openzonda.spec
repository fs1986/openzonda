# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller — bundle onedir de OpenZonda (F0.5).

`onedir` y no `onefile` a propósito: `onefile` se descomprime en un temporal en cada
arranque, lo que penaliza el tiempo de inicio y complica el modo portable, donde el
usuario espera ver la carpeta y su `portable.marker`.

La versión se resuelve desde el tag de git y se congela en `openzonda/_build_info.py`.
Dentro del bundle no hay metadatos de paquete ni repositorio, así que esta es la única
fuente fiable de versión en tiempo de ejecución.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(SPECPATH).parent
BUILD_INFO = REPO_ROOT / "apps" / "openzonda" / "_build_info.py"
ICONO = REPO_ROOT / "packaging" / "windows" / "ico" / "openzonda.ico"
VERSION_INFO = REPO_ROOT / "build" / "version_info.txt"


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


def version_numerica(version: str) -> tuple[int, int, int, int]:
    """Traduce la versión de git a la cuaterna de enteros que exige Windows.

    El recurso VERSIONINFO solo admite números; un `git describe` como
    "0.0.1-3-gc85ecf9-dirty" no le sirve. Se toman los tres primeros componentes:

        v0.0.1            -> (0, 0, 1, 0)
        0.0.1-3-gc85ecf9  -> (0, 0, 1, 0)
        c85ecf9           -> (0, 0, 0, 0)   build de desarrollo

    Se prefiere (0,0,0,0) antes que inventar un número: un ejecutable que declara
    en sus propiedades una versión que no corresponde a ninguna release es peor que
    uno que se declara de desarrollo. La cadena exacta sí se conserva en el campo
    FileVersion, que es texto libre.
    """
    coincidencia = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", version)
    if not coincidencia:
        return (0, 0, 0, 0)
    mayor, menor, parche = (int(g) for g in coincidencia.groups())
    return (mayor, menor, parche, 0)


def escribir_version_info(destino: Path, version: str) -> Path:
    """Genera el recurso VERSIONINFO que Windows muestra en Propiedades → Detalles.

    Sin esto el ejecutable aparece sin nombre de producto ni copyright, y es
    indistinguible en el Administrador de tareas.
    """
    numerica = version_numerica(version)
    # 040904B0 = inglés (EE. UU.) + Unicode. Es el par de códigos convencional para
    # aplicaciones que no localizan sus metadatos; los strings en sí son legibles en
    # ambos idiomas del producto.
    contenido = f"""# Generado por packaging/openzonda.spec. No editar ni versionar.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numerica},
    prodvers={numerica},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'OpenZonda contributors'),
        StringStruct('FileDescription', 'OpenZonda - site surveys WiFi'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'OpenZonda'),
        StringStruct('LegalCopyright',
                     'Copyright (c) OpenZonda contributors. Apache License 2.0'),
        StringStruct('OriginalFilename', 'OpenZonda.exe'),
        StringStruct('ProductName', 'OpenZonda'),
        StringStruct('ProductVersion', '{version}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")
    return destino


VERSION = resolver_version()
BUILD_INFO.write_text(
    '"""Generado por packaging/openzonda.spec. No editar ni versionar."""\n\n'
    f'VERSION = "{VERSION}"\n',
    encoding="utf-8",
)
escribir_version_info(VERSION_INFO, VERSION)

if not ICONO.exists():
    raise SystemExit(
        f"Falta el icono en {ICONO}. Está versionado en el repositorio; "
        "si no aparece, la copia de trabajo está incompleta."
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
    # Las migraciones son archivos .sql, no módulos: el análisis de imports de PyInstaller
    # no las ve y el bundle arrancaría sin ellas. `discover_migrations()` fallaría al abrir
    # el primer proyecto, ya en la máquina del usuario y no en CI.
    datas=[
        (
            str(REPO_ROOT / "packages" / "persistence" / "migrations" / "*.sql"),
            "persistence/migrations",
        ),
        # Catálogos de traducción propios (OZ-35). Van junto al .exe, donde
        # `application_dir()/translations` los busca en runtime. Los `.qm` de Qt
        # (qtbase_*) los aporta el hook de PySide6.
        (str(REPO_ROOT / "translations" / "*.qm"), "translations"),
    ],
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
    icon=str(ICONO),
    version=str(VERSION_INFO),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="OpenZonda",
)

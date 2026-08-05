"""Rellena las traducciones al inglés en el .ts y compila el .qm (OZ-35, ADR-013).

El .ts se genera con `pyside6-lupdate` (escanea los `tr()`/`translate()` del código). Este
script inyecta las traducciones desde `TRANSLATIONS` (diccionario source→inglés, versionado
acá para revisarlo en el PR) y llama a `pyside6-lrelease` para producir `openzonda_en.qm`.

Flujo completo cuando se agregan/cambian strings de UI:

    uv run pyside6-lupdate apps/desktop/*.py -ts translations/openzonda_en.ts
    uv run python scripts/compile_translations.py            # rellena y compila

Falla ruidosamente si algún source del .ts no está en TRANSLATIONS: una cadena sin traducir
no debe pasar en silencio (quedaría en español dentro del inglés).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TS_PATH = Path("translations/openzonda_en.ts")
QM_PATH = Path("translations/openzonda_en.qm")

# source (español, tal como aparece en el código) -> inglés. Los placeholders {…} se conservan.
TRANSLATIONS: dict[str, str] = {
    # --- chrome / MainWindow ---
    "Proyectos OpenZonda (*.wifisurvey)": "OpenZonda projects (*.wifisurvey)",
    "Imágenes de plano (*.png *.jpg *.jpeg)": "Floor plan images (*.png *.jpg *.jpeg)",
    "Sitios y plantas": "Sites and floors",
    "Proyecto": "Project",
    "&Archivo": "&File",
    "&Nuevo": "&New",
    "&Abrir…": "&Open…",
    "&Guardar": "&Save",
    "Guardar &como…": "Save &as…",
    "&Cerrar proyecto": "&Close project",
    "&Recientes": "&Recent",
    "&Salir": "&Quit",
    "Sin proyecto": "No project",
    "Trabajando…": "Working…",
    "(sin guardar)": "(unsaved)",
    "(sin proyectos recientes)": "(no recent projects)",
    "  (no disponible)": "  (unavailable)",
    "Abrir proyecto": "Open project",
    "Guardar proyecto como": "Save project as",
    "Cambios sin guardar": "Unsaved changes",
    "El proyecto tiene cambios sin guardar.": "The project has unsaved changes.",
    "¿Querés guardarlos antes de continuar?": "Do you want to save them before continuing?",
    "Nuevo sitio": "New site",
    "Nombre del sitio:": "Site name:",
    "Renombrar": "Rename",
    "Nuevo nombre:": "New name:",
    "Elegir plano": "Choose floor plan",
    "Nueva planta": "New floor",
    "Nombre de la planta:": "Floor name:",
    "Nivel (0 = planta baja):": "Level (0 = ground floor):",
    "Eliminar": "Delete",
    "¿Eliminar {que}? Esta acción no se puede deshacer.": (
        "Delete {que}? This action cannot be undone."
    ),
    "No se pudo cargar el plano": "Could not load the floor plan",
    "Calibrar": "Calibrate",
    "Distancia real entre los dos puntos (metros):": (
        "Real distance between the two points (meters):"
    ),
    "&Idioma": "&Language",
    "Automático (sistema)": "Automatic (system)",
    "Español": "Spanish",
    "English": "English",
    "Idioma": "Language",
    "El idioma se aplicará la próxima vez que abras OpenZonda.": (
        "The language will take effect the next time you open OpenZonda."
    ),
    # --- árbol ---
    "+ Sitio": "+ Site",
    "+ Planta": "+ Floor",
    "Cargar plano…": "Load floor plan…",
    "Renombrar…": "Rename…",
    "Seleccioná una planta para ver su plano.": "Select a floor to see its plan.",
    "{nombre}  ·  nivel {nivel}": "{nombre}  ·  level {nivel}",
    "el sitio": "the site",
    "la planta": "the floor",
    "Plano: {resumen}": "Plan: {resumen}",
    # --- inicio ---
    "Nuevo proyecto": "New project",
    "Abrir proyecto…": "Open project…",
    "Recientes": "Recent",
    "Quitar de recientes": "Remove from recent",
    "No hay proyectos recientes todavía.": "No recent projects yet.",
    "{nombre}  —  no disponible": "{nombre}  —  unavailable",
    # --- proyecto ---
    "Nombre": "Name",
    "Archivo": "File",
    # --- visor ---
    "Ajustar": "Fit",
    "Rotar 90°": "Rotate 90°",
    "Calibrar…": "Calibrate…",
    "Sin planta seleccionada.": "No floor selected.",
    # --- errores (shell) ---
    "No se pudo editar el proyecto": "Could not edit the project",
    "No se pudo abrir el proyecto": "Could not open the project",
    # --- honestidad del plano (floorplan) ---
    "del archivo": "from file",
    "derivado": "derived",
    "asumido": "assumed",
    "predicho": "predicted",
    "por defecto": "default",
    "rotación": "rotation",
    "calibrado": "calibrated",
    "sin calibrar": "uncalibrated",
    "Sin calibrar — las distancias del plano no tienen escala todavía.": (
        "Uncalibrated — the plan's distances have no scale yet."
    ),
    "Escala: 1 px = {mpp} m · incertidumbre ±{rel}% (calibrado sobre {dist})": (
        "Scale: 1 px = {mpp} m · uncertainty ±{rel}% (calibrated over {dist})"
    ),
}


def main() -> int:
    if not TS_PATH.is_file():
        print(f"No existe {TS_PATH}; generalo con pyside6-lupdate primero.", file=sys.stderr)
        return 2

    tree = ET.parse(TS_PATH)
    faltantes: list[str] = []
    for message in tree.getroot().iter("message"):
        origen = message.find("source")
        traduccion = message.find("translation")
        if origen is None or traduccion is None or origen.text is None:
            continue
        ingles = TRANSLATIONS.get(origen.text)
        if ingles is None:
            faltantes.append(origen.text)
            continue
        traduccion.text = ingles
        traduccion.attrib.pop("type", None)  # deja de estar 'unfinished'

    if faltantes:
        print("Faltan traducciones para:", file=sys.stderr)
        for s in faltantes:
            print(f"  - {s!r}", file=sys.stderr)
        return 1

    tree.write(TS_PATH, encoding="utf-8", xml_declaration=True)

    lrelease = shutil.which("pyside6-lrelease")
    if lrelease is None:
        print("pyside6-lrelease no está en PATH; instalá el extra 'ui'.", file=sys.stderr)
        return 2
    subprocess.run([lrelease, str(TS_PATH), "-qm", str(QM_PATH)], check=True)
    print(f"OK: {len(TRANSLATIONS)} traducciones -> {QM_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

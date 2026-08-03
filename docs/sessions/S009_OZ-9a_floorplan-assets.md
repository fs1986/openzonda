# S009 · OZ-9a · Árbol Site→Floor + carga de plano + almacén de assets [HW]

Fecha: 2026-08-03 · Fase: F1 · Rama: `feature/oz-9-floorplan-assets` · **EN PROGRESO (handoff)**

> Documento de traspaso: la tarjeta NO está terminada. Se implementó el incremento 1 de 5
> (verde y commiteado); los incrementos 2–5 quedan pendientes. Estado detallado abajo.

## Contexto y partición

OZ-9 (F1.5) se partió en **OZ-9a** (esta: árbol + carga de plano + almacén de assets, cierra
la decisión estructural) y **OZ-36** (F1.5b: visor `QGraphicsView` + calibración). OZ-9a
bloquea OZ-36. Ambas convergen en la tanda de validación `[HW]` de `0.1.0-alpha.1` (OZ-10).

## DoD contrastable aprobado por el PO

Verificable por **CI**: (1) round-trip del plano por hash; (2) entrada content-addressed;
(3) extensión por magic bytes, no por nombre + caso hostil; (4) dedup por hash; (5) límite con
rechazo que **distingue px vs. bytes** y da el valor real; (6) DPI con procedencia en dominio;
(7) procedencia del DPI sobrevive el round-trip; (8) árbol Site→Floor headless; (9) migración
0002; (10) gate. Verificable **[HW]** en la tanda alpha.1: (11) cargar plano real desde el
`.exe`; (12) DPI con procedencia en la UI (doble codificación); (13) round-trip visible.

## Decisiones tomadas (aún NO en ADR — pendientes de escribir en el incremento 5)

1. **`FloorPlan.dpi` es `Measured[float]`**, no un campo de procedencia separado. Motivo: un
   campo aparte se puede ignorar; envolver el número en `Measured` hace que un DPI asumido no
   pueda leerse ni usarse como medido (ADR-006). Respondió las dos preguntas del PO: casi
   ningún call-site lee `dpi` para calcular, y el patrón de OZ-5 es `Measured[T]`. → **ADR pendiente**.
2. **Assets content-addressed**: entrada `assets/<sha256>.<ext>`, **extensión derivada por
   magic bytes** (contenido), NO por el nombre del archivo del usuario — si no, `plano.png` y
   `plano.PNG` con bytes idénticos romperían el dedup. **Dedup por hash**. → **ADR pendiente**.
3. **Encuadre = solo viewport (no persistente)**, y va en OZ-36, no acá. En OZ-9a solo
   `rotation_degrees` si aplica.
4. **Límites**: ~12000×12000 px / ~50 MB. Rechazo con mensaje que **distingue** el caso
   (px vs. bytes) y da el valor real y el violado. Nunca fallo silencioso ni truncado.
5. **Resumen textual del plano en OZ-9a** (dimensiones, tamaño, DPI + procedencia): OZ-9a
   carga/almacena pero NO renderiza (el visor es OZ-36); el resumen es lo que hace validable la
   honestidad del DPI sin depender del visor.
6. **Formatos**: PNG/JPG. **Unidades**: solo métrico en alpha.

## Incrementos — estado

| # | Incremento | Estado |
| --- | --- | --- |
| **1** | **DPI honesto**: `FloorPlan.dpi → Measured[float]`; migración `0002_dpi_provenance`; repo persiste value+provenance; tests (incl. que un DPI observado no vuelve degradado). | ✅ **HECHO** — verde, commit `337cc9a`. 62 tests, mypy dominio strict OK, gate limpio. |
| **2** | **Módulo de imagen** (nuevo, en `persistence` o `application`): detectar PNG/JPG por magic bytes; leer dimensiones; leer DPI del EXIF si existe (→ `OBSERVED`) o asumir 96 (→ `ESTIMATED`); rechazar no-imagen renombrada; rechazar > límites con mensaje que distingue px/bytes. | ⬜ **SIGUE ACÁ** |
| **3** | **Assets content-addressed en `WifiSurveyProjectStore`**: poblar `assets=` en `save` (hoy `{}`) con `assets/<sha256>.<ext>`; dedup por hash; al abrir, dejar los assets accesibles; test de round-trip del plano por hash. | ⬜ pendiente |
| **4** | **Árbol Site→Floor + carga de plano**: servicio de edición del proyecto (add/rename/remove Site y Floor; cargar plano en un Floor) en `application`; ViewModel headless del árbol; UI (dock del árbol + resumen textual del plano con DPI/procedencia, doble codificación). | ⬜ pendiente |
| **5** | **ADR** (assets content-addressed + DPI `Measured`), CHANGELOG, completar este S009, gate final, PR. Luego: **medición de render 8000×6000** antes de OZ-36 (reportar el número aunque sea bueno). | ⬜ pendiente |

## Lo próximo exacto

Empezar el **incremento 2 (módulo de imagen)** con TDD: un módulo que recibe bytes y devuelve
`(formato, width_px, height_px, dpi: Measured[float])` o lanza un error tipado; tests con
fixtures PNG/JPG mínimos, un no-imagen renombrado a `.png` (rechazo), y superar límites
(mensajes distintos px vs. bytes). Ese módulo alimenta el incremento 3 (nombre de entrada por
formato) y el 4 (resumen en UI).

## Artefactos del incremento 1

| Archivo | Cambio |
| --- | --- |
| `packages/domain/project.py` | `FloorPlan.dpi: Measured[float]` + validación por `.value` |
| `packages/persistence/migrations/0002_dpi_provenance.sql` | columna `dpi_provenance` (default `estimated`) |
| `packages/persistence/project_repository.py` | escribe/lee value+provenance |
| `tests/unit/test_project_entities.py` · `tests/integration/test_project_repository.py` · `test_project_store.py` | construcciones actualizadas + tests de honestidad y round-trip de procedencia |

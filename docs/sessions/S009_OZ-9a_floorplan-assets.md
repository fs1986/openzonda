# S009 · OZ-9a · Árbol Site→Floor + carga de plano + almacén de assets [HW]

Fecha: 2026-08-03 · Fase: F1 · Rama: `feature/oz-9-floorplan-assets` · **COMPLETA (pendiente `[HW]` + merge del PO)**

## Contexto y partición

OZ-9 (F1.5) se partió en **OZ-9a** (esta: árbol + carga de plano + almacén de assets, cierra
la decisión estructural) y **OZ-36** (F1.5b: visor `QGraphicsView` + calibración). OZ-9a
bloquea OZ-36. Ambas convergen en la tanda de validación `[HW]` de `0.1.0-alpha.1` (OZ-10).

## Decisiones (ahora en ADR-015)

1. **`FloorPlan.dpi` es `Measured[float]`**, no un `float` con enum separado: el tipo impone
   ADR-006, el número no existe crudo.
2. **Assets content-addressed** `assets/<sha256>.<ext>`, extensión por **magic bytes**
   (contenido, no nombre), **dedup por hash**.
3. **Plano obligatorio por planta** (decisión del PO): agregar planta es atómico (nombre +
   nivel + imagen); no existe planta a medias. "Cargar plano en una planta" = reemplazar el
   plano de una planta existente. Sin cambio de dominio/esquema. El modelo "planta sin plano"
   queda para una tarjeta futura con su ADR.
4. **Encuadre = solo viewport** (OZ-36, no acá). En OZ-9a solo `rotation_degrees`.
5. **Límites** ~12000 px/lado / ~50 MB; rechazo que **distingue px de bytes** con el valor
   real. Formatos PNG/JPG; BMP/TIFF/WEBP reconocidos y rechazados con mensaje claro.

### Sub-decisiones del incremento 4 (resueltas con criterio, consistentes con el patrón)

- **Carga de plano async** por el `TaskExecutor` (regla >50 ms de CLAUDE.md: leer+hashear una
  imagen grande lo supera). Reusa la maquinaria de generación/staleness de OZ-34.
- **Errores tipados nuevos**: `INVALID_PLAN` (imagen no válida/aceptable) e `INVALID_EDIT`
  (regla de dominio: nombre/nivel duplicado, nombre vacío). Ambos por el canal `on_error`
  existente; el título se enruta por tipo en el `ShellViewModel`. Un error de edición se emite
  por listener, nunca crashea el slot de Qt.
- **Árbol → UI**: `ProjectState` gana `project: Project | None` (frozen, solo lectura). Evita
  duplicar el árbol en tipos-resumen.

## DoD contrastable — evidencia (Regla A)

Verificable por **CI** (todo verde; `uv run pytest` → **308 passed**):

| # | Punto del DoD | Evidencia (test / comando) |
| --- | --- | --- |
| 1 | Round-trip del plano por hash | `test_project_store.py::test_round_trip_del_plano_por_hash` (los bytes sobreviven guardar+reabrir) |
| 2 | Entrada content-addressed `assets/<sha256>.<ext>` | `test_store_asset_devuelve_el_sha256_del_contenido` |
| 3 | Extensión por magic bytes + caso hostil | `test_plan_image.py::test_png_por_magic_bytes_no_por_nombre`, `test_rechaza_no_imagen_renombrada`, `test_rechaza_formato_reconocido_pero_no_soportado` |
| 4 | Dedup por hash | `test_store_asset_deduplica_por_hash` (un solo archivo en disco pese a dos `store`) |
| 5 | Límite con rechazo px vs. bytes | `test_rechaza_exceso_de_pixeles_distinguiendo_px`, `test_rechaza_exceso_de_bytes_distinguiendo_bytes` |
| 6 | DPI con procedencia en dominio | `test_plan_image.py` (pHYs/JFIF/EXIF → OBSERVED; ausente → ESTIMATED 96) |
| 7 | Procedencia del DPI sobrevive el round-trip | `test_project_repository.py` (round-trip de procedencia; observado no vuelve degradado) |
| 8 | Árbol Site→Floor headless | `test_project_service.py` (add/rename/remove sitio y planta; add_floor carga plano) + `test_floorplan_viewmodel.py` |
| 9 | Migración 0002 | `test_migrations.py` (incremento 1, commit `337cc9a`) |
| 10 | Gate | `ruff check .` OK · `mypy domain rf_engine --strict` OK · `lint-imports` 4/4 KEPT · pytest 308 passed |

Verificable **[HW]** en la tanda `0.1.0-alpha.1` (pendiente del PO en VM build 26200):

| # | Punto | Cómo validar |
| --- | --- | --- |
| 11 | Cargar un plano real desde el `.exe` | Abrir la app instalada, crear sitio+planta, elegir un PNG/JPG real; la planta aparece con su resumen |
| 12 | DPI con procedencia en la UI (doble codificación) | El resumen muestra "N dpi · del archivo" (JPG con EXIF) o "96 dpi · asumido (por defecto)" (PNG sin resolución) |
| 13 | Round-trip visible | Guardar, cerrar, reabrir: el árbol y el resumen del plano se conservan |

## Medición de render (previa a OZ-36)

Pixmap sintético **8000×6000 (48 MP, ~192 MB)**, plataforma Qt `offscreen`, raster CPU:

| Operación | ms/frame |
| --- | --- |
| fit-to-view (transformación suave) | **1.83** |
| fit-to-view (rápido) | 1.39 |
| pan 1:1 (recorte a viewport) | 0.16 |

**Conclusión**: un **único `QPixmap` alcanza** para el visor de OZ-36 — el peor caso
(fit-to-view suave de 48 MP) está muy por debajo de 16 ms (60 fps). **No hace falta
tiling ni mipmaps** en el alpha. El coste real a tener en cuenta es la **memoria**: ~192 MB
por plano a resolución completa, así que solo la planta activa debería mantener un pixmap
vivo. (El tiempo de "construcción" del fixture en Python no es representativo: la carga real
es un decode de PNG único, no un bucle por scanline.)

## Incrementos — estado final

| # | Incremento | Commit |
| --- | --- | --- |
| 1 | DPI honesto (`Measured[float]`) + migración 0002 | `337cc9a` ✅ |
| 2 | Módulo de imagen (`plan_image`): formato/dimensiones/DPI, rechazo px vs. bytes | `685a777` ✅ |
| 3 | Assets content-addressed en el store (store/read_asset, dedup, round-trip) | `b998175` ✅ |
| 4 | Árbol Site→Floor + carga de plano (servicio + ViewModel + dock UI) | `e699cd9` ✅ |
| 5 | ADR-015, CHANGELOG, este log, medición de render, gate final, PR | (este commit) ✅ |

## Artefactos

| Archivo | Cambio |
| --- | --- |
| `packages/application/plan_image.py` | Módulo puro: bytes → `PlanImage` o `PlanImageError` tipado |
| `packages/application/project_service.py` | Ediciones del árbol, carga async de plano, `INVALID_PLAN`/`INVALID_EDIT`, `ProjectState.project` |
| `packages/persistence/project_store.py` | `store_asset`/`read_asset` content-addressed; `save` puebla `assets=` |
| `apps/desktop/floorplan_viewmodel.py` | ViewModel del árbol + resumen honesto del plano |
| `apps/desktop/main_window.py` | Dock del árbol + resumen + acciones |
| `apps/desktop/shell_viewmodel.py` | Título de error enrutado por tipo |
| `ADR/ADR-015-...md` | Decisión: assets content-addressed + DPI `Measured` |
| Tests | `test_plan_image.py` (16), `test_project_store.py` (+5), `test_project_service.py` (+15), `test_floorplan_viewmodel.py` (11), `test_main_window.py` (+1) |

## HALLAZGOS (fuera de alcance — el PO decide)

- **mypy no cubre `apps/desktop` ni `apps/openzonda`.** `app.py` ya arrastraba un `type: ignore`
  sin usar y la CI solo corre mypy strict sobre `domain`+`rf_engine`. La UI queda sin chequeo
  de tipos. Candidato a una tarjeta de deuda (añadir un target mypy no-strict para `desktop`).
- **Selección del árbol tras editar**: se preserva por `id`, pero un árbol muy grande recorre
  todos los nodos para reseleccionar. Irrelevante a la escala del alpha; anotado por si crece.
- **`set_floor_plan` deja el asset anterior huérfano** en el working dir si el hash cambia (no
  se recolecta). Inocuo (dedup + barrido de working dirs), pero un GC de assets no referenciados
  sería prolijo. Candidato a deuda menor.

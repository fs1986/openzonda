# S010 · OZ-36 · Visor del plano + calibración de 2 puntos [HW]

Fecha: 2026-08-03 · Fase: F1 · Rama: `feature/oz-36-visor-calibracion` · **COMPLETA (CI verde; `[HW]` + merge pendientes del PO)**

> Ejecutada bajo `/goal` (loop de objetivo, tope 8 intentos). Cerrada en el **intento 1**.

## Contexto

OZ-36 (F1.5b) es el visor `QGraphicsView` del plano + calibración, sobre la base estructural
de OZ-9a. El tiempo de render ya estaba resuelto por la medición de OZ-9a (1.83 ms/frame para
48 MP); esta tarjeta cierra la memoria (ADR-016) y la calibración honesta. Valida `[HW]` junto
con OZ-9a en la tanda `0.1.0-alpha.1` (OZ-10).

## Decisiones (en ADR-016)

- **Un solo pixmap vivo, el de la planta activa**; cambiar de planta libera el anterior. Sin
  tiling/mipmaps en el alpha (la medición de OZ-9a mostró que un `QPixmap` alcanza).
- **Escena en píxeles de imagen**: zoom/pan/rotación viven en la vista, así la calibración se
  captura en coordenadas de imagen, invariante al zoom. Encuadre no persistente; solo
  `rotation_degrees` en el modelo.
- **Lectura del asset para el pixmap: I/O síncrono** en el hilo de UI (archivo local acotado a
  ~50 MB). Deuda con disparador si en `[HW]` llega a notarse (ver HALLAZGOS).

## DoD contrastable — evidencia (Regla A)

Verificable por **CI** (todo verde; `uv run pytest` → **325 passed**):

| # | Punto del DoD | Evidencia (test / comando) |
| --- | --- | --- |
| C1 | El visor arma el pixmap del plano desde los bytes del asset | `test_main_window.py::test_pixmap_desde_bytes_conserva_dimensiones` |
| C2 | Calibración de 2 puntos persiste (escala + incertidumbre) y round-trip por el store | `test_project_service.py::test_set_floor_calibration_deriva_escala_e_incertidumbre` + `test_project_repository.py` (round-trip de `Calibration`, columnas cal all-or-nothing por CHECK) |
| C3 | Los puntos se toman en coordenadas de imagen, invariantes al zoom | `test_main_window.py::test_calibracion_captura_coordenadas_de_imagen_invariantes_al_zoom` |
| C4 | Escala e incertidumbre **siempre** visibles; sin calibrar lo dice, no un 0 | `test_floorplan_viewmodel.py::test_calibration_summary_*` (incl. distancia larga reduce el error) + wiring `test_seleccionar_planta_muestra_el_plano_y_calibrar_actualiza_la_escala` |
| C5 | Encuadre solo viewport (no se persiste); `rotation_degrees` sí | `test_set_floor_rotation_persiste` (rotación en el modelo); el zoom/pan/fit no tienen campo — no hay estado de viewport que guardar |
| C6 | Memoria: solo el pixmap de la planta activa vive; cambiar libera el anterior | `test_visor_viewmodel.py::test_active_plan_libera_el_anterior_al_cambiar_de_planta` (y no recarga la misma) |
| C7 | ADR-016 + CHANGELOG + este log | archivos presentes |
| C8 | Gate | `ruff check` OK · `ruff format --check` OK (118 archivos) · `mypy domain rf_engine --strict` OK · `lint-imports` 4/4 KEPT · pytest 325 · smoke `--smoke` exit 0 |

Verificable **[HW]** en la tanda `0.1.0-alpha.1` (PO en VM build 26200) — **enganchados, no cerrados a favor**:

| # | Punto | Cómo validar |
| --- | --- | --- |
| H1 | El plano real se ve renderizado desde el `.exe`; zoom/pan/fit/rotar responde | abrir un `.wifisurvey` con plano y operar el visor |
| H2 | Calibrar clicando 2 puntos e ingresando la distancia muestra escala **e incertidumbre** siempre | flujo de calibración completo en la app |
| H3 | Al cambiar de planta con planos grandes reales, la memoria no acumula | observar RAM al alternar plantas |

## Huecos de diseño vigilados (ninguno forzó parar el loop)

- **Calibración vs. reemplazo de plano** (lo había marcado como riesgo): NO forzó decisión en
  esta tarjeta. `set_floor_plan` reemplaza el plano y **conserva** la calibración anterior; si
  las dimensiones cambian, la escala vieja podría no corresponder. No lo resolví por criterio:
  es una decisión de honestidad que merece su propia discusión con el PO. Va a HALLAZGOS, no
  se toca acá (el alcance de OZ-36 es visor + calibración, no la política de invalidación).
- Unidad de la distancia real: el input y el resumen usan **metros**, coherente con el dominio.

## Artefactos

| Archivo | Cambio |
| --- | --- |
| `packages/application/project_service.py` | `set_floor_calibration`, `set_floor_rotation`, `read_plan_bytes`/`read_asset_by_sha` |
| `apps/desktop/visor_viewmodel.py` | `fit_scale` + `ActivePlan` (disciplina de memoria) |
| `apps/desktop/floorplan_viewmodel.py` | `calibration_summary` (escala + incertidumbre siempre) |
| `apps/desktop/main_window.py` | `_Lienzo` (QGraphicsView), `_VisorPanel`, cableado selección→visor→calibración/rotación |
| `ADR/ADR-016-...md` | Estrategia de render del visor |
| Tests | `test_visor_viewmodel.py` (9), `test_project_service.py` (+4), `test_floorplan_viewmodel.py` (+3), `test_main_window.py` (+3) |

## HALLAZGOS (fuera de alcance — el PO decide)

- **Política de calibración al reemplazar el plano**: hoy `set_floor_plan` conserva la
  calibración; si el plano nuevo tiene otras dimensiones, la escala podría quedar
  desactualizada sin aviso. Candidato a decisión de honestidad + tarjeta (¿invalidar la
  calibración al reemplazar? ¿avisar?).
- **Lectura síncrona del plano para el pixmap**: >50 ms posible con planos de ~50 MB. Deuda con
  disparador: mover al worker si en `[HW]` janquea al cambiar de planta.
- **mypy no cubre `apps/desktop`**: ya reportado en OZ-9a; el visor agranda la superficie sin
  tipar. Refuerza esa tarjeta de deuda.

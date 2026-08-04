# ADR-016 — Render del visor: un solo pixmap, solo la planta activa

- **Estado:** Aceptado
- **Fecha:** 2026-08-03
- **Decisores:** architect, dev-ui, el fundador (PO)

## Contexto

El visor de OZ-36 muestra el plano de una planta sobre un `QGraphicsView`. La medición de
render de OZ-9a resolvió la pregunta del *tiempo*: un `QPixmap` de 8000×6000 (48 MP) se
repinta en ~1.8 ms/frame con escalado suave, muy por debajo de 16 ms (60 fps). Quedaba la
pregunta de la *memoria*: ese mismo pixmap ocupa ~192 MB en RAM, y un proyecto puede tener
varias plantas. Cargar todos los planos a la vez escalaría el consumo sin límite útil.

## Decisión

**Un solo pixmap vivo: el de la planta activa.** Al cambiar de planta, el plano anterior se
libera antes de cargar el nuevo (guardián `ActivePlan`). Cargar la misma planta dos veces no
recarga. **Sin tiling ni mipmaps** en el alpha: la medición muestra que un único pixmap
alcanza para el tiempo de frame, así que la complejidad de un esquema por tiles no se paga.

La **escena está en píxeles de imagen**: el pixmap va en el origen, sin escalar ni rotar.
Zoom, pan y rotación viven en la transformación de la *vista*, así que `mapToScene` los
invierte y los dos puntos de calibración se capturan en coordenadas de imagen, invariantes al
zoom con que el usuario los marcó. El **encuadre (zoom/pan/fit) no se persiste**; solo
`rotation_degrees` vive en el modelo (decisión de producto del PO).

## Consecuencias

- **Positivas:**
  - Consumo de memoria acotado: ~192 MB en el peor caso (un plano de 48 MP), no N×192 MB.
  - Calibración correcta por construcción: al medir sobre coordenadas de imagen, la escala no
    depende del zoom de pantalla con que se marcaron los puntos.
  - Implementación simple: `QGraphicsView` nativo, sin motor de tiles que mantener.
- **Aceptadas:**
  - Cambiar de planta recarga (decodifica) el plano. Es aceptable: la decodificación de un
    PNG/JPG es rápida y el cambio de planta es una acción deliberada, no un bucle de frame.
  - La lectura del asset para armar el pixmap es **I/O síncrono** en el hilo de la UI (lee el
    archivo ya extraído en el working dir, acotado a ~50 MB). Si en `[HW]` con planos grandes
    reales llega a notarse, mover esa lectura al worker es deuda con disparador (no antes:
    sería optimización sin evidencia).
- **Alternativas descartadas:**
  - **Tiling/mipmaps**: innecesario para el tiempo de frame medido; complejidad sin retorno
    en el alcance actual. Se reconsiderará si aparecen planos por encima de los límites de
    OZ-9a o superposición de capas (heatmap) que cambien el perfil de render.
  - **Rotar el item de la escena** (en vez de la vista): rompería la equivalencia escena =
    píxeles de imagen y complicaría la calibración.

## Verificación

- `tests/unit/test_visor_viewmodel.py`: `ActivePlan` libera el plano anterior al cambiar de
  planta y no recarga la misma; `fit_scale` encuadra por el lado limitante.
- `tests/integration/test_main_window.py`:
  `test_calibracion_captura_coordenadas_de_imagen_invariantes_al_zoom` (los puntos son
  coordenadas de imagen a cualquier zoom) y el cableado selección→visor→calibración.
- El consumo (~192 MB por plano) y el tiempo de frame vienen de la medición de OZ-9a
  registrada en `docs/sessions/S009_OZ-9a_floorplan-assets.md`.

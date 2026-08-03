# S008 · OZ-8 · Shell UI: proyectos [HW]

Fecha: 2026-08-03 · Fase: F1 · Rama: `feature/oz-8-shell-projects`

Primera convergencia real **dominio ↔ repositorio SQLite ↔ contenedor `.wifisurvey`**. Cierra
las verificaciones diferidas de OZ-6/OZ-7.

## Objetivo (de la tarjeta)

F1.4: MainWindow con docks, ViewModels, crear/abrir/guardar/recientes/dirty. DoD: `[HW]` flujo
completo (crear/abrir/guardar/cerrar) verificado por el fundador; ViewModels con tests headless.

## Alcance acordado con el PO (antes de codificar)

Tres decisiones estructurales se resolvieron con el fundador y quedaron en ADR:

1. **Solo shell + ciclo de archivo**, sin carga de plano/calibración (F1.5) — evita arrastrar
   el almacén de assets (`assets={}` por ahora).
2. **Modelo documento** (ADR-010): abrir extrae, guardar re-empaqueta atómico.
3. **Shell única con vista central reemplazable** (ADR-011), no diálogo de bienvenida.

**Fuera:** carga de plano, captura/survey, docks del árbol, onboarding/`health()` real (OZ-16,
solo enganche), persistencia de `SurveySession`, worker-thread para I/O (deuda, tarjeta aparte).

## DoD contrastado con evidencia

Verificable en CI (headless), corrido en `main` de la rama:

| Punto | Comando | Resultado |
| --- | --- | --- |
| Ciclo de vida del proyecto (servicio puro) | `pytest tests/unit/test_project_service.py` | **14 passed** |
| ViewModels headless (sin QApplication) | `pytest tests/unit/test_shell_viewmodel.py` | **16 passed** |
| Round-trip real + kill-save (glue) | `pytest tests/integration/test_project_store.py` | **8 passed** |
| Shell Qt (offscreen): Inicio↔Proyecto, geometría | `pytest tests/integration/test_main_window.py` | **7 passed** |
| Migración settings v1→v2 | `pytest tests/integration/test_settings_json.py` | **12 passed** |

Gate completo:

```
uv run ruff check .                         All checks passed!
uv run ruff format --check .                102 files already formatted
uv run mypy packages/domain packages/rf_engine --strict   Success
uv run lint-imports                         Contracts: 4 kept, 0 broken
uv run pytest                               258 passed
QT_QPA_PLATFORM=offscreen python -m openzonda --smoke 600   exit 0 (la shell arranca real)
```

Tests: 215 → **258**.

**`[HW]` pendiente del fundador** (no cerrable con tests unitarios): flujo completo desde el
`.exe` instalado en la VM build 26200, que además ejercita `importlib.resources` en frozen.
Checklist en `docs/validacion/oz-8-validacion-vm.md`.

## Diferidas de OZ-6/OZ-7 que se cierran

1. **Glue contenedor↔repositorio**: `WifiSurveyProjectStore` + round-trip real por datos
   (`test_project_store.py`). ✔ en CI.
2. **`importlib.resources` desde el ejecutable congelado**: se ejercita al abrir/guardar un
   proyecto real desde el `.exe`. ✔ **solo** en la validación `[HW]` (los tests corren desde
   fuente). Queda enganchado al checklist.

## Cómo se resolvieron los riesgos de integración

- **WAL + working dir**: antes de empaquetar, `PRAGMA wal_checkpoint(TRUNCATE)` y cierre de la
  conexión, para que el `.sqlite` sea un único archivo consistente sin `-wal`.
- **Guardado atómico** sobre el `.wifisurvey` de destino: `write_container` (temporal +
  `os.replace`). Kill-test a nivel `store.save`: matar el proceso a mitad conserva el original.
- **Working dirs huérfanos**: barrido conservador al arrancar; un `session.lock` abierto impide
  borrar el working dir de otra instancia viva (Windows).
- **Assets**: sin plano en OZ-8 → `assets={}`; el almacén real llega en F1.5.

## Restricciones de diseño respetadas

- **Honestidad metrológica**: la shell no fabrica datos; el dominio sigue siendo la fuente
  (SNR = `Unavailable`), la UI no lo toca.
- **Accesibilidad**: atajos visibles (Ctrl+N/O/S), y los recientes rotos se marcan con **ícono
  + texto** «no disponible», nunca solo color.
- **Sin autosave** en alpha (ADR-010): guardado explícito.

## Decisiones / ADR

- **ADR-010** — Proyecto como documento (extraer/re-empaquetar).
- **ADR-011** — Shell única con vista central reemplazable.
- **Deuda registrada como tarjeta Jira** (no solo nota): mover el I/O a un worker con
  cancelación. Disparador: entra plano/captura, o el I/O supera ~200 ms.

## Artefactos

| Archivo | Contenido |
| --- | --- |
| `packages/application/project_service.py` | Port `ProjectStore`, `ProjectService` (dirty/recientes), estado/errores |
| `packages/persistence/project_store.py` | `WifiSurveyProjectStore`: el glue documento↔repo↔contenedor |
| `packages/application/settings.py` · `persistence/settings_json.py` | Settings v2 + migración v1→v2 |
| `apps/desktop/shell_viewmodel.py` | ViewModel headless de la shell |
| `apps/desktop/main_window.py` · `app.py` | Ventana única, vistas Inicio/Proyecto, diálogos nativos |
| `apps/openzonda/__main__.py` | Cableado del store + servicio; barrido de huérfanos al arrancar |
| `ADR/ADR-010`, `ADR/ADR-011` | Decisiones estructurales |
| `docs/validacion/oz-8-validacion-vm.md` | Checklist `[HW]` para el PO |

## Validación [HW] del PO — VM Windows 11 build 26200, MSI 0.0.4 (2026-08-03)

Resultado: **4 de 5 verdes, 1 bloqueante corregido**. OZ-8 sigue en **In Review** hasta que el
fix del dirty se mergee y el PO lo revalide.

- ✅ **Ciclo de archivo desde el `.exe`** (crear→guardar→cerrar→reabrir). Con esto queda
  **cerrada la diferida de OZ-6/OZ-7**: `importlib.resources` corrió en el binario congelado y
  las migraciones se leyeron desde el bundle. Es la verificación que no se podía hacer en pytest.
- ✅ **Recientes**: aparece al guardar; al mover el archivo se marca «no disponible» con ícono +
  texto; «Quitar de recientes» la saca; sin borrado silencioso.
- ✅ **Working dir huérfano** (observación directa de `%LOCALAPPDATA%\OpenZonda\cache\projects\`):
  app cerrada → la ruta no existe; proyecto abierto → `<hash>\` con `data\survey.sqlite`,
  `manifest.json`, `session.lock`; proceso matado desde el Administrador de tareas → carpeta
  huérfana y `session.lock` pasa de 0 a 4 bytes; app reabierta → `projects\` vacía (el barrido
  limpió). Comportamiento exacto del diseño.
- ✅ **Modo oscuro**: correcto. Validado **en el host** (la VM no tiene el tema del SO activado),
  registrado como validado fuera de VM.
- ❌→✔ **BLOQUEANTE corregido — dirty por `editingFinished`**: el flag se marcaba solo al perder
  el foco del campo Nombre; editar y cerrar con la X sin salir del campo perdía la edición sin el
  diálogo «¿guardar?». Es justo el fallo que el flag previene. Corregido: `editingFinished` →
  **`textEdited`** (marca el cambio en el acto). Se eligió `textEdited` y no un commit en
  `closeEvent` porque el dirty debe ser correcto para *todos* los caminos que lo consultan
  (cerrar, «Nuevo», «Abrir»), no solo el cierre; y `textEdited` —a diferencia de `textChanged`—
  no se dispara con el `setText` de `mostrar()`, evitando un dirty falso al poblar el campo.
  Test de regresión `test_editar_el_nombre_sin_perder_foco_marca_dirty` (falla con el código
  viejo, pasa con el fix). Único campo editable en OZ-8: el Nombre; no hay otros. Fix en rama
  aparte (no reabre el PR ya mergeado).

### Escenarios observados (a vigilar, sin acción ahora)

- **Guardado en OneDrive**: el proyecto de prueba se guardó en
  `C:\Users\...\OneDrive\Documentos\` (el default de Documentos en Windows, común en usuarios).
  El modelo documento (escritura atómica temporal + `os.replace`) **no dio problemas**. Se anota
  porque OneDrive sincronizando durante un guardado es el tipo de interacción que reaparece como
  bug raro más adelante.

### Deuda de producto detectada en la validación

- **i18n**: los botones de `QMessageBox` salen en inglés («Save/Discard/Cancel») porque son
  `StandardButtons` de Qt y no se cargan los catálogos de traducción. Decisión del PO: **i18n real
  es/en**, no parchear con texto hardcodeado. Tarjeta + **ADR-013** aparte, marcada `[HW]` (los
  `.qm` en frozen son el mismo riesgo que `importlib.resources`). Interino: los botones quedan en
  inglés en OZ-8, feo y consciente.

## Validación [HW] pendiente

Revalidar en la VM build 26200 el **flujo de dirty** con el MSI que incluya el fix (editar sin
perder foco → cerrar → aparece el diálogo; y por «Nuevo»/«Abrir»). Recién ahí OZ-8 → Done.

## Próxima sesión sugerida

**F1.5 · Cargar plano (PNG/JPG) + calibración**, donde entra el almacén de assets del
contenedor (hoy `assets={}`) y la herramienta de calibración del brief §5.3.

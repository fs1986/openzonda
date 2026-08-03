# S030 · OZ-34 · Mover el I/O de proyecto a un worker con cancelación

Fecha: 2026-08-03 · Fase: F1 (deuda) · Rama: `feature/oz-34-worker-io`

Deuda registrada en OZ-8 (S008): el I/O de abrir/guardar corría en el hilo de Qt. Se paga
ahora, antes de F1.5a, porque el plano embebido convierte el guardado en un payload grande
que congelaría la UI. Tarjeta **CI-verificable** (no `[HW]`); se valida de rebote en la tanda
`0.1.0-alpha.1` (guardar un proyecto con plano sin que la ventana se congele).

## Qué se hizo

- **Port `TaskExecutor`** (`application/task_executor.py`): «ejecutá este trabajo y avisame».
  - `SyncTaskExecutor` — inline; default y usado en tests (comportamiento previo a OZ-34).
  - `QtTaskExecutor` (`apps/desktop/qt_executor.py`) — corre el trabajo en el `QThreadPool` y
    **marshaliza** el resultado al hilo de la UI vía señales de Qt.
- **`ProjectService`**: `open` y `save` (el I/O pesado) pasan por el executor. `new`, `close`
  y `rename` quedan síncronos (son rápidos). Nuevo estado **`busy`** en `ProjectState`.
- **Shell**: durante `busy` se deshabilitan las acciones (Nuevo/Abrir/Guardar) y la barra de
  estado muestra «Trabajando…».
- **Cableado**: el composition root inyecta `QtTaskExecutor` en el servicio.

## Decisión: cancelación *lógica*, no abortar el I/O

El DoD pedía «cancelación cooperativa (§7.2)». Se implementó como **cancelación lógica por
generación**: cada op async lleva una generación; si el usuario cierra o cambia de proyecto,
la generación avanza y el resultado que llega tarde se **descarta** (y se limpia el working
dir que hubiera abierto). *No* se aborta el I/O a mitad —eso obligaría a re-tocar el
contenedor endurecido de OZ-7 (superficie hostil) para chequear cancelación dentro del
read/write, riesgo que no justifica el alpha—. Con archivos que tardan < ~1 s, descartar el
resultado cubre el caso de uso (cerrar cancela que se aplique). Documentado en el docstring de
`project_service.py`; si hiciera falta abortar I/O real, es una sub-deuda separada.

## Bug encontrado y corregido en el camino

El `QObject` de señales del `QtTaskExecutor` se recolectaba antes de que Qt entregara la señal
encolada (solo lo referenciaba el `QRunnable`, que muere al terminar `run()`), y un evento
encolado hacia un `QObject` muerto se descarta **en silencio** → el callback nunca corría.
Corregido reteniéndolo en el executor hasta que el callback se ejecuta. Cubierto por
`test_qt_executor.py` (falla sin la retención).

## DoD contrastado

| Punto | Comando | Resultado |
| --- | --- | --- |
| `busy` y cancelación (executor diferido) | `pytest tests/unit/test_project_service.py` | **18 passed** (4 nuevos de worker) |
| Marshalling worker→UI | `pytest tests/integration/test_qt_executor.py` | **2 passed** |
| Suite completa | `pytest` | **265 passed** |

Gate: `ruff` · `format` · `mypy` núcleo · `lint-imports` (4 kept, 0 broken) · `pytest` 265 ·
`python -m openzonda --smoke` exit 0.

## Artefactos

| Archivo | Contenido |
| --- | --- |
| `packages/application/task_executor.py` | Port `TaskExecutor` + `SyncTaskExecutor` |
| `apps/desktop/qt_executor.py` | `QtTaskExecutor` (QThreadPool + marshalling) |
| `packages/application/project_service.py` | `open`/`save` async, `busy`, cancelación por generación |
| `apps/desktop/main_window.py` · `apps/openzonda/__main__.py` | UI «Trabajando…» + cableado |

## Próxima

**OZ-9 (F1.5a)** — árbol Site→Floor + carga de plano + almacén de assets content-addressed.

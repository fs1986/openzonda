"""Ejecución de trabajo de I/O fuera del hilo llamante (OZ-34).

El ciclo de vida del proyecto (`ProjectService`) no puede bloquear el hilo de Qt: abrir o
guardar un `.wifisurvey` con un plano embebido puede tardar más de 50 ms (CLAUDE.md). Este
port abstrae "ejecutá este trabajo y avisame cuando termine", para que el servicio no sepa
si corre inline (tests, sin UI) o en un worker de Qt (la app real).

- `SyncTaskExecutor`: ejecuta inline. Es el default —comportamiento previo a OZ-34— y el que
  usan los tests headless.
- El adaptador de Qt (`desktop`) corre el trabajo en un `QThreadPool` y entrega el resultado
  en el hilo de Qt.

**Cancelación:** el executor no cancela; el `ProjectService` descarta por *generación* el
resultado de una operación que quedó obsoleta (el usuario cerró o cambió de proyecto). Es
cancelación lógica, no abortar el I/O a mitad —eso obligaría a re-tocar el contenedor
endurecido de OZ-7 y no lo justifica el alpha—.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class TaskExecutor(Protocol):
    """Ejecuta `work()` y entrega el resultado por callback. La implementación decide en qué
    hilo corre `work` y en cuál se invocan los callbacks (el adaptador de Qt los marshaliza
    al hilo de la UI)."""

    def submit(
        self,
        work: Callable[[], object],
        on_done: Callable[[object], None],
        on_error: Callable[[Exception], None],
    ) -> None: ...


class SyncTaskExecutor:
    """Ejecuta el trabajo en el acto, en el hilo llamante. Default y usado en tests."""

    def submit(
        self,
        work: Callable[[], object],
        on_done: Callable[[object], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        try:
            resultado = work()
        except Exception as error:
            on_error(error)
        else:
            on_done(resultado)

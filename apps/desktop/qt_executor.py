"""Adaptador Qt del port `TaskExecutor` (OZ-34): corre el trabajo en un worker.

El trabajo pesado (`work`) corre en un hilo del `QThreadPool`; los callbacks (`on_done` /
`on_error`) se **marshalizan al hilo de la UI** vía señales de Qt: `_Signals` se crea en el
hilo de la UI, así que emitir desde el worker entrega los slots por conexión encolada en el
hilo de la UI. El `ProjectService` nunca toca widgets desde otro hilo.

Detalle de vida útil: el `QObject` de señales debe seguir vivo hasta que el evento encolado
se **entregue** en el hilo de la UI. Guardarlo solo en el `QRunnable` no basta —el runnable
se destruye al terminar `run()`, y un evento encolado hacia un `QObject` ya recolectado se
descarta silenciosamente—. Por eso el executor lo retiene en `_vivos` y lo suelta recién
cuando el callback ya corrió.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class _Job(QRunnable):
    def __init__(self, work: Callable[[], object], signals: _Signals) -> None:
        super().__init__()
        self._work = work
        self._signals = signals

    def run(self) -> None:
        try:
            resultado = self._work()
        except Exception as error:  # se reenvía tal cual al hilo de la UI
            self._signals.failed.emit(error)
        else:
            self._signals.done.emit(resultado)


class QtTaskExecutor:
    """Ejecuta el trabajo en el `QThreadPool` global y entrega el resultado en el hilo de la UI."""

    def __init__(self, pool: QThreadPool | None = None) -> None:
        self._pool = pool or QThreadPool.globalInstance()
        self._vivos: set[_Signals] = set()

    def submit(
        self,
        work: Callable[[], object],
        on_done: Callable[[object], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        signals = _Signals()  # creado en el hilo de la UI → los slots se entregan ahí
        self._vivos.add(signals)

        def soltar(*_: object) -> None:
            self._vivos.discard(signals)

        signals.done.connect(on_done)
        signals.failed.connect(on_error)
        # Conectado después de los callbacks: cuando corre, on_done/on_error ya se ejecutaron
        # en este mismo hilo, así que soltar la referencia es seguro.
        signals.done.connect(soltar)
        signals.failed.connect(soltar)
        self._pool.start(_Job(work, signals))

"""Adaptador Qt del `TaskExecutor` (OZ-34): el trabajo corre en el pool y el resultado
llega en el hilo de la UI. Se procesa el event loop a mano para no depender de `exec()`."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6", reason="la UI es un extra opcional (extra 'ui')")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from desktop.qt_executor import QtTaskExecutor


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    yield app  # type: ignore[misc]


def _drenar() -> None:
    """Espera a que el worker termine y entrega las señales encoladas en el hilo de la UI."""
    QThreadPool.globalInstance().waitForDone(3000)
    QApplication.processEvents()


def test_entrega_el_resultado(qt_app: QApplication) -> None:
    salida: list[object] = []
    QtTaskExecutor().submit(lambda: 21 * 2, salida.append, lambda e: salida.append(("err", e)))

    _drenar()

    assert salida == [42]


def test_entrega_el_error(qt_app: QApplication) -> None:
    salida: list[object] = []

    def revienta() -> object:
        raise ValueError("falló el trabajo")

    QtTaskExecutor().submit(revienta, lambda r: salida.append(("ok", r)), salida.append)

    _drenar()

    assert len(salida) == 1
    assert isinstance(salida[0], ValueError)

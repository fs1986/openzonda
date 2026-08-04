"""Lógica pura del visor del plano (OZ-36), sin Qt: fit-to-view y disciplina de memoria.

El encuadre (zoom/pan/fit) es **solo viewport**, no se persiste; solo `rotation_degrees` vive
en el modelo. Aquí está la parte de esa lógica que no necesita `QGraphicsView`: el factor de
encuadre inicial y el guardián que garantiza que **solo el plano de la planta activa vive en
memoria** —un plano a resolución completa pesa ~192 MB (medición de OZ-9a), así que cambiar
de planta debe liberar el anterior, no acumular—.
"""

from __future__ import annotations

from collections.abc import Callable


def fit_scale(img_w: int, img_h: int, vp_w: int, vp_h: int) -> float:
    """Factor para encuadrar una imagen `img_w x img_h` en un viewport `vp_w x vp_h`.

    Manda el lado limitante (el menor de los dos cocientes). No amplía más allá de 1: fit
    encuadra un plano grande, pero no interpola uno chico a pantalla completa (eso lo decide
    el usuario con el zoom). Dimensiones inválidas -> 1.0 (neutro), nunca una división por
    cero silenciosa."""
    if img_w <= 0 or img_h <= 0 or vp_w <= 0 or vp_h <= 0:
        return 1.0
    return min(vp_w / img_w, vp_h / img_h, 1.0)


class ActivePlan[T]:
    """Guardián del único plano vivo: el de la planta activa.

    Al cambiar de planta libera el recurso anterior antes de cargar el nuevo, así la memoria
    no crece con cada cambio. `set(None)` o `clear()` liberan y dejan vacío. Cargar el mismo
    `sha` dos veces no recarga: es la misma planta."""

    def __init__(self, load: Callable[[str], T], release: Callable[[T], None]) -> None:
        self._load = load
        self._release = release
        self._sha: str | None = None
        self._resource: T | None = None

    @property
    def sha(self) -> str | None:
        return self._sha

    @property
    def resource(self) -> T | None:
        return self._resource

    def set(self, sha: str | None) -> None:
        if sha == self._sha:
            return
        self._liberar_actual()
        if sha is not None:
            self._resource = self._load(sha)
            self._sha = sha

    def clear(self) -> None:
        self._liberar_actual()

    def _liberar_actual(self) -> None:
        if self._resource is not None:
            self._release(self._resource)
        self._resource = None
        self._sha = None

"""Contrato del ViewModel del visor (OZ-36), verificado headless (sin Qt).

Dos piezas puras: (1) el factor **fit-to-view** que encuadra el plano en el viewport, y (2)
la **disciplina de memoria** — solo el plano de la planta activa vive; cambiar de planta
libera el anterior (un plano a resolución completa pesa ~192 MB, medición de OZ-9a). El
mapeo pantalla→imagen invariante al zoom lo verifica el test offscreen del widget; acá va la
lógica que no necesita `QGraphicsView`.
"""

from __future__ import annotations

from desktop.visor_viewmodel import ActivePlan, fit_scale

# ---------------------------------------------------------------- fit-to-view


def test_fit_scale_encuadra_por_el_lado_limitante() -> None:
    # Imagen 1000x500 en un viewport 400x400: el ancho manda -> 400/1000 = 0.4.
    assert fit_scale(1000, 500, 400, 400) == 0.4
    # Imagen 500x1000 en 400x400: la altura manda -> 400/1000 = 0.4.
    assert fit_scale(500, 1000, 400, 400) == 0.4


def test_fit_scale_no_amplia_mas_alla_de_1_por_defecto() -> None:
    # Un plano más chico que el viewport no se agranda: fit encuadra, no interpola de más.
    assert fit_scale(100, 100, 800, 800) == 1.0


def test_fit_scale_dimensiones_invalidas_es_neutro() -> None:
    assert fit_scale(0, 100, 400, 400) == 1.0
    assert fit_scale(100, 100, 0, 400) == 1.0


# ---------------------------------------------------------------- memoria


class _CargaContada:
    """Cargador falso que cuenta cuántos planos carga y cuáles se liberaron."""

    def __init__(self) -> None:
        self.cargados: list[str] = []
        self.liberados: list[str] = []

    def cargar(self, sha: str) -> str:
        self.cargados.append(sha)
        return f"pixmap:{sha}"  # el recurso; en la app real es un QPixmap

    def liberar(self, recurso: str) -> None:
        self.liberados.append(recurso)


def test_active_plan_carga_una_sola_vez_por_sha() -> None:
    loader = _CargaContada()
    activo = ActivePlan(loader.cargar, loader.liberar)

    activo.set("aaa")
    activo.set("aaa")  # misma planta -> no recarga

    assert loader.cargados == ["aaa"]
    assert activo.resource == "pixmap:aaa"


def test_active_plan_libera_el_anterior_al_cambiar_de_planta() -> None:
    loader = _CargaContada()
    activo = ActivePlan(loader.cargar, loader.liberar)

    activo.set("aaa")
    activo.set("bbb")  # cambia de planta: el plano viejo debe liberarse

    assert loader.cargados == ["aaa", "bbb"]
    assert loader.liberados == ["pixmap:aaa"], "el plano anterior no se liberó"
    assert activo.resource == "pixmap:bbb"


def test_active_plan_clear_libera_y_deja_vacio() -> None:
    loader = _CargaContada()
    activo = ActivePlan(loader.cargar, loader.liberar)
    activo.set("aaa")

    activo.clear()

    assert loader.liberados == ["pixmap:aaa"]
    assert activo.resource is None
    assert activo.sha is None


def test_active_plan_none_limpia() -> None:
    loader = _CargaContada()
    activo = ActivePlan(loader.cargar, loader.liberar)
    activo.set("aaa")

    activo.set(None)  # sin planta seleccionada

    assert loader.liberados == ["pixmap:aaa"]
    assert activo.resource is None

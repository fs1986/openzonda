"""Contrato del ViewModel del árbol y del resumen del plano (OZ-9a), verificado headless.

Dos cosas importan aquí: (1) la honestidad del resumen del plano —el DPI siempre viaja con su
procedencia en texto, un asumido no se muestra como medido (ADR-006)— y (2) que los comandos
del árbol se traduzcan en las ediciones correctas del servicio, resolviendo las entradas del
usuario por callback. No se instancia ningún widget.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from desktop.floorplan_viewmodel import (
    FloorPlanViewModel,
    NewFloor,
    dpi_summary,
    plan_summary,
    provenance_label,
)
from domain.calibration import Calibration
from domain.measurement import Measured, Provenance
from domain.project import FloorPlan
from domain.units import Meters

# --------------------------------------------------------------- honestidad del resumen


def test_dpi_observado_se_muestra_como_del_archivo() -> None:
    dpi = Measured(300.0, Provenance.OBSERVED)
    assert dpi_summary(dpi) == "300 dpi · del archivo"


def test_dpi_estimado_se_marca_como_asumido_por_defecto() -> None:
    dpi = Measured(96.0, Provenance.ESTIMATED)
    resumen = dpi_summary(dpi)
    assert "asumido" in resumen and "por defecto" in resumen
    assert "del archivo" not in resumen  # jamás presentar un asumido como medido


def test_provenance_label_cubre_todas_las_procedencias() -> None:
    for prov in Provenance:
        assert provenance_label(prov)  # no vacío, sin KeyError


def test_plan_summary_incluye_dimensiones_dpi_y_calibracion() -> None:
    plan = FloorPlan(
        asset_sha256="a" * 64,
        width_px=1200,
        height_px=800,
        dpi=Measured(96.0, Provenance.ESTIMATED),
    )
    resumen = plan_summary(plan)
    assert "1200 x 800 px" in resumen
    assert "96 dpi" in resumen and "asumido" in resumen
    assert "sin calibrar" in resumen


def test_plan_summary_marca_calibrado() -> None:
    plan = FloorPlan(
        asset_sha256="a" * 64,
        width_px=1200,
        height_px=800,
        dpi=Measured(96.0, Provenance.OBSERVED),
        calibration=Calibration(
            meters_per_pixel=0.01,
            pixel_distance=100.0,
            real_distance=Meters(1.0),
            click_uncertainty_px=2.0,
        ),
    )
    assert "calibrado" in plan_summary(plan)
    assert "sin calibrar" not in plan_summary(plan)


# ------------------------------------------------------------------- comandos del árbol


class FakeService:
    """Servicio espía: registra las ediciones que el ViewModel le pide."""

    def __init__(self) -> None:
        self.calls: list[object] = []

    def add_site(self, name: str) -> None:
        self.calls.append(("add_site", name))

    def rename_site(self, site_id: object, name: str) -> None:
        self.calls.append(("rename_site", site_id, name))

    def remove_site(self, site_id: object) -> None:
        self.calls.append(("remove_site", site_id))

    def add_floor(self, site_id: object, name: str, level: int, source: object) -> None:
        self.calls.append(("add_floor", site_id, name, level, source))

    def rename_floor(self, floor_id: object, name: str) -> None:
        self.calls.append(("rename_floor", floor_id, name))

    def remove_floor(self, floor_id: object) -> None:
        self.calls.append(("remove_floor", floor_id))

    def set_floor_plan(self, floor_id: object, source: object) -> None:
        self.calls.append(("set_floor_plan", floor_id, source))


def _vm(service: FakeService, **overrides) -> FloorPlanViewModel:
    defaults = dict(
        ask_site_name=lambda: "Sede",
        ask_new_floor=lambda: NewFloor("Baja", 0, Path("plano.png")),
        ask_rename=lambda actual: f"{actual} editado",
        ask_image_path=lambda: Path("nuevo.png"),
        confirm_remove=lambda desc: True,
    )
    defaults.update(overrides)
    return FloorPlanViewModel(service, **defaults)  # type: ignore[arg-type]


def test_add_site_usa_el_nombre_pedido() -> None:
    service = FakeService()
    _vm(service).request_add_site()
    assert service.calls == [("add_site", "Sede")]


def test_add_site_cancelado_no_hace_nada() -> None:
    service = FakeService()
    _vm(service, ask_site_name=lambda: None).request_add_site()
    assert service.calls == []


def test_add_floor_pasa_nombre_nivel_e_imagen() -> None:
    service = FakeService()
    sid = uuid4()
    _vm(service).request_add_floor(sid)
    assert service.calls == [("add_floor", sid, "Baja", 0, Path("plano.png"))]


def test_add_floor_cancelado_no_hace_nada() -> None:
    service = FakeService()
    _vm(service, ask_new_floor=lambda: None).request_add_floor(uuid4())
    assert service.calls == []


def test_remove_site_confirmado_y_cancelado() -> None:
    sid = uuid4()
    service = FakeService()
    _vm(service).request_remove_site(sid, "Sede (2 plantas)")
    assert service.calls == [("remove_site", sid)]

    service2 = FakeService()
    _vm(service2, confirm_remove=lambda desc: False).request_remove_site(sid, "x")
    assert service2.calls == []


def test_load_plan_reemplaza_con_la_imagen_elegida() -> None:
    service = FakeService()
    fid = uuid4()
    _vm(service).request_load_plan(fid)
    assert service.calls == [("set_floor_plan", fid, Path("nuevo.png"))]

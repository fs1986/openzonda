"""ViewModel del árbol Site→Floor y del resumen del plano (OZ-9a).

Se prueba **headless**, sin `QApplication`: las interacciones de la vista —pedir un nombre,
elegir una imagen, confirmar un borrado— se inyectan como callbacks, igual que en la shell
(`shell_viewmodel`). Usa `QCoreApplication.translate` para los textos de usuario (OZ-35), que
sin traductor instalado devuelve el español de origen, así los tests siguen corriendo sin app.
La vista (`main_window`) provee los callbacks reales (`QInputDialog`, `QFileDialog`,
`QMessageBox`) y repinta el árbol al recibir un `ProjectState` nuevo.

**Honestidad del DPI en la presentación (ADR-006):** el resumen del plano no muestra el DPI
como un número pelado. Siempre lo acompaña de su procedencia en *texto* —"del archivo" vs.
"asumido"—, nunca solo por color: quien lee el resumen sabe si el dato se midió o se supuso.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from PySide6.QtCore import QCoreApplication

from application.project_service import ProjectService
from domain.measurement import Measured, Provenance
from domain.project import FloorPlan


def provenance_label(provenance: Provenance) -> str:
    """Etiqueta de texto de una procedencia. Canal no-cromático de la honestidad (ADR-006)."""
    # El contexto de translate() debe ser un literal para que lupdate lo extraiga.
    return {
        Provenance.OBSERVED: QCoreApplication.translate("floorplan", "del archivo"),
        Provenance.DERIVED: QCoreApplication.translate("floorplan", "derivado"),
        Provenance.ESTIMATED: QCoreApplication.translate("floorplan", "asumido"),
        Provenance.PREDICTED: QCoreApplication.translate("floorplan", "predicho"),
    }[provenance]


def dpi_summary(dpi: Measured[float]) -> str:
    """DPI con su procedencia en texto. Un DPI asumido nunca se muestra como si fuera medido."""
    etiqueta = provenance_label(dpi.provenance)
    if dpi.provenance is Provenance.ESTIMATED:
        por_defecto = QCoreApplication.translate("floorplan", "por defecto")
        etiqueta = f"{etiqueta} ({por_defecto})"
    return f"{dpi.value:.0f} dpi · {etiqueta}"


def plan_summary(plan: FloorPlan) -> str:
    """Resumen textual del plano: dimensiones + DPI con procedencia. Es lo que hace validable
    la honestidad del plano en OZ-9a sin depender del visor (OZ-36)."""
    partes = [f"{plan.width_px} x {plan.height_px} px", dpi_summary(plan.dpi)]
    if plan.rotation_degrees:
        rotacion = QCoreApplication.translate("floorplan", "rotación")
        partes.append(f"{rotacion} {plan.rotation_degrees:g}°")
    if plan.is_calibrated:
        partes.append(QCoreApplication.translate("floorplan", "calibrado"))
    else:
        partes.append(QCoreApplication.translate("floorplan", "sin calibrar"))
    return " · ".join(partes)


def calibration_summary(plan: FloorPlan) -> str:
    """Escala del plano y su incertidumbre, **siempre** ambas (OZ-36).

    La incertidumbre no se muestra solo cuando es alta: un factor de escala sin su error
    aparenta más exactitud de la que tiene (ADR-006). Una planta sin calibrar lo dice —no un
    0 falso—; la escala procede de dos clics humanos, y ese margen viaja con ella. Es texto,
    doble canal de accesibilidad."""
    cal = plan.calibration
    if cal is None:
        return QCoreApplication.translate(
            "floorplan", "Sin calibrar — las distancias del plano no tienen escala todavía."
        )
    plantilla = QCoreApplication.translate(
        "floorplan", "Escala: 1 px = {mpp} m · incertidumbre ±{rel}% (calibrado sobre {dist})"
    )
    return plantilla.format(
        mpp=f"{cal.meters_per_pixel:.4g}",
        rel=f"{cal.relative_error * 100:.1f}",
        dist=cal.real_distance,
    )


@dataclass(frozen=True, slots=True)
class NewFloor:
    """Datos que la vista recoge para crear una planta: nombre, nivel y la imagen del plano."""

    name: str
    level: int
    image: object  # pathlib.Path, tipado laxo para no acoplar el ViewModel a la vista


class FloorPlanViewModel:
    """Traduce las acciones del árbol en ediciones del `ProjectService`. Sin estado propio de
    presentación más allá de los callbacks: el árbol se pinta desde `ProjectState.project`."""

    def __init__(
        self,
        service: ProjectService,
        *,
        ask_site_name: Callable[[], str | None],
        ask_new_floor: Callable[[], NewFloor | None],
        ask_rename: Callable[[str], str | None],
        ask_image_path: Callable[[], object | None],
        confirm_remove: Callable[[str], bool],
    ) -> None:
        self._service = service
        self._ask_site_name = ask_site_name
        self._ask_new_floor = ask_new_floor
        self._ask_rename = ask_rename
        self._ask_image_path = ask_image_path
        self._confirm_remove = confirm_remove

    # -------------------------------------------------------------------- sitios

    def request_add_site(self) -> None:
        nombre = self._ask_site_name()
        if nombre and nombre.strip():
            self._service.add_site(nombre.strip())

    def request_rename_site(self, site_id: UUID, current: str) -> None:
        nombre = self._ask_rename(current)
        if nombre and nombre.strip():
            self._service.rename_site(site_id, nombre.strip())

    def request_remove_site(self, site_id: UUID, description: str) -> None:
        if self._confirm_remove(description):
            self._service.remove_site(site_id)

    # -------------------------------------------------------------------- plantas

    def request_add_floor(self, site_id: UUID) -> None:
        datos = self._ask_new_floor()
        if datos is not None:
            self._service.add_floor(site_id, datos.name, datos.level, datos.image)  # type: ignore[arg-type]

    def request_rename_floor(self, floor_id: UUID, current: str) -> None:
        nombre = self._ask_rename(current)
        if nombre and nombre.strip():
            self._service.rename_floor(floor_id, nombre.strip())

    def request_remove_floor(self, floor_id: UUID, description: str) -> None:
        if self._confirm_remove(description):
            self._service.remove_floor(floor_id)

    def request_load_plan(self, floor_id: UUID) -> None:
        """Carga (reemplaza) el plano de una planta existente."""
        ruta = self._ask_image_path()
        if ruta is not None:
            self._service.set_floor_plan(floor_id, ruta)  # type: ignore[arg-type]

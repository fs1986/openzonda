"""Adaptador SQLite del port `ProjectRepository` (plan F1.2).

`save` **reemplaza** el estado completo del proyecto en lugar de acumular. Es la semántica
que corresponde a un agregado inmutable: el objeto en memoria es la verdad, y quitarle un
sitio debe eliminarlo también del archivo. Acumular produciría el fallo más difícil de
diagnosticar de un repositorio — datos que reaparecen tras haberlos borrado.

El reemplazo se apoya en `ON DELETE CASCADE` y ocurre dentro de una transacción, así que un
fallo a mitad deja el proyecto anterior intacto.
"""

from __future__ import annotations

import sqlite3
from uuid import UUID, uuid4

from domain.calibration import Calibration
from domain.measurement import Measured, Provenance
from domain.project import Floor, FloorPlan, Project, Site
from domain.units import Meters


class SQLiteProjectRepository:
    """Persiste proyectos en una conexión ya abierta y migrada."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------ escritura

    def save(self, project: Project) -> None:
        try:
            self._conn.execute("BEGIN")
            # Borrar primero deja que la cascada limpie sitios, plantas y planos.
            # Es más simple y más seguro que reconciliar diferencias: no hay estado
            # intermedio en el que el proyecto sea una mezcla de dos versiones.
            self._conn.execute("DELETE FROM project WHERE id = ?", (str(project.id),))
            self._conn.execute(
                "INSERT INTO project (id, name, schema_version) VALUES (?, ?, ?)",
                (str(project.id), project.name, project.schema_version),
            )
            for orden, site in enumerate(project.sites):
                self._guardar_sitio(site, project.id, orden)
            self._conn.execute("COMMIT")
        except sqlite3.Error:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise

    def _guardar_sitio(self, site: Site, project_id: UUID, orden: int) -> None:
        self._conn.execute(
            "INSERT INTO site (id, project_id, name, position) VALUES (?, ?, ?, ?)",
            (str(site.id), str(project_id), site.name, orden),
        )
        for posicion, floor in enumerate(site.floors):
            plan_id = self._guardar_plano(floor.plan)
            self._conn.execute(
                "INSERT INTO floor (id, site_id, plan_id, name, level, height_m, position) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(floor.id),
                    str(site.id),
                    plan_id,
                    floor.name,
                    floor.level,
                    floor.height.value if floor.height is not None else None,
                    posicion,
                ),
            )

    def _guardar_plano(self, plan: FloorPlan) -> str:
        # El plano no tiene identidad propia en el dominio: se le asigna una técnica para
        # poder referenciarlo desde `floor`. Un mismo asset puede aparecer en dos plantas
        # y son filas distintas, porque su calibración es independiente.
        plan_id = str(uuid4())
        cal = plan.calibration
        self._conn.execute(
            "INSERT INTO floor_plan (id, asset_sha256, width_px, height_px, dpi, "
            "dpi_provenance, rotation_degrees, cal_meters_per_pixel, cal_pixel_distance, "
            "cal_real_distance_m, cal_click_uncertainty) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                plan_id,
                plan.asset_sha256,
                plan.width_px,
                plan.height_px,
                plan.dpi.value,
                plan.dpi.provenance.value,
                plan.rotation_degrees,
                cal.meters_per_pixel if cal else None,
                cal.pixel_distance if cal else None,
                cal.real_distance.value if cal else None,
                cal.click_uncertainty_px if cal else None,
            ),
        )
        return plan_id

    # ------------------------------------------------------------------- lectura

    def load(self, project_id: UUID) -> Project | None:
        fila = self._conn.execute(
            "SELECT id, name, schema_version FROM project WHERE id = ?",
            (str(project_id),),
        ).fetchone()
        if fila is None:
            return None

        return Project(
            id=UUID(fila[0]),
            name=fila[1],
            schema_version=fila[2],
            sites=self._cargar_sitios(fila[0]),
        )

    def _cargar_sitios(self, project_id: str) -> tuple[Site, ...]:
        filas = self._conn.execute(
            "SELECT id, name FROM site WHERE project_id = ? ORDER BY position",
            (project_id,),
        ).fetchall()
        return tuple(
            Site(id=UUID(sid), name=nombre, floors=self._cargar_plantas(sid))
            for sid, nombre in filas
        )

    def _cargar_plantas(self, site_id: str) -> tuple[Floor, ...]:
        filas = self._conn.execute(
            "SELECT f.id, f.name, f.level, f.height_m, "
            "       p.asset_sha256, p.width_px, p.height_px, p.dpi, p.rotation_degrees, "
            "       p.cal_meters_per_pixel, p.cal_pixel_distance, "
            "       p.cal_real_distance_m, p.cal_click_uncertainty, p.dpi_provenance "
            "FROM floor f JOIN floor_plan p ON p.id = f.plan_id "
            "WHERE f.site_id = ? ORDER BY f.position",
            (site_id,),
        ).fetchall()

        return tuple(
            Floor(
                id=UUID(fila[0]),
                name=fila[1],
                level=fila[2],
                height=Meters(fila[3]) if fila[3] is not None else None,
                plan=FloorPlan(
                    asset_sha256=fila[4],
                    width_px=fila[5],
                    height_px=fila[6],
                    dpi=Measured(fila[7], Provenance(fila[13])),
                    rotation_degrees=fila[8],
                    calibration=_calibracion_desde_fila(fila[9:13]),
                ),
            )
            for fila in filas
        )

    def list_ids(self) -> tuple[UUID, ...]:
        filas = self._conn.execute("SELECT id FROM project").fetchall()
        return tuple(UUID(f[0]) for f in filas)


def _calibracion_desde_fila(
    valores: tuple[float | None, float | None, float | None, float | None],
) -> Calibration | None:
    """`NULL` significa «plano sin calibrar», que no es lo mismo que una escala de cero.

    El `CHECK` del esquema garantiza que las cuatro columnas están o todas presentes o
    todas ausentes, así que basta con mirar la primera.
    """
    metros_por_pixel, distancia_px, distancia_real, incertidumbre = valores
    if metros_por_pixel is None:
        return None
    assert distancia_px is not None and distancia_real is not None
    assert incertidumbre is not None
    return Calibration(
        meters_per_pixel=metros_por_pixel,
        pixel_distance=distancia_px,
        real_distance=Meters(distancia_real),
        click_uncertainty_px=incertidumbre,
    )

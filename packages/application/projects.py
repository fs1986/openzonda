"""Port de persistencia de proyectos.

Vive en `application` porque el *contrato* pertenece al caso de uso: la UI necesita saber
que existe algo capaz de guardar y recuperar un proyecto, pero no que detrás hay SQLite
(ADR-003, ADR-008).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.project import Project


class ProjectRepository(Protocol):
    """Guarda y recupera proyectos completos.

    `save` reemplaza el estado completo del proyecto, no acumula: quitar un sitio del
    agregado y guardar debe eliminarlo también del almacenamiento. Es la semántica que
    corresponde a un agregado inmutable — el objeto en memoria es la verdad.
    """

    def save(self, project: Project) -> None:
        """Persiste el proyecto entero, reemplazando la versión anterior si existe."""
        ...

    def load(self, project_id: UUID) -> Project | None:
        """Recupera el proyecto, o `None` si no existe."""
        ...

    def list_ids(self) -> tuple[UUID, ...]:
        """Identificadores de los proyectos almacenados."""
        ...

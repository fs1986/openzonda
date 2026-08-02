"""Honestidad metrológica — clasificación de la procedencia de todo dato.

Este módulo materializa el invariante de producto descrito en el diseño §25 y
ADR-006: la distinción entre dato **observado / derivado / estimado / predictivo**
vive en el modelo de datos, no solo en la UI. Degradar esta clasificación en
silencio está prohibido.

Cualquier magnitud que la aplicación muestre, exporte o coloree en un heatmap
debe viajar acompañada de su :class:`Provenance`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")


class Provenance(Enum):
    """Origen epistémico de un valor. El orden refleja confianza decreciente."""

    OBSERVED = "observed"
    """Medido directamente por la NIC (p. ej. RSSI en dBm de un BSS)."""

    DERIVED = "derived"
    """Calculado de forma determinista a partir de observaciones (p. ej. SNR
    cuando el driver expone noise, o cobertura por umbral)."""

    ESTIMATED = "estimated"
    """Inferido mediante heurística declarada (p. ej. capacidad vía BSS Load).
    Nunca debe presentarse como observado."""

    PREDICTED = "predicted"
    """Producido por el motor RF sobre un plano, sin medición en ese punto."""


@dataclass(frozen=True, slots=True)
class Measured(Generic[T]):
    """Un valor acompañado, de forma inseparable, de su procedencia.

    Al ser ``frozen`` no se puede mutar la procedencia tras la construcción:
    la única forma de "cambiarla" es derivar explícitamente un nuevo valor, lo
    que deja la degradación visible en el código y en los tests.
    """

    value: T
    provenance: Provenance

    def is_observed(self) -> bool:
        return self.provenance is Provenance.OBSERVED

    def downgraded_to(self, provenance: Provenance) -> "Measured[T]":
        """Devuelve una copia con procedencia de **menor** confianza.

        Degradar (p. ej. de OBSERVED a ESTIMATED) es legítimo cuando se
        interpola o modela; hacerlo al revés no lo es y se rechaza aquí.
        """
        order = list(Provenance)
        if order.index(provenance) < order.index(self.provenance):
            raise ValueError(
                f"No se puede 'mejorar' la procedencia de {self.provenance.value} "
                f"a {provenance.value}: violaría la honestidad metrológica (ADR-006)."
            )
        return Measured(self.value, provenance)

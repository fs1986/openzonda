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

CONFIDENCE_ORDER: tuple[Provenance, ...]
"""Procedencias de mayor a menor confianza. Se define tras el enum."""


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
class Measured[T]:
    """Un valor acompañado, de forma inseparable, de su procedencia.

    Al ser ``frozen`` no se puede mutar la procedencia tras la construcción:
    la única forma de "cambiarla" es derivar explícitamente un nuevo valor, lo
    que deja la degradación visible en el código y en los tests.
    """

    value: T
    provenance: Provenance

    def is_observed(self) -> bool:
        return self.provenance is Provenance.OBSERVED

    def downgraded_to(self, provenance: Provenance) -> Measured[T]:
        """Devuelve una copia con procedencia de **menor** confianza.

        Degradar (p. ej. de OBSERVED a ESTIMATED) es legítimo cuando se
        interpola o modela; hacerlo al revés no lo es y se rechaza aquí.
        """
        if CONFIDENCE_ORDER.index(provenance) < CONFIDENCE_ORDER.index(self.provenance):
            raise ValueError(
                f"No se puede 'mejorar' la procedencia de {self.provenance.value} "
                f"a {provenance.value}: violaría la honestidad metrológica (ADR-006)."
            )
        return Measured(self.value, provenance)


CONFIDENCE_ORDER = tuple(Provenance)


def weakest(*provenances: Provenance) -> Provenance:
    """Devuelve la procedencia de **menor** confianza de las recibidas.

    Es la regla que gobierna cualquier cálculo: un valor derivado no puede ser más fiable
    que su entrada menos fiable. Derivar a partir de una estimación produce una
    estimación, no un dato derivado.
    """
    if not provenances:
        raise ValueError("weakest() necesita al menos una procedencia.")
    return max(provenances, key=CONFIDENCE_ORDER.index)


class UnavailableReason(Enum):
    """Por qué no hay dato. El motivo es parte del dato ausente."""

    NOISE_FLOOR_NOT_REPORTED = "noise_floor_not_reported"
    """El driver no expone el noise floor. Es el caso normal en Windows (diseño §5),
    y la razón por la que el SNR suele ser «no disponible»."""

    NOT_SUPPORTED_BY_DRIVER = "not_supported_by_driver"
    """El adaptador o su driver no exponen esta magnitud."""

    NOT_MEASURED = "not_measured"
    """Todavía no se ha medido en este punto."""

    SCAN_FAILED = "scan_failed"
    """El escaneo falló o expiró; no hubo lectura que registrar."""

    OUT_OF_RANGE = "out_of_range"
    """El valor recibido es imposible físicamente y se descartó como lectura."""


@dataclass(frozen=True, slots=True)
class Unavailable:
    """Ausencia **explícita** de dato, con su motivo.

    Existe para que la alternativa —colar un ``0``, un ``-100`` o un ``None`` mudo— sea
    imposible. Un SNR de 0 dB es un valor legítimo y pésimo; «no lo sabemos» es otra cosa
    completamente distinta, y confundirlos es el fallo que ADR-006 existe para evitar.

    Deliberadamente **no** tiene atributo ``value``: cualquier código que intente leerlo
    falla en vez de obtener un número inventado.
    """

    reason: UnavailableReason

    def __str__(self) -> str:
        return f"no disponible ({self.reason.value})"


type Reading[T] = Measured[T] | Unavailable
"""Una lectura: o un valor con su procedencia, o una ausencia con su motivo.

Al ser una unión, el sistema de tipos obliga a distinguir ambos casos antes de usar el
valor. No hay forma de "olvidarse" del caso ausente."""

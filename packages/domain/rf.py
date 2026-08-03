"""Reglas de radiofrecuencia del dominio: rango físico y derivación de SNR.

Aquí vive la consecuencia más concreta de la honestidad metrológica. La restricción
física es del diseño §5: **la mayoría de drivers de Windows no reportan noise floor**.
Sin noise no hay SNR, y las dos salidas fáciles están prohibidas por la decisión
inmutable nº 3 de ``CLAUDE.md``:

1. Devolver ``0`` — indistinguible de un SNR real de 0 dB, que es un valor legítimo.
2. Estimar el noise floor y presentar el resultado como si se hubiera medido.

La única respuesta honesta es :class:`~domain.measurement.Unavailable`, con su motivo.
"""

from __future__ import annotations

from domain.measurement import (
    Measured,
    Provenance,
    Reading,
    Unavailable,
    UnavailableReason,
    weakest,
)
from domain.units import Db, Dbm

RSSI_PHYSICAL_RANGE_DBM = (-100.0, -10.0)
"""Rango físicamente plausible de un RSSI de WiFi (diseño §10.2).

Fuera de él la lectura es sospechosa: casi siempre indica un driver que reporta en otra
escala o un valor centinela. No se descarta la muestra —se marca— porque descartarla
perdería información sobre un adaptador que se comporta mal.
"""


def is_physically_plausible(rssi: Dbm) -> bool:
    """¿Cae este RSSI dentro del rango físico esperable? (diseño §10.2)"""
    minimo, maximo = RSSI_PHYSICAL_RANGE_DBM
    return minimo <= rssi.value <= maximo


def snr_from(rssi: Reading[Dbm], noise: Reading[Dbm]) -> Reading[Db]:
    """Deriva el SNR a partir del RSSI y el noise floor.

    Reglas, todas verificadas por tests:

    - Si **falta cualquiera** de las dos entradas, el resultado es
      :class:`~domain.measurement.Unavailable`. Nunca ``0``, nunca un valor estimado.
    - El resultado **jamás** es ``OBSERVED``: el SNR se calcula, no se mide. Con ambas
      entradas observadas, lo mejor que puede ser es ``DERIVED``.
    - Con alguna entrada de menor confianza, hereda la más débil: derivar de una
      estimación produce una estimación.
    """
    if isinstance(rssi, Unavailable):
        return rssi
    if isinstance(noise, Unavailable):
        return noise

    procedencia = weakest(Provenance.DERIVED, rssi.provenance, noise.provenance)
    return Measured(rssi.value - noise.value, procedencia)


def rssi_reading(rssi: Dbm, provenance: Provenance = Provenance.OBSERVED) -> Reading[Dbm]:
    """Construye una lectura de RSSI, marcándola ausente si es imposible.

    Un valor fuera de todo rango concebible no es una medición mala: no es una medición.
    """
    if not -200.0 <= rssi.value <= 100.0:
        return Unavailable(UnavailableReason.OUT_OF_RANGE)
    return Measured(rssi, provenance)

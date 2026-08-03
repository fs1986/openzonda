"""Value objects de unidades (plan F1.1).

No son tipado decorativo: hacen **imposible** una clase de error que en radiofrecuencia se
comete constantemente — confundir una potencia con una relación.

- **dBm** (:class:`Dbm`) es una potencia absoluta referida a 1 mW. Un RSSI de -65 dBm.
- **dB** (:class:`Db`) es una *relación*, sin referencia. Un SNR de 30 dB, la atenuación
  de 8 dB de un tabique, el offset de calibración de una NIC.

De ahí sale el álgebra que implementan estos tipos::

    dBm - dBm → dB      (relación entre dos niveles: eso es el SNR)
    dBm ± dB  → dBm     (atenuar o amplificar un nivel)
    dB  + dB  → dB      (atenuaciones acumuladas)
    dBm + dBm → TypeError  (no significa nada físicamente)

Lo mismo con :class:`Pixels` y :class:`Meters`: solo una
:class:`~domain.calibration.Calibration` puede convertir entre ellos, porque la conversión
depende de un plano concreto y de dónde hizo clic un humano.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Self, overload


def _validar_finito(valor: float, unidad: str) -> None:
    if not math.isfinite(valor):
        raise ValueError(f"Un valor en {unidad} debe ser finito, no {valor!r}.")


@dataclass(frozen=True, slots=True, order=True)
class Dbm:
    """Nivel de potencia absoluto, en dBm. Referido a 1 mW."""

    value: float

    def __post_init__(self) -> None:
        _validar_finito(self.value, "dBm")

    def __str__(self) -> str:
        return f"{self.value:.1f} dBm"

    # Las sobrecargas no son cosmética: sin ellas, el tipo de `rssi - noise` sería
    # `Dbm | Db` y quien lo consuma tendría que estrecharlo a mano. Con ellas, restar dos
    # niveles produce estáticamente un `Db`, que es lo que un SNR es.
    @overload
    def __sub__(self, other: Dbm) -> Db: ...

    @overload
    def __sub__(self, other: Db) -> Dbm: ...

    def __sub__(self, other: Dbm | Db) -> Dbm | Db:
        """``dBm - dBm`` da una relación; ``dBm - dB`` atenúa el nivel."""
        if isinstance(other, Dbm):
            return Db(self.value - other.value)
        return Dbm(self.value - other.value)

    def __add__(self, other: Db) -> Dbm:
        if isinstance(other, Dbm):
            raise TypeError(
                "Sumar dos valores en dBm no tiene significado físico: son potencias "
                "absolutas. Para relacionarlos, réstalos (da un valor en dB)."
            )
        return Dbm(self.value + other.value)


@dataclass(frozen=True, slots=True, order=True)
class Db:
    """Relación entre dos niveles, en dB. Puede ser negativa (señal bajo el ruido)."""

    value: float

    def __post_init__(self) -> None:
        _validar_finito(self.value, "dB")

    def __str__(self) -> str:
        return f"{self.value:.1f} dB"

    def __add__(self, other: Db) -> Db:
        if isinstance(other, Db):
            return Db(self.value + other.value)
        return NotImplemented

    def __sub__(self, other: Db) -> Db:
        if isinstance(other, Db):
            return Db(self.value - other.value)
        return NotImplemented

    def __neg__(self) -> Db:
        return Db(-self.value)


@dataclass(frozen=True, slots=True, order=True)
class Meters:
    """Distancia en el mundo real. No negativa."""

    value: float

    def __post_init__(self) -> None:
        _validar_finito(self.value, "m")
        if self.value < 0.0:
            raise ValueError(f"Una distancia no puede ser negativa: {self.value} m.")

    def __str__(self) -> str:
        return f"{self.value:.2f} m"

    def __add__(self, other: Self) -> Meters:
        if isinstance(other, Meters):
            return Meters(self.value + other.value)
        return NotImplemented


@dataclass(frozen=True, slots=True, order=True)
class Pixels:
    """Distancia o coordenada sobre la imagen del plano. No negativa."""

    value: float

    def __post_init__(self) -> None:
        _validar_finito(self.value, "px")
        if self.value < 0.0:
            raise ValueError(f"Una distancia no puede ser negativa: {self.value} px.")

    def __str__(self) -> str:
        return f"{self.value:.1f} px"

    def __add__(self, other: Self) -> Pixels:
        if isinstance(other, Pixels):
            return Pixels(self.value + other.value)
        return NotImplemented

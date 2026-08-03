"""Calibración píxel↔metro (plan F1.1, diseño §8.1).

El usuario marca dos puntos sobre el plano y declara la distancia real entre ellos. De ahí
sale la escala, y de la escala sale **todo** lo que el producto afirma sobre distancias:
área cubierta, separación entre APs, alcance de una celda.

Por eso la calibración almacena su error. Se deriva de dos clics humanos sobre una imagen,
y un clic tiene precisión finita. Un factor de escala sin incertidumbre declarada aparenta
más exactitud de la que tiene — exactamente lo que ADR-006 prohíbe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from domain.measurement import Measured, Provenance
from domain.units import Meters, Pixels

DEFAULT_CLICK_UNCERTAINTY_PX = 1.0
"""Incertidumbre asumida al marcar un punto, en píxeles.

Un clic sobre una imagen no cae en el píxel exacto que el usuario pretendía. Un píxel es
una estimación conservadora y honesta; el valor es configurable porque depende del zoom al
que se calibró.
"""


@dataclass(frozen=True, slots=True)
class Calibration:
    """Escala entre la imagen del plano y el mundo real, con su incertidumbre.

    Construir con :meth:`from_two_points`; el constructor directo no valida la coherencia
    entre escala y error.
    """

    meters_per_pixel: float
    pixel_distance: float
    real_distance: Meters
    click_uncertainty_px: float = DEFAULT_CLICK_UNCERTAINTY_PX

    @classmethod
    def from_two_points(
        cls,
        first: tuple[Pixels, Pixels],
        second: tuple[Pixels, Pixels],
        real_distance: Meters,
        click_uncertainty_px: float = DEFAULT_CLICK_UNCERTAINTY_PX,
    ) -> Calibration:
        """Deriva la escala de dos puntos del plano y la distancia real entre ellos."""
        if real_distance.value <= 0.0:
            raise ValueError(
                f"La distancia real debe ser mayor que cero, no {real_distance}. "
                "Sin ella no hay escala que derivar."
            )

        dx = second[0].value - first[0].value
        dy = second[1].value - first[1].value
        distancia_px = math.hypot(dx, dy)
        if distancia_px <= 0.0:
            raise ValueError(
                "Los dos puntos de calibración coinciden en el mismo punto del plano: "
                "no hay distancia en píxeles de la que derivar una escala."
            )

        return cls(
            meters_per_pixel=real_distance.value / distancia_px,
            pixel_distance=distancia_px,
            real_distance=real_distance,
            click_uncertainty_px=click_uncertainty_px,
        )

    @property
    def relative_error(self) -> float:
        """Error relativo de la escala, propagado desde la incertidumbre del clic.

        Calibrar sobre una distancia larga reduce el error: el mismo píxel de duda pesa
        menos cuanto mayor es la separación entre los puntos marcados. Es el consejo
        práctico que la UI debe dar, aquí cuantificado.
        """
        return self.click_uncertainty_px / self.pixel_distance

    def to_meters(self, pixels: Pixels) -> Meters:
        return Meters(pixels.value * self.meters_per_pixel)

    def to_pixels(self, meters: Meters) -> Pixels:
        return Pixels(meters.value / self.meters_per_pixel)

    def to_meters_measured(self, pixels: Pixels) -> Measured[Meters]:
        """Como :meth:`to_meters`, pero declarando la procedencia.

        Una distancia en metros sobre un plano **no es observada**: procede de una escala
        que a su vez procede de dos clics. Es derivada, y el modelo lo dice.
        """
        return Measured(self.to_meters(pixels), Provenance.DERIVED)

    def uncertainty_of(self, pixels: Pixels) -> Meters:
        """Margen de error absoluto de una distancia convertida."""
        return Meters(self.to_meters(pixels).value * self.relative_error)

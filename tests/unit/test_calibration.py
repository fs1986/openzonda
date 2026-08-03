"""Calibración píxel↔metro (plan F1.1, diseño §8.1).

El usuario marca dos puntos sobre el plano y declara la distancia real entre ellos. De ahí
sale la escala. Todo lo que el producto dice sobre distancias —área cubierta, separación
entre APs, alcance— depende de este número.

Por eso la calibración **almacena su error**: se deriva de dos clics humanos sobre una
imagen, y un clic tiene una precisión finita. Un factor de escala sin incertidumbre
declarada es una cifra que aparenta más exactitud de la que tiene, que es justo lo que
ADR-006 prohíbe.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from domain.calibration import Calibration
from domain.measurement import Provenance
from domain.units import Meters, Pixels


def calibracion_simple(metros: float = 10.0, pixeles: float = 100.0) -> Calibration:
    """100 px equivalen a 10 m → 0,1 m/px."""
    return Calibration.from_two_points(
        first=(Pixels(0.0), Pixels(0.0)),
        second=(Pixels(pixeles), Pixels(0.0)),
        real_distance=Meters(metros),
    )


class TestConstruccion:
    def test_la_escala_sale_de_los_dos_puntos(self) -> None:
        cal = calibracion_simple()

        assert cal.meters_per_pixel == pytest.approx(0.1)

    def test_la_distancia_se_mide_en_diagonal(self) -> None:
        """Triángulo 3-4-5: los puntos no tienen por qué estar alineados."""
        cal = Calibration.from_two_points(
            first=(Pixels(0.0), Pixels(0.0)),
            second=(Pixels(30.0), Pixels(40.0)),
            real_distance=Meters(5.0),
        )

        assert cal.pixel_distance == pytest.approx(50.0)
        assert cal.meters_per_pixel == pytest.approx(0.1)

    def test_dos_puntos_coincidentes_se_rechazan(self) -> None:
        """Sin distancia en píxeles no hay escala: dividiría por cero."""
        with pytest.raises(ValueError, match=r"mismo punto|coincid"):
            Calibration.from_two_points(
                first=(Pixels(10.0), Pixels(10.0)),
                second=(Pixels(10.0), Pixels(10.0)),
                real_distance=Meters(5.0),
            )

    def test_una_distancia_real_de_cero_se_rechaza(self) -> None:
        with pytest.raises(ValueError, match=r"mayor que cero|positiva"):
            Calibration.from_two_points(
                first=(Pixels(0.0), Pixels(0.0)),
                second=(Pixels(100.0), Pixels(0.0)),
                real_distance=Meters(0.0),
            )

    def test_es_inmutable(self) -> None:
        cal = calibracion_simple()
        with pytest.raises(AttributeError):
            cal.meters_per_pixel = 1.0  # type: ignore[misc]


class TestConversion:
    def test_de_pixeles_a_metros(self) -> None:
        cal = calibracion_simple()

        assert cal.to_meters(Pixels(250.0)).value == pytest.approx(25.0)

    def test_de_metros_a_pixeles(self) -> None:
        cal = calibracion_simple()

        assert cal.to_pixels(Meters(25.0)).value == pytest.approx(250.0)

    def test_la_conversion_declara_su_procedencia(self) -> None:
        """Una distancia en metros sobre un plano es derivada, no observada:
        procede de una escala que a su vez procede de dos clics."""
        cal = calibracion_simple()

        medida = cal.to_meters_measured(Pixels(250.0))

        assert medida.provenance is Provenance.DERIVED


class TestErrorDeCalibracion:
    def test_se_almacena_un_error_relativo(self) -> None:
        cal = calibracion_simple(pixeles=100.0)

        assert cal.relative_error > 0.0, "una calibración sin error declarado miente"

    def test_calibrar_sobre_mas_pixeles_reduce_el_error(self) -> None:
        """Marcar dos puntos lejanos es más preciso que dos puntos juntos.

        Es el consejo práctico que la UI debe dar, y aquí queda cuantificado.
        """
        corta = calibracion_simple(metros=1.0, pixeles=10.0)
        larga = calibracion_simple(metros=100.0, pixeles=1000.0)

        assert larga.relative_error < corta.relative_error

    def test_el_error_se_propaga_a_las_distancias_convertidas(self) -> None:
        cal = calibracion_simple(pixeles=100.0)

        margen = cal.uncertainty_of(Pixels(250.0))

        assert margen.value == pytest.approx(25.0 * cal.relative_error)


class TestInvariantesPorPropiedad:
    @given(
        pixeles=st.floats(min_value=1.0, max_value=10_000.0, allow_nan=False),
        metros=st.floats(min_value=0.01, max_value=1_000.0, allow_nan=False),
        consulta=st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False),
    )
    def test_ida_y_vuelta_conserva_el_valor(
        self, pixeles: float, metros: float, consulta: float
    ) -> None:
        cal = calibracion_simple(metros=metros, pixeles=pixeles)

        vuelta = cal.to_pixels(cal.to_meters(Pixels(consulta)))

        assert vuelta.value == pytest.approx(consulta, rel=1e-9, abs=1e-9)

    @given(
        pixeles=st.floats(min_value=1.0, max_value=10_000.0, allow_nan=False),
        metros=st.floats(min_value=0.01, max_value=1_000.0, allow_nan=False),
    )
    def test_la_escala_es_siempre_finita_y_positiva(self, pixeles: float, metros: float) -> None:
        cal = calibracion_simple(metros=metros, pixeles=pixeles)

        assert math.isfinite(cal.meters_per_pixel)
        assert cal.meters_per_pixel > 0.0

    @given(
        a=st.floats(min_value=0.0, max_value=1e4, allow_nan=False),
        b=st.floats(min_value=0.0, max_value=1e4, allow_nan=False),
    )
    def test_la_conversion_es_monotona(self, a: float, b: float) -> None:
        """Más píxeles nunca puede significar menos metros."""
        assume(a < b)
        cal = calibracion_simple()

        assert cal.to_meters(Pixels(a)).value <= cal.to_meters(Pixels(b)).value

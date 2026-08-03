"""Value objects de unidades (plan F1.1).

El objetivo no es tipado decorativo: es hacer **imposible** una clase de error que en RF
se comete constantemente — mezclar dBm con dB.

- **dBm** es una potencia absoluta referida a 1 mW. Un RSSI de -65 dBm.
- **dB** es una *relación*, sin referencia. Un SNR de 30 dB, una atenuación de 8 dB.

Sumar dos dBm no significa nada físicamente (-65 dBm + -65 dBm != -130 dBm). Restarlos sí:
da una relación en dB. Esa asimetría es la que codifican estos tipos.

Lo mismo con píxeles y metros: solo una calibración puede convertir entre ellos, y sumar
un píxel a un metro no tiene sentido.
"""

from __future__ import annotations

import pytest

from domain.units import Db, Dbm, Meters, Pixels


class TestAlgebraDeNiveles:
    def test_restar_dos_niveles_da_una_relacion(self) -> None:
        rssi = Dbm(-65.0)
        ruido = Dbm(-95.0)

        resultado = rssi - ruido

        assert isinstance(resultado, Db)
        assert resultado.value == pytest.approx(30.0)

    def test_sumar_una_relacion_a_un_nivel_da_un_nivel(self) -> None:
        resultado = Dbm(-65.0) + Db(3.0)

        assert isinstance(resultado, Dbm)
        assert resultado.value == pytest.approx(-62.0)

    def test_restar_una_relacion_a_un_nivel_da_un_nivel(self) -> None:
        """Atenuar: pasar por una pared resta dB a un nivel."""
        resultado = Dbm(-65.0) - Db(8.0)

        assert isinstance(resultado, Dbm)
        assert resultado.value == pytest.approx(-73.0)

    def test_sumar_dos_niveles_esta_prohibido(self) -> None:
        with pytest.raises(TypeError, match="dBm"):
            Dbm(-65.0) + Dbm(-65.0)  # type: ignore[operator]

    def test_las_relaciones_se_suman_entre_si(self) -> None:
        """Atenuaciones acumuladas: dos paredes."""
        resultado = Db(3.0) + Db(8.0)

        assert isinstance(resultado, Db)
        assert resultado.value == pytest.approx(11.0)


class TestNoMezclarMagnitudes:
    def test_no_se_puede_sumar_pixeles_a_metros(self) -> None:
        with pytest.raises(TypeError):
            Meters(1.0) + Pixels(1.0)  # type: ignore[operator]

    def test_no_se_puede_sumar_un_nivel_a_una_distancia(self) -> None:
        with pytest.raises(TypeError):
            Meters(1.0) + Db(1.0)  # type: ignore[operator]

    def test_metros_se_suman_entre_si(self) -> None:
        assert (Meters(1.5) + Meters(2.5)).value == pytest.approx(4.0)


class TestInvariantes:
    def test_las_unidades_son_inmutables(self) -> None:
        distancia = Meters(3.0)
        with pytest.raises(AttributeError):
            distancia.value = 4.0  # type: ignore[misc]

    def test_una_distancia_no_puede_ser_negativa(self) -> None:
        with pytest.raises(ValueError, match="negativa"):
            Meters(-1.0)

    def test_los_pixeles_no_pueden_ser_negativos(self) -> None:
        with pytest.raises(ValueError, match="negativa"):
            Pixels(-1.0)

    def test_una_relacion_si_puede_ser_negativa(self) -> None:
        """Un SNR negativo es físicamente posible: señal por debajo del ruido."""
        assert Db(-5.0).value == pytest.approx(-5.0)

    def test_un_nivel_si_puede_ser_negativo(self) -> None:
        """Casi todos los RSSI de WiFi son negativos."""
        assert Dbm(-90.0).value == pytest.approx(-90.0)

    def test_se_rechaza_un_valor_no_finito(self) -> None:
        with pytest.raises(ValueError, match="finito"):
            Dbm(float("nan"))

    def test_la_representacion_declara_la_unidad(self) -> None:
        """Un log o un mensaje de error debe decir en qué unidad está el número."""
        assert "dBm" in str(Dbm(-65.0))
        assert "dB" in str(Db(30.0))
        assert "m" in str(Meters(3.0))
        assert "px" in str(Pixels(100.0))

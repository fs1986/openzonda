"""Lecturas con «no disponible» de primera clase, y derivación de SNR.

Este es el módulo donde la honestidad metrológica deja de ser una declaración y se vuelve
ejecutable.

La restricción física (diseño §5): **la mayoría de drivers de Windows no reportan noise
floor**. Sin noise no hay SNR. Las dos salidas fáciles están prohibidas:

1. Devolver ``0`` — indistinguible de un SNR de 0 dB, que es un valor legítimo y pésimo.
2. Estimar el noise floor y presentar el SNR resultante como si fuera medido — prohibido
   explícitamente por la decisión inmutable nº 3 de ``CLAUDE.md``.

La única respuesta honesta es "no disponible", con su motivo, y el tipo obliga a tratarla.
"""

from __future__ import annotations

import pytest

from domain.measurement import Measured, Provenance, Unavailable, UnavailableReason
from domain.rf import snr_from
from domain.units import Db, Dbm


def observado(dbm: float) -> Measured[Dbm]:
    return Measured(Dbm(dbm), Provenance.OBSERVED)


class TestNoDisponibleEsUnValor:
    def test_no_disponible_lleva_siempre_un_motivo(self) -> None:
        nd = Unavailable(UnavailableReason.NOISE_FLOOR_NOT_REPORTED)

        assert nd.reason is UnavailableReason.NOISE_FLOOR_NOT_REPORTED

    def test_no_disponible_es_inmutable(self) -> None:
        nd = Unavailable(UnavailableReason.NOT_MEASURED)
        with pytest.raises(AttributeError):
            nd.reason = UnavailableReason.SCAN_FAILED  # type: ignore[misc]

    def test_no_disponible_no_es_cero_ni_se_le_parece(self) -> None:
        """El error clásico: colar un 0 donde no hay dato."""
        nd = Unavailable(UnavailableReason.NOISE_FLOOR_NOT_REPORTED)

        assert nd != 0
        assert nd != Measured(Dbm(0.0), Provenance.OBSERVED)
        assert not hasattr(nd, "value")

    def test_no_disponible_explica_por_que_al_imprimirse(self) -> None:
        texto = str(Unavailable(UnavailableReason.NOISE_FLOOR_NOT_REPORTED))

        assert "no disponible" in texto.lower()
        assert "noise" in texto.lower() or "ruido" in texto.lower()


class TestDerivacionDeSnr:
    def test_con_ruido_observado_el_snr_es_derivado(self) -> None:
        resultado = snr_from(rssi=observado(-65.0), noise=observado(-95.0))

        assert isinstance(resultado, Measured)
        assert resultado.value == Db(30.0)
        assert resultado.provenance is Provenance.DERIVED, (
            "el SNR se calcula, no se mide: nunca puede ser OBSERVED"
        )

    def test_el_snr_nunca_se_marca_como_observado(self) -> None:
        """Decisión inmutable nº 3: no convertir una estimación en medición."""
        resultado = snr_from(rssi=observado(-65.0), noise=observado(-95.0))

        assert isinstance(resultado, Measured)
        assert not resultado.is_observed()

    def test_sin_ruido_el_snr_es_no_disponible(self) -> None:
        """El caso normal en Windows: el driver no reporta noise floor."""
        resultado = snr_from(
            rssi=observado(-65.0),
            noise=Unavailable(UnavailableReason.NOISE_FLOOR_NOT_REPORTED),
        )

        assert isinstance(resultado, Unavailable)
        assert resultado.reason is UnavailableReason.NOISE_FLOOR_NOT_REPORTED

    def test_sin_rssi_el_snr_es_no_disponible(self) -> None:
        resultado = snr_from(
            rssi=Unavailable(UnavailableReason.SCAN_FAILED),
            noise=observado(-95.0),
        )

        assert isinstance(resultado, Unavailable)

    def test_el_snr_nunca_es_cero_por_falta_de_datos(self) -> None:
        """La regresión que este test protege: devolver 0 dB en vez de N/D."""
        resultado = snr_from(
            rssi=observado(-65.0),
            noise=Unavailable(UnavailableReason.NOISE_FLOOR_NOT_REPORTED),
        )

        assert not isinstance(resultado, Measured)


class TestLaDerivacionNoMejoraLaConfianza:
    """Un valor derivado no puede ser más fiable que su entrada menos fiable."""

    @pytest.mark.parametrize(
        "procedencia_entrada",
        [Provenance.ESTIMATED, Provenance.PREDICTED],
        ids=["estimada", "predictiva"],
    )
    def test_el_snr_hereda_la_procedencia_mas_debil(self, procedencia_entrada: Provenance) -> None:
        resultado = snr_from(
            rssi=Measured(Dbm(-65.0), procedencia_entrada),
            noise=observado(-95.0),
        )

        assert isinstance(resultado, Measured)
        assert resultado.provenance is procedencia_entrada, (
            "derivar de una estimación produce una estimación, no un dato derivado"
        )

    def test_con_ambas_entradas_observadas_el_resultado_es_derivado(self) -> None:
        resultado = snr_from(rssi=observado(-65.0), noise=observado(-95.0))

        assert isinstance(resultado, Measured)
        assert resultado.provenance is Provenance.DERIVED

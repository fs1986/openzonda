"""Tests de contrato del invariante de honestidad metrológica (ADR-006)."""

import pytest

from domain.measurement import Measured, Provenance


def test_valor_viaja_con_su_procedencia() -> None:
    rssi = Measured(-63, Provenance.OBSERVED)
    assert rssi.value == -63
    assert rssi.is_observed()


def test_measured_es_inmutable() -> None:
    rssi = Measured(-63, Provenance.OBSERVED)
    with pytest.raises(AttributeError):
        rssi.provenance = Provenance.ESTIMATED  # type: ignore[misc]


def test_degradar_procedencia_es_legitimo() -> None:
    observed = Measured(-63, Provenance.OBSERVED)
    estimated = observed.downgraded_to(Provenance.ESTIMATED)
    assert estimated.provenance is Provenance.ESTIMATED
    assert observed.provenance is Provenance.OBSERVED  # el original no cambia


def test_no_se_puede_mejorar_la_procedencia() -> None:
    estimated = Measured(-63, Provenance.ESTIMATED)
    with pytest.raises(ValueError, match="honestidad metrológica"):
        estimated.downgraded_to(Provenance.OBSERVED)

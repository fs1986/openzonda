"""Guard de baseline de Windows (OZ-33).

Contexto del bug: el único guard de versión vivía en la `LaunchCondition` del MSI y usaba
la propiedad `WindowsBuild`, que en Windows 10/11 queda congelada en 9600 (Win 8.1) porque
`msiexec.exe` no declara Windows 10 en su manifiesto. Resultado: `9600 >= 19045` es falso y
**toda instalación limpia** en Windows moderno se rechazaba, incluido build 26200 (24H2).

Estos tests fijan el contrato del guard en runtime: comparación por **entero** contra el
umbral de ADR-001 (19045), aceptando los cuatro builds de referencia, y registro del valor
crudo detectado para diagnóstico. La comparación es pura y no toca el registro, así que
corre igual en el CI de Linux que en Windows.
"""

from __future__ import annotations

import logging

import pytest

from openzonda.baseline import (
    BASELINE_MESSAGE,
    SUPPORTED_WINDOWS_BUILD,
    enforce_baseline,
    is_supported_build,
)

# Builds de referencia de la tarjeta OZ-33.
BUILD_22H2 = 19045  # umbral exacto: Windows 10 22H2
BUILD_PREVIO = 19044  # justo por debajo: debe rechazarse
BUILD_WIN11_21H2 = 22000
BUILD_WIN11_24H2 = 26200  # el que hoy falla


def test_umbral_es_el_de_adr_001() -> None:
    assert SUPPORTED_WINDOWS_BUILD == 19045


@pytest.mark.parametrize(
    ("build", "aceptado"),
    [
        (BUILD_PREVIO, False),
        (BUILD_22H2, True),
        (BUILD_WIN11_21H2, True),
        (BUILD_WIN11_24H2, True),
    ],
)
def test_guard_contra_los_cuatro_builds_de_referencia(build: int, aceptado: bool) -> None:
    """19044 rechaza; 19045, 22000 y 26200 aceptan. Protege contra la regresión de OZ-33."""
    assert is_supported_build(build) is aceptado


def test_comparacion_es_por_entero_no_por_string() -> None:
    """Una comparación lexicográfica diría "9600" > "19045"; la numérica no.

    Es exactamente la clase de fallo (string vs entero) que se sospechaba en OZ-33.
    """
    assert is_supported_build(9600) is False


def test_mensaje_menciona_umbral_y_adr() -> None:
    assert "19045" in BASELINE_MESSAGE
    assert "ADR-001" in BASELINE_MESSAGE


def test_enforce_permite_arrancar_en_build_soportado() -> None:
    llamadas: list[str] = []
    ok = enforce_baseline(
        logging.getLogger("oz-test-ok"),
        detect=lambda: BUILD_WIN11_24H2,
        show_error=llamadas.append,
    )
    assert ok is True
    assert llamadas == []  # sistema válido: no se muestra ningún error


def test_enforce_bloquea_build_no_soportado() -> None:
    llamadas: list[str] = []
    ok = enforce_baseline(
        logging.getLogger("oz-test-block"),
        detect=lambda: BUILD_PREVIO,
        show_error=llamadas.append,
    )
    assert ok is False
    assert llamadas == [BASELINE_MESSAGE]  # se avisa al usuario con el mensaje de ADR-001


def test_enforce_loguea_el_build_crudo_detectado(caplog: pytest.LogCaptureFixture) -> None:
    """Criterio de aceptación OZ-33: el guard loguea el valor crudo que detecta."""
    logger = logging.getLogger("oz-test-log")
    logger.propagate = True
    with caplog.at_level(logging.INFO, logger="oz-test-log"):
        enforce_baseline(logger, detect=lambda: BUILD_WIN11_24H2, show_error=lambda _msg: None)
    assert "26200" in caplog.text


def test_enforce_no_bloquea_si_el_build_es_indeterminado(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fail-open deliberado: si no podemos leer la versión, NO repetimos el bug de OZ-33
    (bloquear sistemas válidos). Se continúa, dejando constancia."""
    llamadas: list[str] = []
    logger = logging.getLogger("oz-test-none")
    with caplog.at_level(logging.WARNING, logger="oz-test-none"):
        ok = enforce_baseline(logger, detect=lambda: None, show_error=llamadas.append)
    assert ok is True
    assert llamadas == []
    assert "indetermin" in caplog.text.lower()

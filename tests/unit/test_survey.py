"""SurveySession y punto de medición (diseño §8.1, §10.1, §10.2).

Dos ideas que estos tests fijan:

**La procedencia es por atributo, no por muestra.** El diseño §10.1 lo dice explícitamente
para el modo continuo: *"Posición derivada (flag); RSSI observado"*. En una misma muestra
el RSSI se midió de verdad y la posición se interpoló. Colapsar ambas en una sola etiqueta
perdería justo la información que hace confiable al producto.

**Los flags de calidad no invalidan la muestra: la anotan.** El diseño §10.2 lista casos
—NIC asociada durante el scan, RSSI fuera de rango físico, reloj no monotónico— que hacen
un dato sospechoso sin hacerlo inútil. Descartarlo sería perder información; presentarlo
sin marca sería mentir.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.measurement import Measured, Provenance, Unavailable, UnavailableReason
from domain.survey import (
    AdapterProfile,
    Bssid,
    MeasurementPoint,
    PlanPosition,
    QualityFlag,
    SurveyMode,
    SurveySession,
)
from domain.units import Db, Dbm, Pixels

AHORA = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def adaptador() -> AdapterProfile:
    return AdapterProfile(
        name="Intel Wi-Fi 6E AX211",
        driver_version="23.60.1.1",
        rssi_offset=Db(0.0),
    )


def posicion(x: float = 100.0, y: float = 200.0) -> PlanPosition:
    return PlanPosition(x=Pixels(x), y=Pixels(y))


def punto(
    rssi: float = -65.0,
    *,
    provenance_posicion: Provenance = Provenance.OBSERVED,
    flags: frozenset[QualityFlag] = frozenset(),
) -> MeasurementPoint:
    return MeasurementPoint(
        timestamp=AHORA,
        position=Measured(posicion(), provenance_posicion),
        bssid=Bssid("AA:BB:CC:DD:EE:FF"),
        ssid="OpenZonda-Test",
        rssi=Measured(Dbm(rssi), Provenance.OBSERVED),
        noise=Unavailable(UnavailableReason.NOISE_FLOOR_NOT_REPORTED),
        quality_flags=flags,
    )


class TestBssid:
    def test_se_normaliza_a_minusculas(self) -> None:
        """El mismo BSS escrito de dos formas debe ser el mismo BSS."""
        assert Bssid("AA:BB:CC:DD:EE:FF") == Bssid("aa:bb:cc:dd:ee:ff")

    def test_acepta_separadores_habituales(self) -> None:
        assert Bssid("AA-BB-CC-DD-EE-FF") == Bssid("aa:bb:cc:dd:ee:ff")

    def test_rechaza_algo_que_no_es_una_mac(self) -> None:
        with pytest.raises(ValueError, match="BSSID"):
            Bssid("no-soy-una-mac")

    def test_rechaza_una_mac_incompleta(self) -> None:
        with pytest.raises(ValueError, match="BSSID"):
            Bssid("AA:BB:CC:DD:EE")

    def test_expone_el_oui_para_agrupar_por_fabricante(self) -> None:
        """El diseño §8.1 agrupa BSS en AccessPoint por heurística OUI+SSID."""
        assert Bssid("AA:BB:CC:DD:EE:FF").oui == "aa:bb:cc"


class TestProcedenciaPorAtributo:
    def test_en_stop_and_go_la_posicion_es_observada(self) -> None:
        muestra = punto(provenance_posicion=Provenance.OBSERVED)

        assert muestra.position.provenance is Provenance.OBSERVED
        assert muestra.rssi.provenance is Provenance.OBSERVED

    def test_en_modo_continuo_la_posicion_es_derivada_y_el_rssi_no(self) -> None:
        """Diseño §10.1: la posición se interpola, el RSSI se mide igual."""
        muestra = punto(provenance_posicion=Provenance.DERIVED)

        assert muestra.position.provenance is Provenance.DERIVED
        assert muestra.rssi.provenance is Provenance.OBSERVED, (
            "interpolar la posición no degrada la medición de señal"
        )


class TestSnrDeUnaMuestra:
    def test_sin_noise_el_snr_de_la_muestra_es_no_disponible(self) -> None:
        assert isinstance(punto().snr, Unavailable)

    def test_con_noise_observado_el_snr_es_derivado(self) -> None:
        muestra = MeasurementPoint(
            timestamp=AHORA,
            position=Measured(posicion(), Provenance.OBSERVED),
            bssid=Bssid("AA:BB:CC:DD:EE:FF"),
            ssid="OpenZonda-Test",
            rssi=Measured(Dbm(-65.0), Provenance.OBSERVED),
            noise=Measured(Dbm(-95.0), Provenance.OBSERVED),
        )

        assert isinstance(muestra.snr, Measured)
        assert muestra.snr.value == Db(30.0)
        assert muestra.snr.provenance is Provenance.DERIVED


class TestFlagsDeCalidad:
    def test_una_muestra_limpia_no_tiene_flags(self) -> None:
        assert punto().quality_flags == frozenset()

    def test_un_rssi_fuera_de_rango_fisico_se_detecta(self) -> None:
        """Diseño §10.2: el rango físico plausible es -10..-100 dBm."""
        assert QualityFlag.RSSI_OUT_OF_PHYSICAL_RANGE in MeasurementPoint.detect_flags(
            rssi=Measured(Dbm(+20.0), Provenance.OBSERVED)
        )

    def test_un_rssi_plausible_no_levanta_el_flag(self) -> None:
        assert QualityFlag.RSSI_OUT_OF_PHYSICAL_RANGE not in MeasurementPoint.detect_flags(
            rssi=Measured(Dbm(-65.0), Provenance.OBSERVED)
        )

    def test_los_flags_anotan_pero_no_invalidan(self) -> None:
        """Una muestra sospechosa sigue siendo una muestra."""
        sospechosa = punto(flags=frozenset({QualityFlag.NIC_ASSOCIATED_DURING_SCAN}))

        assert sospechosa.rssi.value == Dbm(-65.0)
        assert sospechosa.is_suspect

    def test_una_muestra_sin_flags_no_es_sospechosa(self) -> None:
        assert not punto().is_suspect

    def test_los_flags_son_inmutables(self) -> None:
        muestra = punto(flags=frozenset({QualityFlag.PARTIAL_SCAN}))

        assert isinstance(muestra.quality_flags, frozenset)


class TestSurveySession:
    def test_registra_el_adaptador_usado(self) -> None:
        """Diseño §10.2: trazabilidad entre equipos. El RSSI no está calibrado y
        cada NIC difiere, así que un dato sin su adaptador no es comparable."""
        sesion = SurveySession(
            mode=SurveyMode.STOP_AND_GO,
            adapter=adaptador(),
            started_at=AHORA,
        )

        assert sesion.adapter.name == "Intel Wi-Fi 6E AX211"
        assert sesion.adapter.driver_version == "23.60.1.1"

    def test_el_offset_del_adaptador_se_declara_aunque_sea_cero(self) -> None:
        assert adaptador().rssi_offset == Db(0.0)

    def test_una_sesion_recien_abierta_no_tiene_muestras(self) -> None:
        sesion = SurveySession(mode=SurveyMode.STOP_AND_GO, adapter=adaptador(), started_at=AHORA)

        assert sesion.points == ()

    def test_anadir_una_muestra_devuelve_una_sesion_nueva(self) -> None:
        """Inmutable: el diseño §8.1 exige Measurement inmutable tras persistir."""
        sesion = SurveySession(mode=SurveyMode.STOP_AND_GO, adapter=adaptador(), started_at=AHORA)

        con_muestra = sesion.with_point(punto())

        assert len(con_muestra.points) == 1
        assert sesion.points == (), "la sesión original no se toca"

    def test_el_timestamp_debe_llevar_zona_horaria(self) -> None:
        """Un survey se compara entre equipos y husos: un naive datetime es ambiguo."""
        with pytest.raises(ValueError, match=r"zona horaria|UTC|tzinfo"):
            SurveySession(
                mode=SurveyMode.STOP_AND_GO,
                adapter=adaptador(),
                started_at=datetime(2026, 8, 2, 12, 0),
            )

"""Sesión de survey y punto de medición (diseño §8.1, §10.1, §10.2).

Dos ideas gobiernan este módulo.

**La procedencia es por atributo, no por muestra.** El diseño §10.1 lo dice para el modo
continuo: *"Posición derivada (flag); RSSI observado"*. En una misma muestra el RSSI se
midió de verdad y la posición se interpoló. Una sola etiqueta por muestra perdería justo
la información que hace confiable al producto.

**Los flags de calidad anotan, no invalidan.** El diseño §10.2 lista casos —NIC asociada
durante el scan, RSSI fuera de rango físico, reloj no monotónico— que hacen un dato
sospechoso sin hacerlo inútil. Descartarlo perdería información sobre un adaptador que se
comporta mal; presentarlo sin marca sería mentir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from uuid import UUID, uuid4

from domain.measurement import Measured, Provenance, Reading, Unavailable
from domain.rf import is_physically_plausible, snr_from
from domain.units import Db, Dbm, Pixels

_MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
_SEPARADORES = re.compile(r"[-.\s]")

NO_RSSI_OFFSET = Db(0.0)
"""Offset nulo. Se declara igualmente en el perfil del adaptador: «sin corrección» es
una afirmación sobre la NIC, no la ausencia de dato."""


@dataclass(frozen=True, slots=True)
class Bssid:
    """Identidad observable de un BSS. Se normaliza para que la comparación funcione.

    El mismo BSS escrito ``AA-BB-CC-DD-EE-FF`` y ``aa:bb:cc:dd:ee:ff`` es el mismo BSS;
    sin normalizar, agrupar muestras produciría duplicados fantasma.
    """

    value: str

    def __init__(self, raw: str) -> None:
        normalizado = _SEPARADORES.sub(":", raw.strip().lower())
        if not _MAC.match(normalizado):
            raise ValueError(f"BSSID inválido: {raw!r}. Se esperan 6 octetos hexadecimales.")
        object.__setattr__(self, "value", normalizado)

    def __str__(self) -> str:
        return self.value

    @property
    def oui(self) -> str:
        """Los tres primeros octetos: identifican al fabricante.

        El diseño §8.1 agrupa BSS en AccessPoint por heurística OUI + SSID.
        """
        return ":".join(self.value.split(":")[:3])


class SurveyMode(Enum):
    """Modos de captura del diseño §10.1."""

    STOP_AND_GO = "stop_and_go"
    """El usuario marca su posición y se capturan N escaneos. Posición observada."""

    CONTINUOUS_ASSISTED = "continuous_assisted"
    """Tramo caminado entre dos marcas; posiciones intermedias interpoladas.
    La posición pasa a ser derivada; el RSSI sigue siendo observado."""


class QualityFlag(Enum):
    """Anomalías que hacen una muestra sospechosa sin invalidarla (diseño §10.2)."""

    NIC_ASSOCIATED_DURING_SCAN = auto()
    """La NIC estaba asociada a una red mientras escaneaba: puede sesgar el resultado."""

    PARTIAL_SCAN = auto()
    """El escaneo devolvió menos BSS de los esperados; posible barrido incompleto."""

    RSSI_OUT_OF_PHYSICAL_RANGE = auto()
    """RSSI fuera de -100..-10 dBm. Suele indicar un driver que reporta en otra escala."""

    NON_MONOTONIC_CLOCK = auto()
    """El reloj retrocedió entre muestras: el orden temporal no es fiable."""


@dataclass(frozen=True, slots=True)
class PlanPosition:
    """Coordenada sobre la imagen del plano, en píxeles.

    Se guarda en píxeles y no en metros a propósito: los píxeles son lo que el usuario
    marcó. Los metros dependen de una calibración que puede rehacerse después, y
    almacenarlos congelaría una escala que quizá era incorrecta.
    """

    x: Pixels
    y: Pixels


@dataclass(frozen=True, slots=True)
class AdapterProfile:
    """NIC, driver y offset aplicado (diseño §10.2).

    El RSSI no está calibrado y cada NIC difiere, así que **un dato sin su adaptador no es
    comparable** con el de otro equipo. Por eso el perfil viaja con la sesión y el reporte
    lo declara.
    """

    name: str
    driver_version: str
    rssi_offset: Db = NO_RSSI_OFFSET


@dataclass(frozen=True, slots=True)
class MeasurementPoint:
    """Una muestra RF con su posición. Inmutable (diseño §8.1)."""

    timestamp: datetime
    position: Measured[PlanPosition]
    bssid: Bssid
    ssid: str
    rssi: Reading[Dbm]
    noise: Reading[Dbm]
    quality_flags: frozenset[QualityFlag] = frozenset()

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError(
                "El timestamp de una muestra debe llevar zona horaria: un survey se "
                "compara entre equipos y husos, y un datetime naive es ambiguo."
            )

    @property
    def snr(self) -> Reading[Db]:
        """SNR derivado. «No disponible» cuando falta el noise floor, que es lo normal."""
        return snr_from(self.rssi, self.noise)

    @property
    def is_suspect(self) -> bool:
        return bool(self.quality_flags)

    @staticmethod
    def detect_flags(rssi: Reading[Dbm]) -> frozenset[QualityFlag]:
        """Deriva los flags que se pueden deducir del propio valor (diseño §10.2)."""
        flags: set[QualityFlag] = set()
        if isinstance(rssi, Measured) and not is_physically_plausible(rssi.value):
            flags.add(QualityFlag.RSSI_OUT_OF_PHYSICAL_RANGE)
        return frozenset(flags)


@dataclass(frozen=True, slots=True)
class SurveySession:
    """Una ejecución de survey: modo, adaptador y las muestras capturadas."""

    mode: SurveyMode
    adapter: AdapterProfile
    started_at: datetime
    points: tuple[MeasurementPoint, ...] = ()
    id: UUID = field(default_factory=uuid4, kw_only=True)

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None:
            raise ValueError(
                "El inicio de la sesión debe llevar zona horaria: sin ella no se puede "
                "comparar con una sesión capturada en otro huso."
            )

    def with_point(self, point: MeasurementPoint) -> SurveySession:
        """Devuelve una sesión nueva con la muestra añadida. No muta la original."""
        return SurveySession(
            mode=self.mode,
            adapter=self.adapter,
            started_at=self.started_at,
            points=(*self.points, point),
            id=self.id,
        )

    @property
    def unavailable_snr_count(self) -> int:
        """Cuántas muestras no pudieron dar SNR.

        Útil para que el reporte diga *"SNR no disponible en 412 de 412 muestras porque el
        driver no reporta noise floor"* en lugar de dibujar un heatmap vacío sin explicar
        por qué.
        """
        return sum(1 for p in self.points if isinstance(p.snr, Unavailable))

    @property
    def observed_position_count(self) -> int:
        return sum(1 for p in self.points if p.position.provenance is Provenance.OBSERVED)

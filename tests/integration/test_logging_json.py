"""Logging estructurado en JSON lines (diseño §19).

El diseño fija JSON lines con niveles configurables y rotación por tamaño (10 MB, 5 copias).
El formato importa porque el bundle de diagnóstico exportable se construye sobre estos
logs: si una línea no es JSON válido, el bundle deja de ser procesable justo cuando más
falta hace, que es cuando algo ha fallado en la máquina de otro.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from openzonda.logging_setup import (
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    JsonLinesFormatter,
    setup_logging,
)


def _formatear(record: logging.LogRecord) -> dict[str, object]:
    linea = JsonLinesFormatter().format(record)
    return json.loads(linea)


def _record(**kwargs: object) -> logging.LogRecord:
    base = {
        "name": "openzonda.test",
        "level": logging.INFO,
        "pathname": __file__,
        "lineno": 10,
        "msg": "arranque completado",
        "args": (),
        "exc_info": None,
    }
    base.update(kwargs)
    return logging.LogRecord(**base)  # type: ignore[arg-type]


def test_cada_linea_es_json_valido_con_los_campos_esperados() -> None:
    datos = _formatear(_record())

    assert datos["level"] == "INFO"
    assert datos["logger"] == "openzonda.test"
    assert datos["message"] == "arranque completado"
    assert isinstance(datos["timestamp"], str)


def test_el_timestamp_es_iso8601_en_utc() -> None:
    from datetime import datetime

    datos = _formatear(_record())

    momento = datetime.fromisoformat(str(datos["timestamp"]))
    assert momento.tzinfo is not None, "un timestamp sin zona horaria no es comparable"


def test_los_argumentos_se_interpolan() -> None:
    datos = _formatear(_record(msg="cargados %d settings", args=(3,)))

    assert datos["message"] == "cargados 3 settings"


def test_las_excepciones_viajan_en_su_propio_campo() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        datos = _formatear(_record(level=logging.ERROR, exc_info=sys.exc_info()))

    assert "ValueError: boom" in str(datos["exception"])
    assert "\n" not in JsonLinesFormatter().format(_record(level=logging.ERROR, msg="x")), (
        "una línea de log no puede contener saltos de línea sin escapar"
    )


def test_los_saltos_de_linea_del_mensaje_no_rompen_el_formato() -> None:
    linea = JsonLinesFormatter().format(_record(msg="primera\nsegunda"))

    assert linea.count("\n") == 0
    assert json.loads(linea)["message"] == "primera\nsegunda"


def test_setup_logging_escribe_un_archivo_con_rotacion(tmp_path: Path) -> None:
    logger = setup_logging(logs_dir=tmp_path, level="INFO", logger_name="oz.test.setup")
    try:
        logger.info("hola")

        archivos = list(tmp_path.glob("*.log"))
        assert len(archivos) == 1

        contenido = archivos[0].read_text(encoding="utf-8").strip()
        assert json.loads(contenido)["message"] == "hola"

        rotativo = logger.handlers[0]
        assert getattr(rotativo, "maxBytes", None) == LOG_MAX_BYTES
        assert getattr(rotativo, "backupCount", None) == LOG_BACKUP_COUNT
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


def test_la_rotacion_respeta_el_diseno() -> None:
    assert LOG_MAX_BYTES == 10 * 1024 * 1024
    assert LOG_BACKUP_COUNT == 5

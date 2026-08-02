"""Logging estructurado en JSON lines (diseño §19).

Una línea de log = un objeto JSON. El formato no es capricho: el bundle de diagnóstico
exportable se construye sobre estos archivos, y una línea mal formada lo vuelve
improcesable justo cuando más falta hace — cuando algo ha fallado en la máquina de otro.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILENAME = "openzonda.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB por archivo, diseño §19
LOG_BACKUP_COUNT = 5  # 5 archivos de respaldo, diseño §19


class JsonLinesFormatter(logging.Formatter):
    """Serializa cada registro como un único objeto JSON en una sola línea."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # json.dumps escapa los saltos de línea, así que un mensaje multilínea o un
        # traceback no pueden partir el registro en dos entradas.
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(
    logs_dir: Path,
    level: str = "INFO",
    logger_name: str = "openzonda",
) -> logging.Logger:
    """Configura el logger de la aplicación con rotación por tamaño.

    Es idempotente: reconfigurar no acumula handlers duplicados.
    """
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    archivo = RotatingFileHandler(
        logs_dir / LOG_FILENAME,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    archivo.setFormatter(JsonLinesFormatter())
    logger.addHandler(archivo)

    return logger

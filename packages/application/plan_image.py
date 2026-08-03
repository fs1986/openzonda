"""Lectura honesta de un plano: bytes -> (formato, dimensiones, DPI con procedencia).

Módulo **puro** (solo stdlib + dominio): recibe los bytes de un archivo de imagen y devuelve
un :class:`PlanImage`, o lanza un :class:`PlanImageError` tipado. No hace I/O de archivo, no
usa Windows, Qt ni Pillow — por eso vive en `application` y no necesita port ni adaptador; el
store (`persistence`) y el servicio lo llaman directo.

Dos invariantes gobiernan el diseño:

- **Honestidad del DPI (ADR-006).** Si el archivo trae resolución real (pHYs en PNG, JFIF o
  EXIF en JPEG) el DPI es `OBSERVED`; si no, se asume 96 y queda `ESTIMATED`. El número nunca
  viaja crudo: se devuelve envuelto en `Measured`, así nadie puede tratar un DPI asumido como
  medido.
- **No decodificar para medir.** El formato, las dimensiones y el DPI se leen de las
  *cabeceras*, sin expandir el bitmap. Un PNG que declara 12000x12000 se rechaza a partir de
  su IHDR de 25 bytes, sin asignar 144 M de píxeles: es la protección contra bombas de
  descompresión y lo que hace barato el límite de píxeles.

El rechazo por tamaño **distingue el motivo**: superar el límite de píxeles y superar el de
bytes son errores distintos con mensajes distintos (uno habla de `px`, el otro de `MB`), cada
uno con el valor real y el violado. Nunca un fallo silencioso ni truncado.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum, auto

from domain.measurement import Measured, Provenance

MAX_DIMENSION_PX = 12000
"""Lado máximo del plano en píxeles. Por encima, `TOO_MANY_PIXELS`."""

MAX_BYTES = 50 * 1024 * 1024
"""Peso máximo del archivo en bytes (~50 MB). Por encima, `TOO_MANY_BYTES`."""

_DEFAULT_DPI = 96.0
"""DPI asumido cuando el archivo no declara resolución real. Es el estándar de Windows y se
marca `ESTIMATED`: es una suposición, no una medición."""

_METERS_PER_INCH = 0.0254
_CM_PER_INCH = 2.54


class PlanImageFormat(Enum):
    """Formato soportado del plano. El *value* es la extensión del asset (OZ-9a, inc. 3)."""

    PNG = "png"
    JPEG = "jpg"


@dataclass(frozen=True, slots=True)
class PlanImage:
    """Resultado de leer un plano: qué es, cuánto mide y a qué resolución (con procedencia)."""

    format: PlanImageFormat
    width_px: int
    height_px: int
    dpi: Measured[float]


class PlanImageErrorKind(Enum):
    """Por qué no se pudo aceptar el archivo como plano. Cada motivo tiene su mensaje."""

    NOT_AN_IMAGE = auto()  # los bytes no corresponden a ninguna imagen conocida
    UNSUPPORTED_FORMAT = auto()  # es una imagen, pero de un formato que no soportamos
    MALFORMED = auto()  # es PNG/JPEG pero su cabecera está rota o truncada
    TOO_MANY_PIXELS = auto()  # excede el lado máximo en píxeles
    TOO_MANY_BYTES = auto()  # excede el peso máximo en bytes


class PlanImageError(Exception):
    """Rechazo tipado de un plano, con motivo clasificado y mensaje para el usuario."""

    def __init__(self, kind: PlanImageErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


def read_plan_image(data: bytes) -> PlanImage:
    """Lee `data` como plano PNG/JPEG. Devuelve :class:`PlanImage` o lanza `PlanImageError`.

    El orden de las comprobaciones importa: primero el peso (barato, protege memoria), luego
    el formato por *magic bytes* (no por el nombre del archivo, que el usuario controla),
    luego las dimensiones de la cabecera y por último el DPI.
    """
    if len(data) > MAX_BYTES:
        raise PlanImageError(
            PlanImageErrorKind.TOO_MANY_BYTES,
            f"El archivo pesa {_mb(len(data))} MB y supera el límite de {_mb(MAX_BYTES)} MB.",
        )

    fmt = _classify(data)
    if fmt is PlanImageFormat.PNG:
        width, height = _png_dimensions(data)
        dpi = _png_dpi(data)
    else:
        width, height, dpi = _jpeg_read(data)

    if width <= 0 or height <= 0:
        raise PlanImageError(
            PlanImageErrorKind.MALFORMED,
            f"El plano declara dimensiones inválidas ({width}x{height} px).",
        )
    if width > MAX_DIMENSION_PX or height > MAX_DIMENSION_PX:
        raise PlanImageError(
            PlanImageErrorKind.TOO_MANY_PIXELS,
            f"El plano mide {width}x{height} px y supera el límite de "
            f"{MAX_DIMENSION_PX} px por lado.",
        )
    return PlanImage(format=fmt, width_px=width, height_px=height, dpi=dpi)


# --------------------------------------------------------------------------- formato

_PNG_SIG = b"\x89PNG\r\n\x1a\n"

# Firmas de imágenes que reconocemos pero no soportamos: se rechazan con un mensaje que dice
# qué son, en vez de un genérico "no es una imagen".
_UNSUPPORTED_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"GIF87a", "GIF"),
    (b"GIF89a", "GIF"),
    (b"BM", "BMP"),
    (b"II\x2a\x00", "TIFF"),
    (b"MM\x00\x2a", "TIFF"),
)


def _classify(data: bytes) -> PlanImageFormat:
    if data[:8] == _PNG_SIG:
        return PlanImageFormat.PNG
    if data[:3] == b"\xff\xd8\xff":
        return PlanImageFormat.JPEG
    # WEBP: "RIFF"????"WEBP".
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        raise _unsupported("WEBP")
    for firma, nombre in _UNSUPPORTED_SIGNATURES:
        if data.startswith(firma):
            raise _unsupported(nombre)
    raise PlanImageError(
        PlanImageErrorKind.NOT_AN_IMAGE,
        f"El archivo no es una imagen PNG ni JPEG reconocible "
        f"(empieza con {data[:8].hex() or '<vacío>'}).",
    )


def _unsupported(nombre: str) -> PlanImageError:
    return PlanImageError(
        PlanImageErrorKind.UNSUPPORTED_FORMAT,
        f"El archivo es {nombre}, un formato no soportado; usá PNG o JPEG.",
    )


# ------------------------------------------------------------------------------ PNG


def _png_dimensions(data: bytes) -> tuple[int, int]:
    # Tras la firma (8 bytes): longitud(4) + "IHDR"(4) + ancho(4) + alto(4) + ...
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise PlanImageError(
            PlanImageErrorKind.MALFORMED, "El PNG no tiene una cabecera IHDR válida."
        )
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _png_dpi(data: bytes) -> Measured[float]:
    off = 8  # tras la firma
    n = len(data)
    while off + 8 <= n:
        (length,) = struct.unpack(">I", data[off : off + 4])
        ctype = data[off + 4 : off + 8]
        if ctype == b"pHYs":
            body = data[off + 8 : off + 8 + length]
            if len(body) >= 9:
                x_ppu, _y_ppu, unit = struct.unpack(">IIB", body[:9])
                if unit == 1 and x_ppu > 0:  # unidad 1 = píxeles por metro
                    return Measured(x_ppu * _METERS_PER_INCH, Provenance.OBSERVED)
            break
        if ctype == b"IEND":
            break
        off += 12 + length  # longitud(4) + tipo(4) + datos + crc(4)
    return _estimated_dpi()


# ----------------------------------------------------------------------------- JPEG

# Marcadores Start-Of-Frame que llevan dimensiones (se excluyen C4=DHT, C8=JPG, CC=DAC).
_SOF_MARKERS = frozenset(
    {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
)


def _jpeg_read(data: bytes) -> tuple[int, int, Measured[float]]:
    off = 2  # tras SOI (FFD8)
    n = len(data)
    dims: tuple[int, int] | None = None
    dpi: Measured[float] | None = None
    while off + 1 < n:
        if data[off] != 0xFF:
            off += 1
            continue
        marker = data[off + 1]
        off += 2
        # Marcadores autónomos (sin segmento de longitud): relleno, SOI/EOI, RSTn, TEM.
        if marker in (0xFF, 0x00, 0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if off + 2 > n:
            break
        (seg_len,) = struct.unpack(">H", data[off : off + 2])
        payload = data[off + 2 : off + seg_len]
        if marker == 0xE0:
            candidato = _jfif_dpi(payload)
            if candidato is not None and dpi is None:
                dpi = candidato  # JFIF solo si EXIF no lo fijó ya
        elif marker == 0xE1:
            candidato = _exif_dpi(payload)
            if candidato is not None:
                dpi = candidato  # EXIF es autoritativo: pisa a JFIF
        elif marker in _SOF_MARKERS:
            if len(payload) >= 5:
                height, width = struct.unpack(">HH", payload[1:5])
                dims = (width, height)
        elif marker == 0xDA:  # SOS: empiezan los datos de escaneo, no hay más cabeceras
            break
        off += seg_len
    if dims is None:
        raise PlanImageError(
            PlanImageErrorKind.MALFORMED, "El JPEG no declara dimensiones (sin SOF)."
        )
    return dims[0], dims[1], dpi or _estimated_dpi()


def _jfif_dpi(payload: bytes) -> Measured[float] | None:
    # "JFIF\0"(5) + versión(2) + unidades(1) + Xdensity(2) + Ydensity(2) + ...
    if payload[:5] != b"JFIF\x00" or len(payload) < 12:
        return None
    units = payload[7]
    (xd,) = struct.unpack(">H", payload[8:10])
    if xd <= 0:
        return None
    if units == 1:  # puntos por pulgada
        return Measured(float(xd), Provenance.OBSERVED)
    if units == 2:  # puntos por cm
        return Measured(xd * _CM_PER_INCH, Provenance.OBSERVED)
    return None  # unidad 0 = solo relación de aspecto, no es un DPI real


def _exif_dpi(payload: bytes) -> Measured[float] | None:
    if payload[:6] != b"Exif\x00\x00":
        return None
    tiff = payload[6:]
    if len(tiff) < 8:
        return None
    if tiff[:2] == b"II":
        bo = "<"
    elif tiff[:2] == b"MM":
        bo = ">"
    else:
        return None
    (ifd_off,) = struct.unpack(bo + "I", tiff[4:8])
    if ifd_off + 2 > len(tiff):
        return None
    (count,) = struct.unpack(bo + "H", tiff[ifd_off : ifd_off + 2])
    xres: float | None = None
    unit = 2  # por defecto EXIF/TIFF: pulgadas
    base = ifd_off + 2
    for i in range(count):
        e = base + i * 12
        if e + 12 > len(tiff):
            break
        tag, typ, _cnt = struct.unpack(bo + "HHI", tiff[e : e + 8])
        valoff = tiff[e + 8 : e + 12]
        if tag == 0x011A and typ == 5:  # XResolution, RATIONAL (offset a num/den)
            (ro,) = struct.unpack(bo + "I", valoff)
            if ro + 8 <= len(tiff):
                num, den = struct.unpack(bo + "II", tiff[ro : ro + 8])
                if den:
                    xres = num / den
        elif tag == 0x0128 and typ == 3:  # ResolutionUnit, SHORT (en el propio campo)
            (unit,) = struct.unpack(bo + "H", valoff[:2])
    if xres is None or xres <= 0:
        return None
    if unit == 3:  # cm
        return Measured(xres * _CM_PER_INCH, Provenance.OBSERVED)
    if unit == 2:  # pulgadas
        return Measured(xres, Provenance.OBSERVED)
    return None  # unidad 1 = sin unidad, no es un DPI real


# --------------------------------------------------------------------------- helpers


def _estimated_dpi() -> Measured[float]:
    return Measured(_DEFAULT_DPI, Provenance.ESTIMATED)


def _mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.1f}"

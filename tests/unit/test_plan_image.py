"""Contrato del módulo de imagen del plano (OZ-9a, incremento 2).

`read_plan_image` recibe **bytes** y devuelve `PlanImage` (formato, dimensiones y DPI con
procedencia) o lanza un `PlanImageError` **tipado**. Estos tests fijan la honestidad
metrológica del DPI (OBSERVED si el archivo lo trae, ESTIMATED si se asume 96) y el rechazo
que distingue *píxeles* de *bytes*, todo sin depender de fixtures binarios: las imágenes se
construyen a mano (headers válidos, sin datos de píxel reales — el módulo no decodifica).
"""

from __future__ import annotations

import struct
import zlib

import pytest

from application.plan_image import (
    MAX_BYTES,
    MAX_DIMENSION_PX,
    PlanImageError,
    PlanImageErrorKind,
    PlanImageFormat,
    read_plan_image,
)
from domain.measurement import Provenance

# --------------------------------------------------------------------------- fixtures

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _chunk(ctype: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)


def _png(width: int, height: int, *, phys: tuple[int, int, int] | None = None) -> bytes:
    """PNG mínimo válido. `phys` = (x_ppu, y_ppu, unidad) para el chunk pHYs (unidad 1=metro).

    El IDAT es basura: no se decodifica, así que declarar 12000x12000 no cuesta memoria."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, color RGB
    out = PNG_SIG + _chunk(b"IHDR", ihdr)
    if phys is not None:
        out += _chunk(b"pHYs", struct.pack(">IIB", *phys))
    out += _chunk(b"IDAT", zlib.compress(b"\x00"))
    out += _chunk(b"IEND", b"")
    return out


_SOF0 = 0xC0


def _seg(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def _jpeg(
    width: int,
    height: int,
    *,
    jfif: tuple[int, int, int] | None = None,
    exif: bytes | None = None,
) -> bytes:
    """JPEG mínimo válido. `jfif` = (unidades, Xdensity, Ydensity); `exif` = payload APP1."""
    out = b"\xff\xd8"  # SOI
    if jfif is not None:
        units, xd, yd = jfif
        payload = b"JFIF\x00\x01\x02" + bytes([units]) + struct.pack(">HH", xd, yd) + b"\x00\x00"
        out += _seg(0xE0, payload)
    if exif is not None:
        out += _seg(0xE1, exif)
    sof = bytes([8]) + struct.pack(">HH", height, width) + bytes([1, 1, 0x11, 0])
    out += _seg(_SOF0, sof)
    out += b"\xff\xd9"  # EOI
    return out


def _exif_app1(xres: int, unit: int) -> bytes:
    """Payload EXIF (APP1) con XResolution (RATIONAL) y ResolutionUnit (2=pulgada, 3=cm)."""
    tiff = b"II" + struct.pack("<H", 0x2A) + struct.pack("<I", 8)  # little-endian, IFD0 en 8
    ifd = struct.pack("<H", 2)  # dos entradas
    ifd += struct.pack("<HHI", 0x011A, 5, 1) + struct.pack("<I", 38)  # XResolution -> offset 38
    ifd += struct.pack("<HHI", 0x0128, 3, 1) + struct.pack("<I", unit)  # ResolutionUnit
    ifd += struct.pack("<I", 0)  # sin IFD siguiente
    ifd += struct.pack("<II", xres, 1)  # rational en offset 38
    return b"Exif\x00\x00" + tiff + ifd


# ------------------------------------------------------------------- formato y dimensiones


def test_png_por_magic_bytes_no_por_nombre() -> None:
    img = read_plan_image(_png(800, 600))
    assert img.format is PlanImageFormat.PNG
    assert (img.width_px, img.height_px) == (800, 600)


def test_jpeg_por_magic_bytes() -> None:
    img = read_plan_image(_jpeg(1024, 768))
    assert img.format is PlanImageFormat.JPEG
    assert (img.width_px, img.height_px) == (1024, 768)


# --------------------------------------------------------------------------- DPI honesto


def test_png_sin_phys_dpi_estimado_96() -> None:
    img = read_plan_image(_png(400, 300))
    assert img.dpi.value == pytest.approx(96.0)
    assert img.dpi.provenance is Provenance.ESTIMATED


def test_png_con_phys_en_metros_dpi_observado() -> None:
    # 11811 px/m ~= 300 dpi (300 / 0.0254).
    img = read_plan_image(_png(400, 300, phys=(11811, 11811, 1)))
    assert img.dpi.value == pytest.approx(300.0, abs=0.5)
    assert img.dpi.provenance is Provenance.OBSERVED


def test_png_phys_unidad_desconocida_no_es_dpi() -> None:
    # unidad 0 = solo relación de aspecto, no hay resolución real -> se asume 96 estimado.
    img = read_plan_image(_png(400, 300, phys=(3, 4, 0)))
    assert img.dpi.value == pytest.approx(96.0)
    assert img.dpi.provenance is Provenance.ESTIMATED


def test_jpeg_sin_metadatos_dpi_estimado_96() -> None:
    img = read_plan_image(_jpeg(640, 480))
    assert img.dpi.value == pytest.approx(96.0)
    assert img.dpi.provenance is Provenance.ESTIMATED


def test_jpeg_jfif_dpi_en_pulgadas_observado() -> None:
    img = read_plan_image(_jpeg(640, 480, jfif=(1, 150, 150)))
    assert img.dpi.value == pytest.approx(150.0)
    assert img.dpi.provenance is Provenance.OBSERVED


def test_jpeg_jfif_dpi_en_cm_convertido() -> None:
    # unidad 2 = puntos/cm; 100 dots/cm = 254 dpi.
    img = read_plan_image(_jpeg(640, 480, jfif=(2, 100, 100)))
    assert img.dpi.value == pytest.approx(254.0)
    assert img.dpi.provenance is Provenance.OBSERVED


def test_jpeg_exif_dpi_observado() -> None:
    img = read_plan_image(_jpeg(800, 600, exif=_exif_app1(200, 2)))
    assert img.dpi.value == pytest.approx(200.0)
    assert img.dpi.provenance is Provenance.OBSERVED


def test_jpeg_exif_gana_sobre_jfif_sin_resolucion_real() -> None:
    # JFIF con unidad 0 (aspecto) no aporta DPI; EXIF sí -> gana EXIF.
    img = read_plan_image(_jpeg(800, 600, jfif=(0, 1, 1), exif=_exif_app1(200, 2)))
    assert img.dpi.value == pytest.approx(200.0)
    assert img.dpi.provenance is Provenance.OBSERVED


# ------------------------------------------------------------------- rechazos tipados


def test_rechaza_no_imagen_renombrada() -> None:
    with pytest.raises(PlanImageError) as exc:
        read_plan_image(b"esto no es una imagen, solo texto plano renombrado a .png")
    assert exc.value.kind is PlanImageErrorKind.NOT_AN_IMAGE


def test_rechaza_formato_reconocido_pero_no_soportado() -> None:
    gif = b"GIF89a" + b"\x00" * 20
    with pytest.raises(PlanImageError) as exc:
        read_plan_image(gif)
    assert exc.value.kind is PlanImageErrorKind.UNSUPPORTED_FORMAT


def test_rechaza_exceso_de_pixeles_distinguiendo_px() -> None:
    with pytest.raises(PlanImageError) as exc:
        read_plan_image(_png(MAX_DIMENSION_PX + 1, 100))
    err = exc.value
    assert err.kind is PlanImageErrorKind.TOO_MANY_PIXELS
    # El mensaje distingue: habla de píxeles, da el valor real y el límite, NO de bytes.
    assert "px" in err.message
    assert str(MAX_DIMENSION_PX + 1) in err.message
    assert str(MAX_DIMENSION_PX) in err.message
    assert "MB" not in err.message


def test_rechaza_exceso_de_bytes_distinguiendo_bytes() -> None:
    demasiado = b"\x00" * (MAX_BYTES + 1)
    with pytest.raises(PlanImageError) as exc:
        read_plan_image(demasiado)
    err = exc.value
    assert err.kind is PlanImageErrorKind.TOO_MANY_BYTES
    # El mensaje distingue: habla de peso en MB, NO de píxeles.
    assert "MB" in err.message
    assert "px" not in err.message


def test_rechaza_png_truncado_como_malformado() -> None:
    with pytest.raises(PlanImageError) as exc:
        read_plan_image(PNG_SIG + b"\x00\x00")
    assert exc.value.kind is PlanImageErrorKind.MALFORMED


def test_rechaza_dimensiones_cero() -> None:
    with pytest.raises(PlanImageError) as exc:
        read_plan_image(_png(0, 100))
    assert exc.value.kind is PlanImageErrorKind.MALFORMED

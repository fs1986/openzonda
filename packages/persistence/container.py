"""Contenedor de proyecto `.wifisurvey` (ADR-004, diseño §14.1, §17.3).

Un ZIP con `manifest.json`, `data/survey.sqlite` y `assets/`. Autocontenido y trasladable:
nunca rutas absolutas, los planos siempre embebidos con su hash.

Dos exigencias dominan este módulo, y ambas vienen de la misma constatación: un
`.wifisurvey` contiene **trabajo de campo irrepetible** y puede llegar de un tercero.

**Guardar no puede destruir lo anterior.** Se escribe a un temporal, se hace `fsync`, y solo
entonces se renombra. `os.replace` es atómico dentro del mismo volumen, así que en cualquier
instante el archivo de destino es o la versión vieja completa o la nueva completa, nunca una
mezcla.

**Abrir no puede hacer daño.** La regla que gobierna todo el lector: *nada de lo que dice el
archivo se cree hasta haberlo comprobado leyendo*. En particular, `ZipInfo.file_size` lo
escribe quien construyó el archivo, así que **jamás** se usa para reservar memoria ni como
prueba de que algo cabe; sirve como rechazo temprano barato, y el límite real se aplica
contando los bytes que salen del descompresor.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

CONTAINER_FORMAT = "openzonda.wifisurvey"
"""Marca del formato dentro del manifest. Distingue nuestro contenedor de un ZIP ajeno."""

CONTAINER_FORMAT_VERSION = 1
"""Versión del **contenedor**, distinta de la del esquema SQLite que lleva dentro."""

MANIFEST_NAME = "manifest.json"
DATABASE_ENTRY = "data/survey.sqlite"
ASSETS_PREFIX = "assets/"

_ZIP_MAGIC = b"PK\x03\x04"
_TEMP_SUFFIX = ".tmp"
_UNIDAD_WINDOWS = re.compile(r"^[a-zA-Z]:")
# Fecha fija para que dos guardados del mismo contenido den bytes idénticos. Sin esto, el
# reloj se filtraría en cada entrada y las copias incrementales y los diffs dejarían de
# funcionar aunque no hubiera cambiado nada.
_FECHA_FIJA = (1980, 1, 1, 0, 0, 0)


class ContainerError(RuntimeError):
    """Raíz de los fallos del contenedor."""


class NotAContainerError(ContainerError):
    """El archivo no es un `.wifisurvey`."""


class ContainerTooNewError(ContainerError):
    """Lo escribió una versión más nueva de OpenZonda."""


class CorruptContainerError(ContainerError):
    """Es un `.wifisurvey`, pero está dañado o manipulado."""


class HostileContainerError(ContainerError):
    """El contenido es peligroso: rutas que escapan, expansión abusiva, enlaces.

    Se distingue de «corrupto» a propósito. Un archivo corrupto es un accidente y el
    usuario puede intentar recuperarlo; este otro caso indica que **alguien lo construyó
    así**, y el mensaje no debe sugerir que reintente.
    """


@dataclass(frozen=True, slots=True)
class ContainerLimits:
    """Techos de la extracción. Inyectables para poder testearlos sin mover gigabytes."""

    max_entries: int = 10_000
    max_total_bytes: int = 2 * 1024**3
    max_entry_bytes: int = 512 * 1024**2
    max_compression_ratio: float = 200.0
    ratio_floor_bytes: int = 8 * 1024**2
    """Por debajo de este tamaño no se aplica el límite de ratio.

    Un archivo pequeño puede comprimir 1000x sin ser una amenaza —una base SQLite recién
    creada es casi toda ceros—. Una bomba, para hacer daño, tiene que ser grande *y*
    comprimir mucho. Sin este suelo, el lector rechazaría proyectos legítimos.
    """
    max_manifest_bytes: int = 1024**2


DEFAULT_LIMITS = ContainerLimits()


@dataclass(frozen=True, slots=True)
class ContainerManifest:
    """Metadatos del contenedor."""

    format_version: int
    app_version: str
    schema_version: int
    entry_hashes: Mapping[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- escritura


def write_container(
    destination: Path,
    *,
    database: Path,
    assets: Mapping[str, Path],
    app_version: str,
    schema_version: int,
    _before_rename: Callable[[Path], None] | None = None,
    _format_version: int = CONTAINER_FORMAT_VERSION,
) -> None:
    """Guarda el proyecto de forma atómica: temporal, `fsync`, `rename`.

    `_before_rename` es un punto de inyección para los tests: se invoca con la ruta del
    temporal justo antes del renombrado, que es el instante en el que una escritura
    in-place habría dejado el proyecto destruido.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    entradas: dict[str, Path] = {DATABASE_ENTRY: Path(database)}
    for nombre, ruta in assets.items():
        entradas[f"{ASSETS_PREFIX}{nombre}"] = Path(ruta)

    hashes = {nombre: _sha256_de(ruta) for nombre, ruta in entradas.items()}
    manifest = {
        "format": CONTAINER_FORMAT,
        "format_version": _format_version,
        "app_version": app_version,
        "schema_version": schema_version,
        "entry_hashes": hashes,
    }

    temporal = destination.with_name(f".{destination.name}.{uuid4().hex}{_TEMP_SUFFIX}")
    try:
        with open(temporal, "wb") as salida:
            with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zf:
                _escribir_entrada(
                    zf,
                    MANIFEST_NAME,
                    json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
                )
                # Orden estable: dos guardados del mismo contenido deben dar los mismos
                # bytes, y el orden de un dict no es una garantía que convenga heredar.
                for nombre in sorted(entradas):
                    _escribir_entrada(zf, nombre, entradas[nombre].read_bytes())
            salida.flush()
            # El punto crítico: sin este fsync, un corte de energía puede dejar el
            # temporal a medias y el rename lo habría promovido igualmente.
            os.fsync(salida.fileno())

        if _before_rename is not None:
            _before_rename(temporal)

        os.replace(temporal, destination)
        _fsync_directorio(destination.parent)
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise

    _barrer_temporales_abandonados(destination)


def _escribir_entrada(zf: zipfile.ZipFile, nombre: str, datos: bytes) -> None:
    info = zipfile.ZipInfo(nombre, date_time=_FECHA_FIJA)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, datos)


def _sha256_de(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with open(ruta, "rb") as origen:
        while trozo := origen.read(1024 * 1024):
            resumen.update(trozo)
    return resumen.hexdigest()


def _fsync_directorio(directorio: Path) -> None:
    """En POSIX el rename no es duradero hasta que se sincroniza el directorio.

    Windows no expone esta operación y tampoco la necesita: `os.replace` sobre NTFS ya es
    duradero respecto del orden de escrituras.
    """
    if os.name != "posix":
        return
    fd = os.open(directorio, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _barrer_temporales_abandonados(destination: Path) -> None:
    """Limpia temporales de guardados que murieron antes del renombrado.

    Un proceso muerto no puede limpiar tras de sí, así que lo hace el siguiente guardado
    correcto. Solo se tocan los temporales de **este** destino.
    """
    patron = f".{destination.name}.*{_TEMP_SUFFIX}"
    for resto in destination.parent.glob(patron):
        resto.unlink(missing_ok=True)


# ----------------------------------------------------------------------------- lectura


def read_container(
    source: Path,
    destination_dir: Path,
    *,
    limits: ContainerLimits = DEFAULT_LIMITS,
) -> ContainerManifest:
    """Valida y extrae el contenedor bajo `destination_dir`.

    El orden de las comprobaciones no es casual: primero lo que se puede saber sin
    descomprimir nada (magia, listado, nombres, duplicados, número de entradas), después
    el manifest con su techo, y solo al final el contenido, contando bytes a medida que
    salen.
    """
    source = Path(source)
    destination_dir = Path(destination_dir)

    _exigir_magia(source)

    try:
        with zipfile.ZipFile(source) as zf:
            entradas = _entradas_validadas(zf, limits)
            manifest = _leer_manifest(zf, limits)
            destination_dir.mkdir(parents=True, exist_ok=True)
            _extraer(zf, entradas, destination_dir, manifest, limits)
    except zipfile.BadZipFile as error:
        raise CorruptContainerError(
            f"{source} es un contenedor dañado y no se puede leer: {error}"
        ) from error

    return manifest


def _exigir_magia(source: Path) -> None:
    """Rechazo más barato posible: cuatro bytes, sin abrir el ZIP."""
    try:
        with open(source, "rb") as archivo:
            magia = archivo.read(len(_ZIP_MAGIC))
    except OSError as error:
        raise NotAContainerError(f"No se puede leer {source}: {error}") from error

    if magia != _ZIP_MAGIC:
        raise NotAContainerError(
            f"{source} no es un contenedor .wifisurvey: no empieza por la firma de un ZIP."
        )


def _entradas_validadas(
    zf: zipfile.ZipFile, limits: ContainerLimits
) -> tuple[zipfile.ZipInfo, ...]:
    """Comprueba nombres, duplicados, enlaces y número de entradas. Sin descomprimir."""
    infos = [i for i in zf.infolist() if not i.is_dir()]

    if len(infos) > limits.max_entries:
        raise HostileContainerError(
            f"El contenedor declara {len(infos)} entradas y el límite es "
            f"{limits.max_entries}. Un archivo legítimo no las necesita."
        )

    vistos: set[str] = set()
    for info in infos:
        require_safe_entry_name(info.filename)
        if _es_enlace(info):
            raise HostileContainerError(
                f"La entrada {info.filename!r} es un enlace simbólico. Un contenedor de "
                "proyecto solo puede llevar archivos regulares."
            )
        if info.filename in vistos:
            raise HostileContainerError(
                f"La entrada {info.filename!r} está duplicada. Con nombres repetidos, lo "
                "verificado y lo extraído pueden ser cosas distintas."
            )
        vistos.add(info.filename)

    return tuple(infos)


def require_safe_entry_name(nombre: str) -> PurePosixPath:
    """Rechaza cualquier nombre de entrada que pueda escapar del directorio de destino.

    Se valida el nombre **tal cual viene**, sin normalizar antes: normalizar primero es
    justo el error que convierte `a/../../x` en algo de aspecto inocente.

    Público a propósito, para poder testear cada regla en su propio nivel. Una de ellas
    —la de la barra invertida— **no puede dispararse a través de `zipfile`**, porque el
    módulo convierte `\\` en `/` al leer el directorio central del archivo. Se conserva
    igualmente como defensa para cualquier otro origen de nombres, y se comprueba con un
    test directo: una defensa que nadie ejercita es una que nadie sabe si funciona.
    """

    def rechazar(motivo: str) -> None:
        raise HostileContainerError(f"Ruta insegura en el contenedor: {nombre!r} ({motivo}).")

    if not nombre or nombre != nombre.strip():
        rechazar("vacía o con espacios al borde")
    if "\\" in nombre:
        rechazar("usa la barra invertida como separador")
    if any(ord(c) < 32 for c in nombre):
        rechazar("contiene caracteres de control")
    if _UNIDAD_WINDOWS.match(nombre):
        rechazar("lleva letra de unidad de Windows")
    if nombre.startswith("/"):
        rechazar("es una ruta absoluta")

    ruta = PurePosixPath(nombre)
    if ".." in ruta.parts:
        rechazar("sube al directorio padre")

    # Forma canónica. Cubre de una vez `a//b`, `a/./b` y la barra final, en lugar de
    # enumerar casos y dejarse alguno.
    #
    # No es cosmético: `PurePosixPath` colapsa las barras duplicadas, así que `a/b` y
    # `a//b` son cadenas **distintas** —esquivan el control de nombres duplicados— pero
    # designan el **mismo archivo** en disco. Sin esta regla, un contenedor podría
    # declarar dos entradas que se pisan, y la verificada no sería la extraída.
    if ruta.as_posix() != nombre:
        rechazar("no está en forma canónica")

    return ruta


def _es_enlace(info: zipfile.ZipInfo) -> bool:
    # create_system 3 = Unix; los 16 bits altos de external_attr son el modo st_mode.
    return info.create_system == 3 and (info.external_attr >> 16) & 0o170000 == 0o120000


def _leer_manifest(zf: zipfile.ZipFile, limits: ContainerLimits) -> ContainerManifest:
    try:
        info = zf.getinfo(MANIFEST_NAME)
    except KeyError as error:
        raise NotAContainerError(
            "El archivo no lleva manifest.json: no es un contenedor .wifisurvey."
        ) from error

    if info.file_size > limits.max_manifest_bytes:
        raise HostileContainerError(
            f"El manifest declara {info.file_size} bytes y el límite es "
            f"{limits.max_manifest_bytes}."
        )

    with zf.open(info) as origen:
        # +1 para distinguir «justo en el límite» de «se pasó», sin creer al encabezado.
        crudo = origen.read(limits.max_manifest_bytes + 1)
    if len(crudo) > limits.max_manifest_bytes:
        raise HostileContainerError(
            f"El manifest supera el límite de {limits.max_manifest_bytes} bytes al leerlo."
        )

    try:
        datos: Any = json.loads(crudo)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise CorruptContainerError(f"El manifest no es JSON válido: {error}") from error

    if not isinstance(datos, dict):
        raise CorruptContainerError("El manifest no es un objeto JSON.")

    if datos.get("format") != CONTAINER_FORMAT:
        raise NotAContainerError(
            f"El manifest declara el formato {datos.get('format')!r}, que no es "
            f"{CONTAINER_FORMAT!r}. No es un contenedor de OpenZonda."
        )

    version = datos.get("format_version")
    if not isinstance(version, int):
        raise CorruptContainerError("El manifest no declara una versión de formato válida.")
    if version > CONTAINER_FORMAT_VERSION:
        raise ContainerTooNewError(
            f"El contenedor usa la versión de formato {version}, y esta versión de "
            f"OpenZonda entiende hasta la {CONTAINER_FORMAT_VERSION}. Actualiza OpenZonda "
            "para abrirlo."
        )

    hashes = datos.get("entry_hashes", {})
    if not isinstance(hashes, dict):
        raise CorruptContainerError("El manifest declara unos hashes ilegibles.")

    return ContainerManifest(
        format_version=version,
        app_version=str(datos.get("app_version", "")),
        schema_version=int(datos.get("schema_version", 0)),
        entry_hashes=dict(hashes),
    )


def _extraer(
    zf: zipfile.ZipFile,
    entradas: tuple[zipfile.ZipInfo, ...],
    destino: Path,
    manifest: ContainerManifest,
    limits: ContainerLimits,
) -> None:
    raiz = destino.resolve()
    presupuesto = limits.max_total_bytes
    # Una apertura que falla no debe dejar nada detrás. Se anota lo escrito para poder
    # deshacerlo, en vez de borrar el directorio entero: puede ser un espacio de trabajo
    # del llamante con contenido previo que no nos corresponde tocar.
    escritos_en_disco: list[Path] = []

    try:
        for info in entradas:
            objetivo = (raiz / info.filename).resolve()
            # Segunda barrera, después de validar el nombre: comprobar el resultado y no
            # solo la entrada. Si la primera se saltara un caso, esta lo atrapa.
            if not objetivo.is_relative_to(raiz):
                raise HostileContainerError(
                    f"Ruta insegura en el contenedor: {info.filename!r} apunta fuera del "
                    "directorio de destino."
                )

            objetivo.parent.mkdir(parents=True, exist_ok=True)
            escritos_en_disco.append(objetivo)
            escritos = _extraer_entrada(zf, info, objetivo, presupuesto, limits)
            presupuesto -= escritos

            esperado = manifest.entry_hashes.get(info.filename)
            if esperado is not None and _sha256_de(objetivo) != esperado:
                raise CorruptContainerError(
                    f"La entrada {info.filename!r} no coincide con el hash declarado en "
                    "el manifest: el contenedor está dañado o fue manipulado."
                )
    except BaseException:
        for parcial in escritos_en_disco:
            parcial.unlink(missing_ok=True)
        raise


def _extraer_entrada(
    zf: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    objetivo: Path,
    presupuesto: int,
    limits: ContainerLimits,
) -> int:
    """Extrae contando los bytes reales. Devuelve cuántos se escribieron.

    Se aborta **durante** la lectura, no después: llegar al final para entonces decir que
    era demasiado grande ya habría llenado el disco, que es exactamente lo que busca una
    bomba.
    """
    escritos = 0
    try:
        with zf.open(info) as origen, open(objetivo, "wb") as salida:
            while trozo := origen.read(64 * 1024):
                escritos += len(trozo)
                if escritos > limits.max_entry_bytes:
                    raise HostileContainerError(
                        f"La entrada {info.filename!r} supera el tamaño máximo de "
                        f"{limits.max_entry_bytes} bytes."
                    )
                if escritos > presupuesto:
                    raise HostileContainerError(
                        f"El contenido descomprimido supera el tamaño total permitido de "
                        f"{limits.max_total_bytes} bytes."
                    )
                if (
                    escritos > limits.ratio_floor_bytes
                    and info.compress_size > 0
                    and escritos / info.compress_size > limits.max_compression_ratio
                ):
                    raise HostileContainerError(
                        f"La entrada {info.filename!r} se expande más de "
                        f"{limits.max_compression_ratio:.0f} veces: ratio de compresión "
                        "propio de una bomba."
                    )
                salida.write(trozo)
    except BaseException:
        # No dejar a medias lo que se estaba escribiendo: abortar una bomba no debe
        # costar el disco igualmente.
        objetivo.unlink(missing_ok=True)
        raise

    return escritos

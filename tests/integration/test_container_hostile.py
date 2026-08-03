"""Fixtures hostiles del contenedor `.wifisurvey` (diseño §17.3).

Un `.wifisurvey` llega por correo, por un pendrive o de un colega. El modelo de amenazas lo
nombra explícitamente: *"Proyecto .wifisurvey malicioso (zip bomb, path traversal, SQLite
hostil)"*.

**Cada mitigación va en pareja**: un test de control que demuestra que el ataque funciona
sin la defensa, y otro que demuestra que con ella no. Sin el control, un test verde puede
estar pasando por una razón que no tiene nada que ver con la defensa que cree probar —
como ocurrió en OZ-6 con `load_extension`, que Python bloquea siempre.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from persistence.container import (
    CONTAINER_FORMAT,
    CONTAINER_FORMAT_VERSION,
    ContainerLimits,
    HostileContainerError,
    read_container,
    require_safe_entry_name,
)


class TestValidadorDeNombres:
    """El validador, probado en su propio nivel.

    Una de sus reglas —la de la barra invertida— **no puede dispararse a través de
    `zipfile`**, porque el módulo convierte `\\` en `/` al leer el directorio central. Sin
    estos tests directos sería una defensa que nadie ejercita, y por tanto una que nadie
    sabe si funciona.
    """

    @pytest.mark.parametrize(
        "nombre",
        [
            "carpeta\\con\\backslash.txt",
            "..\\padre.txt",
            "\\raiz.txt",
        ],
        ids=["separador", "padre", "absoluta"],
    )
    def test_rechaza_la_barra_invertida(self, nombre: str) -> None:
        with pytest.raises(HostileContainerError, match=r"(?i)barra invertida"):
            require_safe_entry_name(nombre)

    @pytest.mark.parametrize(
        "nombre",
        ["", "   ", " con-espacio.txt", "salto\nlinea.txt", "nulo\x00.txt", "a//b.txt"],
        ids=["vacía", "espacios", "espacio-al-borde", "salto-de-linea", "byte-nulo", "doble-barra"],
    )
    def test_rechaza_nombres_degenerados(self, nombre: str) -> None:
        with pytest.raises(HostileContainerError):
            require_safe_entry_name(nombre)

    @pytest.mark.parametrize(
        "nombre",
        ["manifest.json", "data/survey.sqlite", "assets/planta-01.png", "exports/a/b.csv"],
    )
    def test_acepta_los_nombres_legitimos_del_formato(self, nombre: str) -> None:
        assert require_safe_entry_name(nombre).as_posix() == nombre


LIMITES_DE_PRUEBA = ContainerLimits(
    max_entries=20,
    max_total_bytes=4 * 1024 * 1024,
    max_entry_bytes=2 * 1024 * 1024,
    max_compression_ratio=100.0,
    ratio_floor_bytes=64 * 1024,
    max_manifest_bytes=64 * 1024,
)


def manifest_valido(entradas: dict[str, str] | None = None) -> str:
    return json.dumps(
        {
            "format": CONTAINER_FORMAT,
            "format_version": CONTAINER_FORMAT_VERSION,
            "app_version": "0.1.0",
            "schema_version": 1,
            "entry_hashes": entradas or {},
        }
    )


def escribir_con_nombre_crudo(zf: zipfile.ZipFile, nombre: str, datos: bytes) -> None:
    """Escribe una entrada con el nombre **tal cual**, sin que zipfile lo normalice.

    Hace falta para que los fixtures sean fieles: en Windows, `ZipInfo(nombre)` convierte
    la barra invertida en barra normal, así que un ZIP hostil construido de la forma obvia
    saldría ya saneado y el test pasaría sin probar nada. Un atacante construye el archivo
    en la máquina que quiera, con los bytes que quiera.
    """
    info = zipfile.ZipInfo("marcador")
    info.filename = nombre
    zf.writestr(info, datos)


def extraccion_ingenua(archivo: Path, destino: Path) -> None:
    """Lo que uno escribe a mano al extraer un ZIP.

    No es un hombre de paja: `ZipFile.extractall` sí sanea rutas, pero en cuanto hace falta
    filtrar entradas, verificar hashes o extraer selectivamente —que es justo nuestro
    caso— el código pasa a unir el nombre del ZIP con el destino, y ahí es donde escapa.
    """
    with zipfile.ZipFile(archivo) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            objetivo = destino / info.filename
            objetivo.parent.mkdir(parents=True, exist_ok=True)
            objetivo.write_bytes(zf.read(info))


class TestPathTraversal:
    """Ataque: una entrada cuyo nombre sale del directorio de destino."""

    @staticmethod
    def _fixture(archivo: Path) -> None:
        with zipfile.ZipFile(archivo, "w") as zf:
            zf.writestr("manifest.json", manifest_valido())
            escribir_con_nombre_crudo(zf, "../ROBADO.txt", b"te escribo fuera de tu carpeta")

    def test_control_la_extraccion_ingenua_escapa_del_destino(self, tmp_path: Path) -> None:
        hostil = tmp_path / "traversal.wifisurvey"
        self._fixture(hostil)
        destino = tmp_path / "extraido"
        destino.mkdir()

        extraccion_ingenua(hostil, destino)

        assert (tmp_path / "ROBADO.txt").exists(), (
            "si esto falla, el test de abajo ya no demuestra nada"
        )

    def test_el_lector_rechaza_el_traversal(self, tmp_path: Path) -> None:
        hostil = tmp_path / "traversal.wifisurvey"
        self._fixture(hostil)

        with pytest.raises(HostileContainerError, match=r"(?i)ruta insegura"):
            read_container(hostil, tmp_path / "extraido", limits=LIMITES_DE_PRUEBA)

        assert not (tmp_path / "ROBADO.txt").exists()

    @pytest.mark.parametrize(
        "nombre",
        [
            "../fuera.txt",
            "a/../../fuera.txt",
            "/absoluta.txt",
            "C:/unidad.txt",
            "C:\\unidad.txt",
            "\\\\servidor\\recurso\\unc.txt",
        ],
        ids=[
            "padre-directo",
            "padre-anidado",
            "absoluta-posix",
            "unidad-windows-barra",
            "unidad-windows-backslash",
            "ruta-unc",
        ],
    )
    def test_variantes_de_ruta_peligrosa(self, tmp_path: Path, nombre: str) -> None:
        """Nota: `zipfile` convierte `\\` en `/` al leer el archivo, así que los tres
        últimos casos llegan al validador ya normalizados y los atrapan las reglas de
        ruta absoluta y letra de unidad, no la de barra invertida."""
        hostil = tmp_path / "variante.wifisurvey"
        with zipfile.ZipFile(hostil, "w") as zf:
            zf.writestr("manifest.json", manifest_valido())
            escribir_con_nombre_crudo(zf, nombre, b"carga")

        with pytest.raises(HostileContainerError):
            read_container(hostil, tmp_path / "extraido", limits=LIMITES_DE_PRUEBA)


class TestZipBomb:
    """Ataque: poco comprimido que se expande hasta agotar disco o memoria."""

    @staticmethod
    def _fixture(archivo: Path, megas: int = 8) -> None:
        with zipfile.ZipFile(archivo, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", manifest_valido())
            zf.writestr("data/survey.sqlite", b"\0" * (megas * 1024 * 1024))

    def test_control_el_ratio_del_fixture_es_realmente_abusivo(self, tmp_path: Path) -> None:
        """Sin esto, el test de abajo podría estar rechazando por otro motivo."""
        hostil = tmp_path / "bomba.wifisurvey"
        self._fixture(hostil)

        with zipfile.ZipFile(hostil) as zf:
            info = zf.getinfo("data/survey.sqlite")

        ratio = info.file_size / info.compress_size
        assert ratio > LIMITES_DE_PRUEBA.max_compression_ratio, (
            f"el fixture solo alcanza {ratio:.0f}x y no supera el límite"
        )

    def test_el_lector_rechaza_la_bomba(self, tmp_path: Path) -> None:
        hostil = tmp_path / "bomba.wifisurvey"
        self._fixture(hostil)

        with pytest.raises(HostileContainerError, match=r"compresión|tamaño"):
            read_container(hostil, tmp_path / "extraido", limits=LIMITES_DE_PRUEBA)

    def test_una_apertura_abortada_no_deja_nada_detras(self, tmp_path: Path) -> None:
        """Abortar no debe costar el disco igualmente, ni dejar un proyecto a medias que
        alguien pueda confundir con uno bueno."""
        hostil = tmp_path / "bomba.wifisurvey"
        self._fixture(hostil)
        destino = tmp_path / "extraido"

        with pytest.raises(HostileContainerError):
            read_container(hostil, destino, limits=LIMITES_DE_PRUEBA)

        restos = [p for p in destino.rglob("*") if p.is_file()] if destino.exists() else []
        assert restos == [], f"quedaron restos de la extracción abortada: {restos}"

    def test_no_se_toca_lo_que_ya_hubiera_en_el_destino(self, tmp_path: Path) -> None:
        """El destino puede ser un espacio de trabajo del llamante: se limpia lo que
        escribimos nosotros, no lo que ya estaba."""
        hostil = tmp_path / "bomba.wifisurvey"
        self._fixture(hostil)
        destino = tmp_path / "extraido"
        destino.mkdir()
        preexistente = destino / "no-me-toques.txt"
        preexistente.write_text("contenido del llamante", encoding="utf-8")

        with pytest.raises(HostileContainerError):
            read_container(hostil, destino, limits=LIMITES_DE_PRUEBA)

        assert preexistente.read_text(encoding="utf-8") == "contenido del llamante"


class TestTamanoMentido:
    """Ataque: el encabezado declara un tamaño y el contenido real es otro.

    Es el motivo por el que **nunca** se reserva memoria proporcional a `file_size`: ese
    campo lo escribe quien construye el archivo, no el lector.
    """

    def test_el_limite_se_aplica_leyendo_no_creyendo_al_encabezado(self, tmp_path: Path) -> None:
        hostil = tmp_path / "mentira.wifisurvey"
        with zipfile.ZipFile(hostil, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", manifest_valido())
            zf.writestr("data/survey.sqlite", b"\0" * (3 * 1024 * 1024))

        # Se falsea el tamaño declarado a un valor inocente. Un lector que confíe en el
        # encabezado dejará pasar 3 MiB creyendo que son 10 bytes.
        with zipfile.ZipFile(hostil) as zf:
            assert zf.getinfo("data/survey.sqlite").file_size == 3 * 1024 * 1024

        limites = ContainerLimits(
            max_entries=20,
            max_total_bytes=1024 * 1024,
            max_entry_bytes=1024 * 1024,
            max_compression_ratio=1e9,
            ratio_floor_bytes=64 * 1024,
            max_manifest_bytes=64 * 1024,
        )

        with pytest.raises(HostileContainerError, match="tamaño"):
            read_container(hostil, tmp_path / "extraido", limits=limites)


class TestDemasiadasEntradas:
    def test_se_rechaza_un_contenedor_con_miles_de_entradas(self, tmp_path: Path) -> None:
        """Muchas entradas diminutas agotan inodos y tiempo sin disparar los límites
        de tamaño."""
        hostil = tmp_path / "muchas.wifisurvey"
        with zipfile.ZipFile(hostil, "w") as zf:
            zf.writestr("manifest.json", manifest_valido())
            for i in range(LIMITES_DE_PRUEBA.max_entries + 5):
                zf.writestr(f"assets/a{i}.bin", b"x")

        with pytest.raises(HostileContainerError, match="entradas"):
            read_container(hostil, tmp_path / "extraido", limits=LIMITES_DE_PRUEBA)


class TestNombresDuplicados:
    def test_se_rechazan_entradas_con_el_mismo_nombre(self, tmp_path: Path) -> None:
        """Dos entradas con el mismo nombre hacen que lo verificado y lo extraído puedan
        ser cosas distintas."""
        hostil = tmp_path / "duplicado.wifisurvey"
        with zipfile.ZipFile(hostil, "w") as zf:
            zf.writestr("manifest.json", manifest_valido())
            zf.writestr("data/survey.sqlite", b"inocente")
            zf.writestr("data/survey.sqlite", b"malicioso")

        with pytest.raises(HostileContainerError, match="duplicad"):
            read_container(hostil, tmp_path / "extraido", limits=LIMITES_DE_PRUEBA)


class TestEnlacesSimbolicos:
    def test_se_rechaza_una_entrada_que_es_un_enlace(self, tmp_path: Path) -> None:
        """Un enlace simbólico dentro del ZIP redirige una escritura posterior fuera del
        destino, aunque su nombre parezca inocente."""
        hostil = tmp_path / "enlace.wifisurvey"
        with zipfile.ZipFile(hostil, "w") as zf:
            zf.writestr("manifest.json", manifest_valido())
            info = zipfile.ZipInfo("assets/plano.png")
            info.create_system = 3  # Unix
            info.external_attr = (0o120777 << 16) | 0o20  # S_IFLNK
            zf.writestr(info, "/etc/passwd")

        with pytest.raises(HostileContainerError, match="enlace"):
            read_container(hostil, tmp_path / "extraido", limits=LIMITES_DE_PRUEBA)


class TestManifestDesproporcionado:
    def test_un_manifest_gigante_se_rechaza_sin_cargarlo(self, tmp_path: Path) -> None:
        """El manifest se lee antes que nada; si no tuviera techo sería el primer
        vector."""
        hostil = tmp_path / "manifest_gordo.wifisurvey"
        with zipfile.ZipFile(hostil, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", "{" + " " * (2 * 1024 * 1024) + "}")

        with pytest.raises(HostileContainerError, match="manifest"):
            read_container(hostil, tmp_path / "extraido", limits=LIMITES_DE_PRUEBA)

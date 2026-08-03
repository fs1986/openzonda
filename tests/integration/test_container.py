"""Contenedor `.wifisurvey`: round-trip, escritura atómica y taxonomía de errores.

Formato (diseño §14.1, ADR-004): ZIP con `manifest.json`, `data/survey.sqlite` y
`assets/`. Autocontenido y trasladable; nunca rutas absolutas.

Un `.wifisurvey` contiene trabajo de campo **irrepetible**: horas caminando un edificio
con un portátil. De ahí las dos exigencias que dominan estos tests — que guardar no pueda
destruir lo anterior, y que abrir un archivo ajeno no pueda hacer daño.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from persistence.container import (
    CONTAINER_FORMAT_VERSION,
    ContainerTooNewError,
    CorruptContainerError,
    NotAContainerError,
    read_container,
    write_container,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def fuentes(tmp_path: Path) -> dict[str, Path]:
    """Los archivos que componen un proyecto: la base y un plano."""
    origen = tmp_path / "origen"
    origen.mkdir()
    base = origen / "survey.sqlite"
    base.write_bytes(b"SQLite format 3\x00" + b"contenido de la base" * 500)
    plano = origen / "planta-baja.png"
    plano.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 40)
    return {"database": base, "asset": plano}


def guardar(destino: Path, fuentes: dict[str, Path]) -> None:
    write_container(
        destino,
        database=fuentes["database"],
        assets={"planta-baja.png": fuentes["asset"]},
        app_version="0.1.0",
        schema_version=1,
    )


class TestRoundTrip:
    def test_la_base_vuelve_identica_por_hash(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        """DoD: round-trip idéntico por hash."""
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)
        extraido = tmp_path / "extraido"

        read_container(contenedor, extraido)

        assert sha256(extraido / "data" / "survey.sqlite") == sha256(fuentes["database"])

    def test_los_assets_vuelven_identicos_por_hash(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)
        extraido = tmp_path / "extraido"

        read_container(contenedor, extraido)

        assert sha256(extraido / "assets" / "planta-baja.png") == sha256(fuentes["asset"])

    def test_el_manifest_declara_los_hashes(self, tmp_path: Path, fuentes: dict[str, Path]) -> None:
        """El diseño §14.1 los exige: son lo que permite detectar manipulación."""
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)

        manifest = read_container(contenedor, tmp_path / "extraido")

        assert manifest.entry_hashes["data/survey.sqlite"] == sha256(fuentes["database"])
        assert manifest.entry_hashes["assets/planta-baja.png"] == sha256(fuentes["asset"])

    def test_el_manifest_conserva_las_versiones(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)

        manifest = read_container(contenedor, tmp_path / "extraido")

        assert manifest.app_version == "0.1.0"
        assert manifest.schema_version == 1
        assert manifest.format_version == CONTAINER_FORMAT_VERSION

    def test_no_se_extrae_nada_fuera_del_destino(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)
        extraido = tmp_path / "extraido"

        read_container(contenedor, extraido)

        escritos = {p.relative_to(extraido).as_posix() for p in extraido.rglob("*") if p.is_file()}
        assert escritos == {
            "manifest.json",
            "data/survey.sqlite",
            "assets/planta-baja.png",
        }


class TestDeterminismo:
    def test_guardar_dos_veces_el_mismo_contenido_da_bytes_identicos(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        """Sin esto, cada guardado produciría un archivo distinto aunque nada cambiara:
        las copias de seguridad incrementales y los diffs dejarían de servir."""
        uno, dos = tmp_path / "uno.wifisurvey", tmp_path / "dos.wifisurvey"
        guardar(uno, fuentes)
        guardar(dos, fuentes)

        assert sha256(uno) == sha256(dos)


class TestEscrituraAtomica:
    def test_sobrescribir_deja_el_contenido_nuevo(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)
        fuentes["database"].write_bytes(b"SQLite format 3\x00" + b"version dos" * 500)

        guardar(contenedor, fuentes)

        read_container(contenedor, tmp_path / "extraido")
        assert sha256(tmp_path / "extraido" / "data" / "survey.sqlite") == sha256(
            fuentes["database"]
        )

    def test_un_fallo_antes_del_rename_no_toca_el_original(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        """El punto exacto donde una escritura in-place destruiría el proyecto."""
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)
        hash_original = sha256(contenedor)
        fuentes["database"].write_bytes(b"SQLite format 3\x00" + b"version dos" * 500)

        def reventar(_temporal: Path) -> None:
            raise OSError("disco lleno justo antes del rename")

        with pytest.raises(OSError, match="disco lleno"):
            write_container(
                contenedor,
                database=fuentes["database"],
                assets={"planta-baja.png": fuentes["asset"]},
                app_version="0.2.0",
                schema_version=1,
                _before_rename=reventar,
            )

        assert sha256(contenedor) == hash_original, "el proyecto anterior se perdió"

    def test_no_deja_temporales_tras_un_guardado_correcto(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        contenedor = tmp_path / "proyecto.wifisurvey"

        guardar(contenedor, fuentes)

        assert [p.name for p in tmp_path.iterdir() if p.is_file()] == ["proyecto.wifisurvey"]


class TestKillTest:
    """DoD: kill-test sin corrupción.

    Se mata el proceso con `os._exit`, que termina de inmediato sin ejecutar `finally`,
    ni `atexit`, ni vaciar buffers de Python. Es lo más cercano a un `kill -9` que se
    puede provocar de forma determinista, y ataca el instante peor: entre el `fsync` del
    temporal y el `rename`.

    Salvedad honesta: no simula un corte de energía, donde además se perderían las
    escrituras que el sistema operativo aún no ha bajado a disco. De eso protege el
    `fsync`, no este test.
    """

    def test_matar_el_proceso_antes_del_rename_conserva_el_proyecto(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)
        hash_original = sha256(contenedor)

        nueva_base = tmp_path / "nueva.sqlite"
        nueva_base.write_bytes(b"SQLite format 3\x00" + b"contenido nuevo" * 500)

        script = tmp_path / "suicida.py"
        script.write_text(
            "import os, sys\n"
            "from pathlib import Path\n"
            "from persistence.container import write_container\n"
            "write_container(\n"
            "    Path(sys.argv[1]),\n"
            "    database=Path(sys.argv[2]),\n"
            "    assets={},\n"
            "    app_version='9.9.9',\n"
            "    schema_version=1,\n"
            "    _before_rename=lambda _t: os._exit(137),\n"
            ")\n",
            encoding="utf-8",
        )

        resultado = subprocess.run(
            [sys.executable, str(script), str(contenedor), str(nueva_base)],
            capture_output=True,
            check=False,
        )

        assert resultado.returncode == 137, "el proceso debía morir antes del rename"
        assert sha256(contenedor) == hash_original, (
            "matar el proceso durante el guardado destruyó el proyecto anterior"
        )
        # El contenedor sigue siendo legible y con el contenido viejo, no una mezcla.
        manifest = read_container(contenedor, tmp_path / "tras_muerte")
        assert manifest.app_version == "0.1.0"

    def test_el_temporal_huerfano_no_impide_reabrir_ni_reguardar(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        """Un proceso muerto no puede limpiar tras de sí; el resto debe tolerarlo."""
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)
        huerfano = tmp_path / ".proyecto.wifisurvey.abandonado.tmp"
        huerfano.write_bytes(b"restos de un guardado que murio")

        read_container(contenedor, tmp_path / "extraido")
        guardar(contenedor, fuentes)

        assert not huerfano.exists(), (
            "un guardado correcto debería barrer los temporales abandonados"
        )


class TestTaxonomiaDeErrores:
    """Cada fallo dice **qué** pasó. No es lo mismo un archivo ajeno que uno corrupto
    que uno de una versión futura: la acción del usuario es distinta en cada caso."""

    def test_un_archivo_que_no_es_zip(self, tmp_path: Path) -> None:
        falso = tmp_path / "falso.wifisurvey"
        falso.write_bytes(b"esto no es un contenedor" * 50)

        with pytest.raises(NotAContainerError, match="no es un contenedor"):
            read_container(falso, tmp_path / "extraido")

    def test_un_zip_cualquiera_sin_manifest(self, tmp_path: Path) -> None:
        ajeno = tmp_path / "ajeno.wifisurvey"
        with zipfile.ZipFile(ajeno, "w") as zf:
            zf.writestr("cualquier.txt", "contenido")

        with pytest.raises(NotAContainerError, match="manifest"):
            read_container(ajeno, tmp_path / "extraido")

    def test_un_contenedor_de_version_futura(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        futuro = tmp_path / "futuro.wifisurvey"
        write_container(
            futuro,
            database=fuentes["database"],
            assets={},
            app_version="99.0.0",
            schema_version=1,
            _format_version=CONTAINER_FORMAT_VERSION + 1,
        )

        with pytest.raises(ContainerTooNewError) as error:
            read_container(futuro, tmp_path / "extraido")

        mensaje = str(error.value)
        assert str(CONTAINER_FORMAT_VERSION + 1) in mensaje
        assert str(CONTAINER_FORMAT_VERSION) in mensaje

    def test_un_contenedor_truncado(self, tmp_path: Path, fuentes: dict[str, Path]) -> None:
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)
        crudo = contenedor.read_bytes()
        contenedor.write_bytes(crudo[: len(crudo) // 2])

        with pytest.raises((CorruptContainerError, NotAContainerError)):
            read_container(contenedor, tmp_path / "extraido")

    def test_un_contenido_manipulado_no_cuadra_con_su_hash(
        self, tmp_path: Path, fuentes: dict[str, Path]
    ) -> None:
        """Los hashes del manifest no son decoración: detectan manipulación."""
        contenedor = tmp_path / "proyecto.wifisurvey"
        guardar(contenedor, fuentes)

        manipulado = tmp_path / "manipulado.wifisurvey"
        with zipfile.ZipFile(contenedor) as origen, zipfile.ZipFile(manipulado, "w") as salida:
            for info in origen.infolist():
                datos = origen.read(info.filename)
                if info.filename == "data/survey.sqlite":
                    datos = b"SQLite format 3\x00" + b"CONTENIDO SUSTITUIDO" * 500
                salida.writestr(info.filename, datos)

        with pytest.raises(CorruptContainerError, match=r"hash|integridad"):
            read_container(manipulado, tmp_path / "extraido")

    def test_un_manifest_que_no_es_json(self, tmp_path: Path) -> None:
        roto = tmp_path / "roto.wifisurvey"
        with zipfile.ZipFile(roto, "w") as zf:
            zf.writestr("manifest.json", "{esto no es json")

        with pytest.raises(CorruptContainerError):
            read_container(roto, tmp_path / "extraido")

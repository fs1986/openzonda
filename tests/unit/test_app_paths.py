"""Resolución de rutas de aplicación y detección de modo portable (diseño §18).

El diseño fija dos modos excluyentes:

- **Instalado**: settings en `%APPDATA%\\OpenZonda\\`, logs y caché en
  `%LOCALAPPDATA%\\OpenZonda\\`.
- **Portable**: detectado por un archivo `portable.marker` junto al ejecutable; en ese
  modo config y logs viven junto a la app y no se toca el perfil del usuario.

Confundir los dos modos es un fallo con consecuencias: un portable que escribe en
`%APPDATA%` deja rastro en una máquina ajena, que es justo lo que un usuario elige portable
para evitar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from persistence.app_paths import PORTABLE_MARKER, resolve_app_paths


@pytest.fixture
def perfil(tmp_path: Path) -> dict[str, str]:
    """Perfil de usuario simulado.

    Se construye desde `tmp_path` en vez de literales `C:\\...` porque en Linux —donde
    también corre CI— una ruta con letra de unidad no es absoluta y las aserciones
    pasarían por la razón equivocada.
    """
    return {
        "APPDATA": str(tmp_path / "perfil" / "Roaming"),
        "LOCALAPPDATA": str(tmp_path / "perfil" / "Local"),
    }


def test_sin_marker_usa_el_perfil_del_usuario(tmp_path: Path, perfil: dict[str, str]) -> None:
    paths = resolve_app_paths(app_dir=tmp_path, env=perfil)

    assert paths.portable is False
    assert paths.settings_file.parts[-2:] == ("OpenZonda", "settings.json")
    assert "Roaming" in str(paths.settings_file)
    assert paths.logs_dir.parts[-2:] == ("OpenZonda", "logs")
    assert paths.cache_dir.parts[-2:] == ("OpenZonda", "cache")


def test_con_marker_todo_vive_junto_al_ejecutable(tmp_path: Path, perfil: dict[str, str]) -> None:
    (tmp_path / PORTABLE_MARKER).touch()

    paths = resolve_app_paths(app_dir=tmp_path, env=perfil)

    assert paths.portable is True
    assert paths.settings_file == tmp_path / "settings.json"
    assert paths.logs_dir == tmp_path / "logs"
    assert paths.cache_dir == tmp_path / "cache"


def test_el_modo_portable_no_escribe_en_el_perfil_del_usuario(
    tmp_path: Path, perfil: dict[str, str]
) -> None:
    """Invariante del modo portable: ninguna ruta cae fuera de la carpeta de la app."""
    (tmp_path / PORTABLE_MARKER).touch()

    paths = resolve_app_paths(app_dir=tmp_path, env=perfil)

    for ruta in (paths.settings_file, paths.logs_dir, paths.cache_dir):
        assert ruta.is_relative_to(tmp_path), f"{ruta} escapa de la carpeta portable"


def test_sin_variables_de_windows_cae_a_rutas_del_home(tmp_path: Path) -> None:
    """En Linux (CI) no existen APPDATA/LOCALAPPDATA; no debe reventar."""
    paths = resolve_app_paths(app_dir=tmp_path, env={"HOME": str(tmp_path / "home")})

    assert paths.portable is False
    assert paths.settings_file.is_relative_to(tmp_path / "home")


def test_las_rutas_son_absolutas(tmp_path: Path, perfil: dict[str, str]) -> None:
    paths = resolve_app_paths(app_dir=tmp_path, env=perfil)

    assert paths.settings_file.is_absolute()
    assert paths.logs_dir.is_absolute()
    assert paths.cache_dir.is_absolute()


def test_appaths_es_inmutable(tmp_path: Path, perfil: dict[str, str]) -> None:
    paths = resolve_app_paths(app_dir=tmp_path, env=perfil)

    with pytest.raises(AttributeError):
        paths.portable = True  # type: ignore[misc]

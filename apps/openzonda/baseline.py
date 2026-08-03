"""Guard de baseline de Windows: rechaza arrancar por debajo del build soportado (OZ-33).

## Por qué existe y por qué aquí

El baseline mínimo lo fija ADR-001 (Windows 10 22H2 = build 19045). Ese requisito ya se
comprobaba en el **preflight del instalador** (diseño §18), que es su sitio natural. Pero
la comprobación del MSI usaba la propiedad `WindowsBuild`, que en Windows 10/11 queda
**congelada en 9600** (valor de Win 8.1) porque `msiexec.exe` no declara Windows 10 en su
manifiesto y MSI deriva esa propiedad del `GetVersionEx` compatibilizado. Consecuencia:
`9600 >= 19045` es falso y **toda** instalación limpia en Windows moderno se rechazaba
(build 26200 incluido). Ver OZ-33.

Este módulo añade el guard equivalente **en runtime**, leyendo el build por una vía que no
miente (registro `CurrentBuildNumber`, con RtlGetVersion de respaldo). Dos motivos:

1. Previene la *clase* de bug, no solo la instancia: cualquiera que sea la vía por la que
   se detecte la versión, aquí se lee la verdad y se compara como **entero**.
2. El modo portable (diseño §18) no pasa por el instalador, así que sin este guard no
   tendría ninguna comprobación de baseline.

## Relación con ADR-001

ADR-001 prohíbe *gatear capacidades por número de versión* ("toda API se comprueba por
disponibilidad en runtime"). Esto no es eso: es una **aserción de piso** única y fail-closed
que se limita a negarse a arrancar por debajo del SO soportado, sin ramificar ninguna
funcionalidad por versión. La distinción y su encaje con ADR-001 quedan en ADR-009.

Vive en `apps/openzonda` (composition root) porque es el único paquete autorizado a tocar
APIs de Windows (`winreg`/`ctypes`); la UI nunca las importa (contrato de capas, ADR-003).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

# Umbral de ADR-001: Windows 10 22H2. NO se toca sin un ADR nuevo (decisión inmutable).
SUPPORTED_WINDOWS_BUILD = 19045

# Mismo texto que la LaunchCondition del MSI, para que el usuario vea un mensaje coherente
# venga el rechazo del instalador o del arranque.
BASELINE_MESSAGE = "OpenZonda requiere Windows 10 22H2 (build 19045) o superior. Consulta ADR-001."

_log = logging.getLogger("openzonda")


def is_supported_build(build: int) -> bool:
    """True si `build` cumple el baseline. Comparación por entero, nunca por string.

    Pura y sin dependencias de SO: el mismo contrato se verifica en CI (Linux) y en Windows.
    """
    return build >= SUPPORTED_WINDOWS_BUILD


def _build_from_registry() -> int | None:
    """Lee `HKLM\\...\\CurrentVersion\\CurrentBuildNumber`. La fuente que no miente.

    Es un `REG_SZ` con el build base (p. ej. "26100"), presente en todo Windows. Devuelve
    None si no se puede leer o el valor no es numérico, para que el llamador decida.
    """
    try:
        import winreg
    except ImportError:  # no es Windows (CI en Linux): no aplica
        return None

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        ) as key:
            crudo, _tipo = winreg.QueryValueEx(key, "CurrentBuildNumber")
    except OSError:
        return None

    try:
        return int(str(crudo).strip())
    except (TypeError, ValueError):
        return None


def _build_from_rtlgetversion() -> int | None:
    """Respaldo vía `ntdll.RtlGetVersion`, que —a diferencia de GetVersionEx— no está
    sujeta al shim de compatibilidad por manifiesto. Solo se usa si el registro falla."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:  # pragma: no cover - ctypes está en la stdlib de Windows
        return None

    class _RTL_OSVERSIONINFOW(ctypes.Structure):
        _fields_ = [
            ("dwOSVersionInfoSize", wintypes.DWORD),
            ("dwMajorVersion", wintypes.DWORD),
            ("dwMinorVersion", wintypes.DWORD),
            ("dwBuildNumber", wintypes.DWORD),
            ("dwPlatformId", wintypes.DWORD),
            ("szCSDVersion", wintypes.WCHAR * 128),
        ]

    info = _RTL_OSVERSIONINFOW()
    info.dwOSVersionInfoSize = ctypes.sizeof(info)
    try:
        status = ctypes.windll.ntdll.RtlGetVersion(ctypes.byref(info))
    except (OSError, AttributeError):  # pragma: no cover - defensivo
        return None
    if status != 0:  # pragma: no cover - RtlGetVersion no falla en la práctica
        return None
    return int(info.dwBuildNumber)


def detect_windows_build() -> int | None:
    """Build real de Windows, o None si no se puede determinar (p. ej. fuera de Windows).

    Prefiere el registro; si no, RtlGetVersion. Ninguna de las dos pasa por el
    `GetVersionEx` compatibilizado que causó OZ-33.
    """
    return _build_from_registry() or _build_from_rtlgetversion()


def _show_error_dialog(message: str) -> None:  # pragma: no cover - requiere GUI de Windows
    """Muestra el mensaje en un cuadro nativo, sin depender de Qt (aún no está arrancado).

    Se usa `user32.MessageBoxW` directamente porque el guard corre antes de crear la
    `QApplication`; además mantiene la dependencia de Windows fuera de la capa de UI.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        MB_OK = 0x0
        MB_ICONERROR = 0x10
        ctypes.windll.user32.MessageBoxW(0, message, "OpenZonda", MB_OK | MB_ICONERROR)
    except (OSError, AttributeError):
        return


def enforce_baseline(
    logger: logging.Logger | None = None,
    *,
    detect: Callable[[], int | None] = detect_windows_build,
    show_error: Callable[[str], None] = _show_error_dialog,
) -> bool:
    """Aplica el guard de baseline. Devuelve True si la app puede arrancar.

    Siempre registra el valor crudo detectado (criterio de aceptación de OZ-33). Si el
    build no llega al mínimo, avisa al usuario y devuelve False. Si no se puede determinar
    (registro ilegible, no-Windows), **no** bloquea: repetir el bug de OZ-33 —rechazar un
    sistema válido— es peor que arrancar en uno que quizá no cumpla.

    `detect` y `show_error` se inyectan para poder verificar el contrato sin depender del
    SO donde corren los tests.
    """
    log = logger or _log
    build = detect()
    log.info(
        "Baseline Windows: build detectado=%r (mínimo soportado=%d, ADR-001)",
        build,
        SUPPORTED_WINDOWS_BUILD,
    )

    if build is None:
        log.warning("Baseline Windows: build indeterminado; se continúa sin bloquear (fail-open)")
        return True

    if is_supported_build(build):
        return True

    log.error(
        "Baseline Windows: build %d por debajo del mínimo %d; no soportado (ADR-001)",
        build,
        SUPPORTED_WINDOWS_BUILD,
    )
    show_error(BASELINE_MESSAGE)
    return False

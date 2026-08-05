"""Resolución del idioma efectivo de la UI (OZ-35, ADR-013).

El ajuste `AppSettings.language` es una *preferencia*: `"system"` (seguir el SO) o un override
explícito `"es"`/`"en"`. El idioma **efectivo** —el que decide qué catálogo `.qm` cargar— sale
de combinar esa preferencia con el locale del sistema. Esta función es pura: la detección del
locale (Qt / `locale`) la hace el composition root y le pasa el código ya leído, así la regla
se prueba headless.
"""

from __future__ import annotations

from application.settings import LANGUAGE_SYSTEM, SUPPORTED_LANGUAGES

FALLBACK_LANGUAGE = "en"
"""Idioma cuando el locale del sistema no es uno soportado. Inglés como lengua franca: un
usuario con el SO en, p. ej., francés, entiende antes el inglés que el español de origen."""


def resolve_language(setting: str, system_language: str | None) -> str:
    """Idioma efectivo (`"es"` o `"en"`) a partir de la preferencia y el locale del SO.

    - `"es"`/`"en"`: override explícito, se respeta tal cual.
    - `"system"` (u otro valor): se sigue el locale del SO —`es*` → `"es"`—; cualquier otro
      cae en :data:`FALLBACK_LANGUAGE`.
    """
    if setting in SUPPORTED_LANGUAGES:
        return setting
    codigo = (system_language or "").strip().lower()
    if codigo.startswith("es"):
        return "es"
    if codigo.startswith("en"):
        return "en"
    return FALLBACK_LANGUAGE


__all__ = ["FALLBACK_LANGUAGE", "LANGUAGE_SYSTEM", "resolve_language"]

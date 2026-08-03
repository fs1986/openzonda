# S029 · OZ-33 · El guard de versión rechaza Windows 11 24H2 (build 26200) siendo válido

Fecha: 2026-08-02 · Fase: F0 (bug) · Rama: `feature/oz-33-guard-baseline-build` · Prioridad: High

Bug prioritario detectado por el PO durante la validación `[HW]` de OZ-4. Bloquea OZ-4
(no puede completarse la validación install→upgrade→uninstall si la app no abre).

## Síntoma (de la tarjeta)

En una VM Windows 11 Home 24H2 (10.0.26200, build 26200) la app se niega a arrancar con
«OpenZonda requiere Windows 10 22H2 (build 19045) o superior. Consulta ADR-001», siendo
26200 ≫ 19045.

## Diagnóstico ANTES de tocar nada (regla de la tarjeta: loguear el valor crudo, no asumir)

La instrucción fue explícita: registrar el valor **crudo** que ve el guard, sin dar por
buena ninguna hipótesis. Dos sondas, en la propia máquina build 26200 (el equipo de
desarrollo es 26200):

**1. Qué reporta cada vía de detección** (`scratchpad/version_probe.py`):

```
sys.getwindowsversion : build=26200
GetVersionExW         : build=26200
RtlGetVersion         : build=26200
registro CurrentBuildNumber = '26200', UBR = 8973
```

Todas coinciden en 26200. La detección **del ejecutable no miente** en esta máquina, así que
la hipótesis del manifiesto del bundle PyInstaller (sospecha (a) de la tarjeta) no se
sostiene aquí.

**2. Dónde está realmente el guard.** Búsqueda en el código: la única comprobación de
`19045` no está en Python, sino en la `LaunchCondition` del MSI (`OpenZonda.wxs`):

```
Installed OR (WindowsBuild >= 19045)
```

**3. Qué ve el MSI.** Sonda diagnóstica: un MSI mínimo con la condición original y un
mensaje que imprime los valores crudos, ejecutado en la máquina build 26200. Resultado: la
condición **falla y aborta la instalación** — reproducido el bug en hardware real. La causa,
confirmada además por el issue tracker de WiX y la KB de Flexera: en Windows 10/11 la
propiedad MSI `WindowsBuild` queda **congelada en 9600** (valor de Win 8.1) porque
`msiexec.exe` no declara Windows 10 en su manifiesto y MSI deriva la propiedad del
`GetVersionEx` compatibilizado. `9600 >= 19045` es falso.

**Alcance real, mayor que el reportado:** el guard no bloquea «todo 24H2», bloquea **toda
instalación limpia en cualquier Windows 10/11**. No se había detectado antes porque la
validación `[HW]` de instalación limpia de OZ-4 se está haciendo por primera vez ahora — que
es precisamente cómo apareció este bug.

## Decisión (ADR-009)

El umbral 19045 de ADR-001 **no se toca**; se corrige la *detección*. El piso de versión
pasa a aplicarse como **aserción de arranque fail-closed en runtime** (`openzonda.baseline`,
composition root), leyendo el build real por una vía no compatibilizada (registro
`CurrentBuildNumber`, `RtlGetVersion` de respaldo), **logueando el valor crudo** y comparando
como **entero**. Del MSI se retira la condición rota; se conserva el preflight de x64.

Por qué runtime y no arreglar el MSI: una `LaunchCondition` no puede leer el registro de
forma fiable (la acción `LaunchConditions` se secuencia **antes** que `AppSearch`), y el modo
portable no pasa por el instalador. El detalle y su encaje con ADR-001 —que prohíbe *gatear
capacidades* por versión, no una aserción de piso única— en **ADR-009**.

## Criterios de aceptación: contrastados con evidencia

| # | Criterio | Cómo se verifica | Estado |
| --- | --- | --- | --- |
| 1 | Abre en build 26200 | El MSI ya no bloquea (condición retirada) + el guard runtime acepta 26200 (test) | **Verificado en unit + repro MSI; falta confirmación del PO en VM** |
| 2 | Sigue rechazando < 19045 con el mensaje actual | `is_supported_build(19044) is False`; `BASELINE_MESSAGE` idéntico al del MSI | **PASS** |
| 3 | Test de los cuatro builds de referencia | `pytest tests/unit/test_baseline_guard.py` | **11 passed** (19044 rechaza; 19045/22000/26200 aceptan) |
| 4 | El guard loguea el valor crudo | test `test_enforce_loguea_el_build_crudo_detectado` | **PASS** |

Gate completo antes del PR:

```
uv run ruff check .                         All checks passed!
uv run ruff format --check .                (touched files formateados)
uv run lint-imports                         Contracts: 4 kept, 0 broken
uv run pytest                               216 passed
wix build OpenZonda.wxs (dummy vars)        compila (MSI generado)
```

## Por qué esto NO se cierra con tests unitarios (regla A)

El criterio 1 —«abre en build 26200»— depende de la máquina real del PO. Los tests
unitarios prueban el contrato del guard, y el repro del MSI prueba que la condición vieja
bloqueaba; **ninguno prueba que la app efectivamente abre en la VM 26200 del PO**. Por eso
OZ-33 queda en **Review**, no en Done, hasta que el PO instale el nuevo MSI en esa VM y
confirme que OpenZonda arranca. El bug se marcó como `[HW]`.

## Entrega al PO

Se necesita un MSI nuevo con el fix para probar en la VM. El pipeline `release.yml` produce
el instalador; el MSI del fix debe salir de un run/artifact o de un release en borrador (ver
OZ-32 sobre cómo acceder a los assets de un borrador). Coordinar con el fundador qué vía usar.

## Artefactos

| Archivo | Contenido |
| --- | --- |
| `apps/openzonda/baseline.py` | `is_supported_build`, `detect_windows_build` (registro + RtlGetVersion), `enforce_baseline`, `BASELINE_MESSAGE`, `SUPPORTED_WINDOWS_BUILD` |
| `apps/openzonda/__main__.py` | Invoca `enforce_baseline` antes de crear la `QApplication`; código de salida 3 si no soportado |
| `tests/unit/test_baseline_guard.py` | Cuatro builds de referencia, comparación por entero, logueo del crudo, fail-open |
| `packaging/windows/OpenZonda.wxs` | Retirada la `LaunchCondition` de `WindowsBuild`; conservado el preflight x64, con el porqué |
| `ADR/ADR-009-piso-version-runtime.md` | Decisión y encaje con ADR-001 |

## Desvíos / deuda registrada

- **Un SO por debajo del piso ahora puede instalar el MSI** (ya no se bloquea por versión en
  install-time) pero la app se negará a abrir con mensaje claro. Coste aceptado en ADR-009
  frente a reintroducir el false-block.
- El repro del MSI dejó procesos `msiexec` colgados en el diálogo de rechazo (el `/quiet` no
  lo suprime); se limpiaron. Nada quedó instalado (la condición rechazó 26200, como debía).

## Estado de proceso

- OZ-33: **In Progress → Review** (pendiente validación `[HW]` del PO en VM build 26200).
- OZ-33 **blocks** OZ-4 (enlace creado). OZ-4 sigue en Review, no se cierra.
- OZ-32 (documentar acceso a release en borrador) y OZ-7 (cierre de tarjeta) quedan aparte.

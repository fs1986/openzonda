# ADR-009 — Piso de versión de Windows: aserción de arranque en runtime

- **Estado:** Propuesto (pendiente de aceptación del fundador en el PR de OZ-33)
- **Fecha:** 2026-08-02
- **Decisores:** architect
- **Relacionado:** complementa (no supersede) ADR-001; motivado por el bug OZ-33.

## Contexto

ADR-001 fija el baseline en Windows 10 22H2 (build 19045) y ordena comprobar las
**capacidades por disponibilidad en runtime, nunca por número de versión**. El piso de
versión se aplicaba en el **preflight del instalador** (diseño §18) con una `LaunchCondition`
`Installed OR (WindowsBuild >= 19045)`.

Esa comprobación estaba rota (OZ-33). En Windows 10/11 la propiedad MSI `WindowsBuild`
queda **congelada en 9600** (valor de Windows 8.1): `msiexec.exe` no declara Windows 10 en
su manifiesto y MSI deriva la propiedad del `GetVersionEx` compatibilizado. Como
`9600 >= 19045` es falso, la condición **rechazaba toda instalación limpia en Windows
moderno**, build 26200 (24H2) incluido — lo contrario de su propósito. Reproducido en una
máquina real build 26200: el MSI aborta con el diálogo de rechazo; en la misma máquina, el
registro `CurrentBuildNumber` y `RtlGetVersion` devuelven el 26200 correcto.

Corregir la condición dentro del MSI leyendo el registro no es fiable: la acción
`LaunchConditions` se **secuencia antes que `AppSearch`**, así que la propiedad de una
`RegistrySearch` aún no está poblada cuando la condición se evalúa. Sortearlo exige
re-secuenciar o una custom action nativa. Además, el **modo portable** (diseño §18) no pasa
por el instalador, luego un guard que viva solo en el MSI deja ese modo sin piso.

## Decisión

El piso de versión de Windows se aplica como una **aserción de arranque fail-closed** en el
composition root (`openzonda.baseline`, invocada por `main()` antes de crear la
`QApplication`). Lee el build **real** por una vía no compatibilizada —registro
`CurrentBuildNumber`, con `RtlGetVersion` de respaldo—, **loguea el valor crudo** y lo
compara **como entero** contra 19045. Si no llega, muestra el mensaje de ADR-001 y sale con
código 3. Si el build no puede determinarse, **no bloquea** (fail-open), para no reintroducir
el false-block que motivó OZ-33.

El MSI conserva únicamente el preflight de **arquitectura x64** (`VersionNT64`, que no depende
del número de versión). Se elimina la `LaunchCondition` basada en `WindowsBuild`.

Esta aserción de piso **no contradice ADR-001**: ADR-001 prohíbe *gatear capacidades por
versión* (ramificar qué API se usa según el número de versión). Aquí no se ramifica ninguna
funcionalidad; es un único umbral de "me niego a arrancar por debajo del SO soportado", que
es exactamente lo que el preflight ya pretendía, movido a donde puede leerse la verdad y
verificarse.

## Consecuencias

- **Positivas:** detección veraz que previene la *clase* de bug (no solo build 26200);
  cubre también el modo portable; verificable con unit tests deterministas (los cuatro
  builds de referencia) y con el valor crudo en el log para diagnóstico futuro.
- **Aceptadas:** un SO por debajo del piso ahora **puede instalar** el MSI (ya no se bloquea
  en tiempo de instalación por versión) pero la aplicación **se negará a abrir** con un
  mensaje claro. Se pierde el fail-fast de versión en el instalador; se mantiene el de x64.
  Es un coste menor frente a reintroducir el rechazo de sistemas válidos.
- **Alternativas descartadas:**
  - *Parchear solo el manifiesto de `msiexec`*: imposible, es un binario del sistema.
  - *`RegistrySearch` + re-secuenciar `AppSearch` antes de `LaunchConditions`, o custom
    action nativa*: más superficie frágil para replicar algo que el ejecutable hace bien y
    de forma testeable.
  - *Mantener `WindowsBuild`*: es la causa raíz del bug.

## Verificación

- `tests/unit/test_baseline_guard.py`: 19044 rechaza; 19045, 22000 y 26200 aceptan;
  comparación por entero (no lexicográfica); se loguea el build crudo; fail-open si es
  indeterminado.
- `apps/openzonda/__main__.py` invoca `enforce_baseline` antes de arrancar la UI.
- Contrato de capas (import-linter, ADR-003): el guard vive en `openzonda`; la UI (`desktop`)
  no importa `winreg`/`ctypes`.
- `[HW]` El PO confirma que la aplicación abre en su VM build 26200 (criterio que no puede
  cerrarse solo con tests unitarios).

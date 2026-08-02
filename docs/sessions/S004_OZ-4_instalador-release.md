# S004 · OZ-4 · Instalador WiX + pipeline de release

Fecha: 2026-08-02 · Duración: ~1 h 30 min · Fase: F0 · Rama: `feature/oz-4-instalador-release`

## Objetivo (copiado de la tarjeta)

Autoría WiX: MSI per-user, UpgradeCode fijo, MajorUpgrade, uninstaller, preflight.
Workflow `release.yml` por tag: build → SHA256SUMS → SBOM CycloneDX → Release draft.
Redacta CONTRIBUTING, GOVERNANCE, SECURITY, BUILD.md. Cierra F0 con retro.

## Agentes utilizados y salidas clave

Sesión ejecutada por el agente principal sin delegar en subagentes, por decisión del
fundador. Roles: `devops` (WiX, release, CI), `security` (SBOM, política de auditoría,
corrección de `SECURITY.md`), `docs` (gobernanza), `scrum` (retro F0), `pm-jira`.

## Decisiones tomadas (y si requirieron ADR)

### WiX v4 → v5 (no requiere ADR, pero corrige el stack declarado)

`CLAUDE.md` y el diseño §12 fijaban **WiX v4**. Al construir, v4 rechaza el elemento
`<Files>`, que es el que cosecha automáticamente un árbol de archivos; ese elemento existe
solo desde v5.

La alternativa dentro de v4 era enumerar a mano los 177 archivos del bundle, o escribir un
harvester propio. Ambas producen una lista que se desincroniza en silencio en cuanto
cambia una versión de PySide6 — y "en silencio" es la parte grave: el instalador se
construiría igual, sin las DLL nuevas, y el fallo aparecería en la máquina del usuario.

Se sube a v5 y se corrige la documentación (`CLAUDE.md`, diseño §12 y §18, plan de
implementación F0.6, plan operativo). No es una decisión inmutable, pero dejar la
documentación afirmando v4 habría sido dejarla mintiendo.

### El espacio en disco no se comprueba en el preflight

El plan pedía "preflight x64/espacio". Se implementan las dos primeras comprobaciones como
`<Launch>` reales: arquitectura x64 y build de Windows ≥ 19045 (Windows 10 22H2, el
baseline de ADR-001).

El espacio en disco **no** se comprueba: Windows Installer lo calcula durante
`CostFinalize` y aborta con un mensaje claro y ya localizado. Duplicar esa lógica con un
umbral fijo produce una comprobación que envejece mal —el tamaño del bundle cambia cada
release— y que puede contradecir a la del propio instalador. Se declara explícitamente en
el `.wxs` en lugar de fingir que se hizo.

### El preflight por número de versión no contradice ADR-001

ADR-001 dice "toda API se comprueba por disponibilidad en runtime, **nunca** por número de
versión". Eso se refiere a detectar capacidades del stack WLAN dentro de la aplicación.
El preflight del instalador es otra cosa: impide instalar sobre un SO fuera del baseline
soportado, y ahí el número de versión es el único criterio disponible, porque todavía no
existe aplicación alguna que pueda interrogar al sistema. Queda anotado en el `.wxs`.

### Política de auditoría: bloquear solo lo que llega al usuario

Decisión del fundador entre tres opciones. Un CVE en una dependencia de **runtime** (las 5
que viajan dentro del MSI) rompe el build. Un CVE en herramientas de desarrollo (las 78 del
conjunto completo: pytest, mypy, ruff, PyInstaller) se reporta pero no bloquea.

El razonamiento: bloquear releases por un CVE en una herramienta de test que no llega a
ninguna máquina ajena enseña al equipo a desactivar la comprobación, y una comprobación
desactivada es peor que una comprobación que distingue.

### Fuera de alcance, declarado

- **ZIP portable.** El diseño lo lista como canal de distribución, pero F0.7 define el
  contenido de la release y no lo incluye. Añadirlo sería decidir por el producto desde una
  tarjeta de tooling. Queda como deuda.
- **Diálogo de desinstalación con opción "eliminar todo"** (diseño §18). Requiere UI
  personalizada en el MSI. El valor por defecto del diseño —conservar datos— sí está
  garantizado, y por la vía más sólida: el instalador no escribe fuera de
  `%LOCALAPPDATA%\Programs\OpenZonda`, así que desinstalar no puede destruir nada. La
  decisión inmutable nº 6 se satisface no eliminando nada.

## Un bug real encontrado al verificar, no al escribir

El primer MSI construido **incluía `logs\openzonda.log` y `settings.json`** de la ejecución
local del smoke test. Se detectó extrayendo el MSI con `msiexec /a` en lugar de darlo por
bueno porque `wix build` había salido en verde.

Consecuencias si hubiera llegado a una release:

1. Se distribuirían los logs de la máquina de quien compila.
2. Peor: si el bundle hubiera tenido un `portable.marker` —y lo tiene mientras corre el
   smoke test— **toda instalación habría arrancado en modo portable**, guardando la
   configuración junto al ejecutable en `Program Files`-like en lugar de en el perfil del
   usuario.

Arreglo: `build_msi.ps1` copia el bundle a un staging, elimina `logs`, `cache`,
`settings.json` y `portable.marker`, y **falla el build** si alguno sobrevive. Así el orden
de construcción deja de importar, que es lo que hacía el fallo intermitente y difícil de
atribuir.

## Corrección en `SECURITY.md`

El archivo afirmaba que las releases se publican con "artefactos firmados". **Es falso**:
no hay certificado de firma de código y SmartScreen advertirá al usuario. Se corrigió el
texto y se añadió una sección explicando qué se publica en su lugar (SHA256SUMS y SBOM) y
por qué. Una política de seguridad que promete una garantía inexistente es peor que no
tenerla.

## Artefactos

| Archivo | Qué es |
| --- | --- |
| `packaging/windows/OpenZonda.wxs` | Autoría MSI per-user, UpgradeCode fijo, MajorUpgrade, preflight |
| `packaging/windows/build_msi.ps1` | Traduce la versión de git a ProductVersion y construye desde staging limpio |
| `packaging/release-notes.md` | Notas de release versionadas, con una sección explícita de "sin verificar" |
| `.github/workflows/release.yml` | Pipeline por tag: bundle → smoke → MSI → SBOM → audit → SHA256SUMS → draft |
| `.github/workflows/ci.yml` | Job de auditoría nuevo, con criterios distintos para runtime y desarrollo |
| `BUILD.md` | Cómo compilar desde cero sin preguntar nada |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1, con una nota sobre honestidad metrológica |
| `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/` | Plantillas |
| `docs/retros/F0-retro.md` | Retro de fase |

## DoD: checklist con estado real (no aspiracional)

- [x] **MSI per-user idempotente** — `UpgradeCode` fijo, `MajorUpgrade` con
      `AllowSameVersionUpgrades`, atajo en el menú Inicio con keypath HKCU, preflight de
      x64 y build de Windows. **36,8 MB** desde un bundle de 112,8 MB.
- [x] **El MSI instala donde debe** — verificado extrayéndolo con `msiexec /a`:
      `LocalApp\Programs\OpenZonda\` con `OpenZonda.exe` y `_internal\`, y nada más.
- [x] **SBOM CycloneDX** — 1.6, 5 componentes de runtime, generado desde el mismo `uv.lock`
      con el que se construye el artefacto, así que no puede desincronizarse.
- [x] **Auditoría de dependencias** — `pip-audit` sin vulnerabilidades conocidas ni en las
      5 de runtime ni en las 78 del conjunto completo. Política escrita en `SECURITY.md`.
- [x] **Documentos de gobernanza** — `BUILD.md`, `CODE_OF_CONDUCT.md` y plantillas.
      `CONTRIBUTING`, `GOVERNANCE` y `SECURITY` ya existían; este último, corregido.
- [x] **Retro F0** — `docs/retros/F0-retro.md`.
- [ ] **Tag `v0.0.1` produce release completa sin intervención manual** — pendiente:
      el tag se crea **después** de mergear, y hasta entonces `release.yml` no se ha
      ejecutado nunca. Es el único DoD que no se puede verificar antes del merge.
- [ ] **[HW] Install → upgrade → uninstall en VM Windows 11 limpia** — pendiente,
      corresponde al fundador.

## Validaciones [HW] pendientes del fundador

1. **Ciclo completo en VM limpia**: instalar el MSI, instalar encima una versión con número
   mayor para comprobar que `MajorUpgrade` reemplaza en vez de duplicar la entrada en
   Programas y características, y desinstalar comprobando que `%APPDATA%\OpenZonda\`
   sobrevive.
2. Comprobar el atajo del menú Inicio y que la aplicación arranca desde él.
3. Confirmar que SmartScreen advierte —es lo esperado sin firma— y que se puede continuar.

## Desvíos / deuda registrada

- **Sin firma de código.** Es la deuda de mayor impacto para la alpha: cada colega verá una
  advertencia de SmartScreen. Requiere comprar un certificado.
- **ZIP portable** no producido por el release, pese a estar en los canales de distribución
  del diseño.
- **Diálogo de desinstalación con opción "eliminar todo"** sin implementar.
- **Sin icono ni `VERSIONINFO`** en el ejecutable (arrastrado de S003). No se inventó un
  icono: el logotipo es una decisión de producto del fundador, no de esta sesión.
- **`pre-commit`** sigue sin configurar ni tarjeta (arrastrado de S002).
- Se instaló **.NET SDK 8** en la máquina de desarrollo, necesario para WiX.

La retro de F0 recoge estos siete elementos en una tabla y establece el acuerdo de que la
deuda sin tarjeta no cuenta como registrada.

## Próxima sesión sugerida

**OZ-5 · S005 · Dominio: entidades y value objects**, primera de F1. Antes conviene:

1. Ejecutar las validaciones `[HW]` de OZ-3 y OZ-4. F1 construye la shell de proyectos
   sobre una ventana que **nadie ha visto renderizada**.
2. Dar destino a los siete elementos de deuda de la retro: tarjeta o aceptación por escrito.

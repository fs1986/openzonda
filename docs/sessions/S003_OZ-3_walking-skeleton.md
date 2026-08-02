# S003 · OZ-3 · Walking skeleton Qt + PyInstaller

Fecha: 2026-08-02 · Duración: ~1 h 30 min · Fase: F0 · Rama: `feature/oz-3-walking-skeleton`

## Objetivo (copiado de la tarjeta)

Implementa MainWindow mínima con logging JSON y settings.json versionado; modo portable
por marker file. Crea el spec de PyInstaller onedir con exclusiones y versión desde git
tag. Genera el bundle y un script `scripts/smoke_local.ps1` que lo arranca y verifica el
log.

## Agentes utilizados y salidas clave

Sesión ejecutada por el agente principal sin delegar en subagentes, por decisión del
fundador. Roles cubiertos en secuencia: `architect` (ADR-008 y nomenclatura), `qa` (tests
del contrato, escritos y ejecutados en rojo antes de implementar), `dev-ui` y `dev-core`
(implementación), `devops` (spec, smoke test, CI), `security` (revisión de dependencias
nuevas).

## Decisiones tomadas (y si requirieron ADR)

### ADR-008 — Composition root en un paquete propio (sí requirió ADR)

El DoD pedía `settings.json` y modo portable, es decir **acceso a disco**, en la primera
línea de UI del proyecto. El contrato de capas prohíbe que `desktop` importe
`persistence`, y alguien tiene que instanciar los adaptadores concretos: es la tensión
clásica del *composition root*.

Se resolvió con un paquete nuevo, `apps/openzonda`, único autorizado a importar
infraestructura. `desktop` queda reducido a vistas y recibe sus colaboradores por
constructor. Alternativas descartadas y su porqué están en el ADR.

Consecuencia verificable: los cinco tests de `MainWindow` corren **sin tocar el disco**,
con un doble del port. Si la ventana construyera su propio repositorio, no podrían.

### Nomenclatura: el renombrado del producto nunca se había propagado

El diseño §18 seguía especificando `%APPDATA%\WiFiSurveyAI\settings.json` y §19 los
códigos de error como `WSA-xxxx`, con el nombre anterior del producto. OZ-3 era la primera
tarjeta que tenía que materializar esas rutas en código, así que se corrigió antes de que
el nombre viejo se filtrara al binario.

- Rutas → `%APPDATA%\OpenZonda\`, `%LOCALAPPDATA%\OpenZonda\{logs,cache}\`.
- Códigos de error → prefijo **`OZD-`**, no `OZ-`: este último colisionaría visualmente
  con las claves de tarjeta Jira (`OZ-3`), y un código de error que se confunde con un
  ticket es una fuente de ruido garantizada en soporte.
- CLI de fixtures → `oz-capture` (afecta a S013, aún no implementada).

### Otras decisiones, sin ADR

1. **`onedir` y no `onefile`.** `onefile` se descomprime en un temporal en cada arranque:
   penaliza el inicio y rompe la expectativa del modo portable, donde el usuario quiere
   ver la carpeta y su `portable.marker`.
2. **Un settings roto no impide arrancar.** JSON corrupto, permisos, valores inválidos →
   se cae a valores por defecto. Un usuario que no puede abrir el programa por su archivo
   de preferencias no tiene forma de arreglarlo desde dentro del programa.
   **Única excepción**: un `schema_version` mayor que el soportado sí falla, y además la
   aplicación arranca con un repositorio de solo lectura para **no sobrescribir**
   configuración que no sabe interpretar. El diseño §18 exige que el upgrade preserve los
   settings; el downgrade merece la misma cortesía.
3. **Modificador `--smoke [ms]`.** Programa el cierre de la ventana con un `QTimer`, de
   modo que el smoke test ejercita el **event loop real** y no una simulación. Sin esto,
   verificar el arranque de una app GUI desde un script exige matarla por PID y el código
   de salida deja de significar nada.
4. **Contrato de capas nuevo: "Application declara ports, no conoce adaptadores".**
   Sin él, `application` podría importar `persistence` y la inversión de dependencias
   quedaría en decoración. Cubierto por los tests de mutación de OZ-23.
5. **`smoke_local.ps1` se guarda con BOM UTF-8.** Windows PowerShell 5.1 —el que trae
   Windows de fábrica— lee los `.ps1` sin BOM como ANSI y destroza los acentos. Se
   detectó ejecutándolo de verdad, no leyéndolo.

## Revisión de dependencias (rol `security`)

Dos incorporaciones, ambas registradas en `uv.lock` con hash:

| Dependencia | Dónde | Justificación |
| --- | --- | --- |
| `PySide6` 6.11.1 | extra `ui` (ya declarado en F0) | Qt6 bajo LGPL con enlace dinámico, según el stack fijado |
| `pyinstaller` 6.11+ | grupo `build` (nuevo) | Herramienta de build: **no viaja en el binario distribuido**. Se aísla en su propio grupo para no lastrar el entorno de desarrollo ni el de tests |

El lockfile pasa de 583 a **607 hashes `sha256`**, 46 paquetes resueltos.

## Artefactos

Paquetes y módulos nuevos:

- `apps/openzonda/` — composition root: `__main__.py`, `logging_setup.py`, `version.py`.
- `apps/desktop/main_window.py`, `apps/desktop/app.py`.
- `packages/application/settings.py` — `AppSettings` + port `SettingsRepository`.
- `packages/persistence/app_paths.py`, `packages/persistence/settings_json.py`.
- `packaging/openzonda.spec`, `scripts/smoke_local.ps1`.

Tests: de 10 a **44**. Nuevos en `test_settings.py`, `test_app_paths.py`,
`test_settings_json.py`, `test_logging_json.py`, `test_main_window.py`, más dos casos
añadidos al test de contratos de capas (application→adaptador, UI→composition root).

## DoD: checklist con estado real (no aspiracional)

- [x] **Bundle < 180 MB** — **112,8 MB** medidos por `smoke_local.ps1`. El margen viene de
      excluir 35 módulos Qt no usados; solo QtWebEngine pesa más de 100 MB.
- [x] **Log JSON correcto generado** — dos líneas, ambas JSON válido, con
      `timestamp`/`level`/`logger`/`message`. Rotación 10 MB y 5 copias, según §19.
- [x] **El bundle arranca y cierra limpio** — código de salida 0; 2,4 s totales, de los
      cuales 1,5 s son el cierre programado, así que el arranque real ronda los 0,9 s en
      esta máquina. Verificado además con `QT_QPA_PLATFORM=offscreen`, igual que CI.
- [x] **Modo portable** — con `portable.marker`, settings y logs viven junto al ejecutable
      y ninguna ruta escapa de la carpeta de la app (test dedicado al invariante).
- [ ] **[HW] Arranque < 4 s en tu máquina / VM** — pendiente. Lo medido arriba es esta
      máquina de desarrollo, que no es el escenario del DoD. Ejecuta
      `scripts/smoke_local.ps1` para confirmarlo.

## Validaciones [HW] pendientes del fundador

1. Ejecutar `scripts/smoke_local.ps1` sobre el artefacto del PR (o construir en local con
   `uv run --group build pyinstaller packaging/openzonda.spec --noconfirm`) y confirmar
   que arranca en menos de 4 s.
2. Comprobar visualmente que la ventana se abre y se cierra sin residuos. CI lo ejecuta en
   modo `offscreen`, así que **nadie ha visto todavía la ventana dibujada de verdad**.

## Desvíos / deuda registrada

- **La versión del bundle es un hash, no un número.** `git describe --tags` no encuentra
  ningún tag porque el repositorio aún no tiene ninguno, así que el bundle se identifica
  como `9fe937b-dirty`. Es el comportamiento correcto —preferible a inventar un número que
  parezca un release— y se resuelve solo cuando OZ-4 cree el tag `v0.0.1`.
- **El diseño §7.3 no contempla `apps/openzonda`.** ADR-008 lo justifica, pero el capítulo
  de estructura del diseño debería reflejarlo.
- **`pre-commit` sigue sin configurar ni tarjeta**, arrastrado desde S002.
- **Sin icono ni metadatos de versión en el ejecutable.** El `.exe` sale con el icono por
  defecto de PyInstaller y sin `VERSIONINFO` de Windows. Es trabajo natural de OZ-4, junto
  con la firma del instalador.
- El plan operativo §2 sigue describiendo un repo documental separado que no existe
  (arrastrado desde S001).

## Próxima sesión sugerida

**OZ-4 · S004 · Instalador WiX + pipeline de release [HW]**, que cierra F0: MSI per-user,
`release.yml` por tag con SHA256SUMS y SBOM CycloneDX (absorbido de OZ-24), documentos de
gobernanza pendientes (`BUILD.md`, `CODE_OF_CONDUCT.md`, plantillas de issue/PR) y la
retro de F0.

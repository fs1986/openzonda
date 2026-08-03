# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto sigue [Versionado Semántico](https://semver.org/lang/es/).

## [No publicado]

### Añadido
- **Contenedor de proyecto `.wifisurvey` (OZ-7).**
  - Guardado **atómico**: temporal, `fsync` y `rename`. En cualquier instante el archivo es la versión vieja completa o la nueva completa, nunca una mezcla. Verificado matando el proceso justo antes del renombrado.
  - Apertura defensiva de archivos que pueden venir de terceros: se rechazan rutas que escapan del destino, bombas de compresión, tamaños mentidos en el encabezado, enlaces simbólicos, nombres duplicados y manifests desproporcionados.
  - **Nada de lo que dice el archivo se cree sin comprobarlo leyendo**: el tamaño declarado nunca se usa para reservar memoria, y el límite se aplica contando los bytes que salen del descompresor, abortando a mitad.
  - Cuatro tipos de error distintos —ajeno, de versión futura, corrupto y hostil— porque la acción del usuario es distinta en cada caso.
  - Escritura determinista: dos guardados del mismo contenido producen bytes idénticos, para que las copias incrementales y los diffs sigan sirviendo.
  - Hashes de cada entrada en el manifest, verificados al abrir: detectan manipulación.
- **Persistencia SQLite (OZ-6).**
  - Runner de migraciones con numeración lineal y **una transacción por migración**: si la quinta falla, las cuatro anteriores quedan confirmadas y reabrir el proyecto reintenta solo desde donde se cortó.
  - Esquema inicial según diseño §8.2, con tablas `STRICT` — SQLite acepta por defecto texto en una columna `INTEGER`, y eso contradice el invariante de honestidad del dato.
  - **Apertura defensiva** de todo proyecto, sin opción de desactivarla: `trusted_schema=OFF` impide que un esquema hostil ejecute funciones desde vistas o triggers; `foreign_keys=ON` porque SQLite las trae apagadas; WAL para que la UI dibuje mientras se captura.
  - Abrir un proyecto de una versión más nueva **falla sin tocar el archivo**, diciendo qué versión trae y cuál se entiende.
  - `SQLiteProjectRepository`: guardar reemplaza el estado completo en lugar de acumular, para que borrar un sitio lo borre de verdad.
  - Las migraciones viajan en el bundle: son `.sql`, y el análisis de imports de PyInstaller no las habría visto.
- **Núcleo de dominio de F1 (OZ-5).**
  - Value objects de unidades con álgebra real: `dBm - dBm → dB` (eso es un SNR), `dBm ± dB → dBm` (atenuar), `dB + dB → dB` (atenuaciones acumuladas). Sumar dos dBm es `TypeError`, porque no significa nada físicamente. Mezclar píxeles con metros, tampoco.
  - **«No disponible» como tipo de primera clase**: `Unavailable` lleva su motivo y **no tiene atributo `value`**, así que el código que intente leer un número inexistente falla en lugar de inventarlo. `Reading[T] = Measured[T] | Unavailable` obliga a distinguir ambos casos.
  - Regla de derivación: un valor derivado nunca es más fiable que su entrada menos fiable. Aplicada al SNR — con noise observado es `DERIVED`, **nunca `OBSERVED`**; sin noise es «no disponible», **nunca `0`**, que es el caso normal en Windows.
  - `Calibration` píxel↔metro que **almacena su incertidumbre**: se deriva de dos clics humanos, y calibrar sobre una distancia larga reduce el error de forma cuantificada.
  - Entidades frozen `Project`, `Site`, `Floor`, `FloorPlan` y `SurveySession`, con procedencia **por atributo**: en modo continuo la posición es derivada mientras el RSSI sigue siendo observado.
  - Flags de calidad que anotan sin invalidar (diseño §10.2).
  - Tests: 44 → 126, con property tests de invariantes de calibración.
- **F0 — bootstrap del repositorio.**
  - Estructura hexagonal (`packages/`, `apps/desktop`, `native/windows`) según diseño §7.3.
  - Documentación de diseño convertida a Markdown en `docs/design/` (fuente `.docx` en `docs/design/source/`).
  - ADR-001 a ADR-006 materializados en `ADR/`.
  - Invariante de honestidad metrológica en `packages/domain/measurement.py` (`Measured`, `Provenance`) con tests de contrato.
  - Tooling: `pyproject.toml` con uv, ruff, mypy (strict en dominio y RF), pytest y contratos `import-linter`.
  - CI en GitHub Actions (lint, type-check, tests y contratos de capas).
  - Gobernanza OSS: `LICENSE` (Apache-2.0), `CONTRIBUTING`, `SECURITY`, `GOVERNANCE`.
- **Hardening de CI (OZ-23).**
  - `uv.lock` versionado (583 hashes `sha256`); CI usa `uv sync --locked`, que falla si el lock no concuerda con `pyproject.toml`.
  - CI en matriz `ubuntu-latest` + `windows-latest`: Windows es el SO objetivo del producto y hasta ahora no se compilaba nunca.
  - Tests de la barrera de capas en `tests/integration/test_contratos_de_capas.py`: inyectan un import ilegal y verifican que `lint-imports` lo rechaza. Validados por mutación.

- **Cierre documental de F0 (OZ-1).**
  - `ADR-007 — Binding a wlanapi.dll mediante ctypes`, que materializa como ADR la decisión ya razonada en `plan-implementacion.md` §4.1. Gobierna la superficie más delicada del producto y F2 depende de ella.
  - Templates de trabajo en `docs/templates/`: session log, tarjeta Jira y retro de fase.
  - `docs/retros/` para las retros de fase.
  - Session logs reconstruidos de S001 y S002, marcados explícitamente como reconstrucciones a posteriori desde el historial de git y no como registro contemporáneo.

- **Walking skeleton de escritorio (OZ-3).**
  - `MainWindow` PySide6 mínima, con geometría persistida entre sesiones.
  - Composition root en `apps/openzonda` (ADR-008): único paquete que cablea adaptadores, de modo que la UI no importa infraestructura.
  - `AppSettings` con esquema versionado y port `SettingsRepository`; adaptador JSON con escritura atómica. Un settings corrupto no impide arrancar; uno de esquema más nuevo no se sobrescribe.
  - Modo portable detectado por `portable.marker`: config, logs y caché viven junto al ejecutable y nada se escribe en el perfil del usuario.
  - Logging estructurado en JSON lines con rotación (10 MB, 5 copias), según diseño §19.
  - Bundle PyInstaller onedir (112,8 MB) y `scripts/smoke_local.ps1`, que verifica tamaño, código de salida y validez del log.
  - Nuevo contrato de capas: `application` declara ports y no conoce adaptadores.

- **Instalador y pipeline de release (OZ-4).**
  - Instalador MSI per-user (WiX v5), sin elevación: `UpgradeCode` fijo, `MajorUpgrade`, atajo en el menú Inicio y preflight de arquitectura x64 y versión de Windows. 36,8 MB.
  - `release.yml` por tag: bundle → smoke test → MSI → SBOM CycloneDX → auditoría → SHA256SUMS → release en borrador.
  - Auditoría de dependencias en CI con `pip-audit`: bloqueante para las que viajan en el instalador, informativa para las de desarrollo.
  - `BUILD.md`, `CODE_OF_CONDUCT.md`, plantillas de issue y PR.
  - Retro de fase F0 en `docs/retros/F0-retro.md`.

- **Smoke test usable por una persona (OZ-25).**
  - Modificador `-Visible` en `scripts/smoke_local.ps1`: muestra la ventana 8 s en lugar de lanzarla minimizada, para poder validarla a ojo.
  - `scripts/smoke_local.cmd`: lanzador de doble clic que aplica la política de ejecución, mantiene la ventana abierta al terminar —también al fallar— y propaga el código de salida.
  - La salida ahora separa el arranque real del cierre programado, en lugar de obligar a restar mentalmente.

- **Identidad del ejecutable (OZ-29).**
  - Icono en el ejecutable, en el atajo del menú Inicio y en la entrada de «Aplicaciones instaladas». **Provisional**: se reemplaza cuando exista el logotipo definitivo.
  - Bloque `VERSIONINFO`: producto, versión, empresa, copyright Apache-2.0 y descripción, generados desde la misma versión que usa el resto del build. La cuaterna numérica cae a `0.0.0.0` cuando no hay tag reconocible, en lugar de inventar un número con pinta de release; la cadena exacta de `git describe` se conserva en `FileVersion`.
- **Instalación documentada (OZ-26).** El README explica la advertencia de SmartScreen antes de que aparezca, qué significa realmente y cómo verificar el instalador por SHA-256 y SBOM.

### Cambiado
- Toolchain del instalador: WiX v4 → **v5**.
- **Decisión: v0.x se distribuye sin firmar** (OZ-26). No se adquiere certificado de firma de código para la alpha; se revisita Azure Trusted Signing cuando haya usuarios reales. El elemento `<Files>`, que cosecha el árbol del bundle automáticamente, solo existe desde v5; en v4 habría que enumerar a mano las dependencias de Qt, una lista que se desincroniza en silencio al cambiar de versión.
- Rutas de aplicación y códigos de error adoptan el nombre definitivo del producto: `%APPDATA%\OpenZonda\`, prefijo `OZD-` para errores (no `OZ-`, que colisiona con las claves de tarjeta) y CLI de fixtures `oz-capture`. El renombrado nunca se había propagado al diseño §18 y §19.

### Corregido
- **El guard de versión rechazaba todo Windows 10/11 moderno, no solo el objetivo (OZ-33).** El único piso de versión vivía en la `LaunchCondition` del MSI y usaba la propiedad `WindowsBuild`, que en Windows 10/11 queda congelada en 9600 (valor de Win 8.1) porque `msiexec.exe` no declara Windows 10 en su manifiesto. `9600 >= 19045` es falso, así que **toda instalación limpia** en Windows moderno se bloqueaba —build 26200 (24H2) incluido—, justo lo contrario del propósito del guard. Reproducido en una máquina real build 26200: el MSI aborta; en la misma máquina, el registro `CurrentBuildNumber` y `RtlGetVersion` devuelven el 26200 correcto. El umbral de ADR-001 (19045) no se toca; se corrige la **detección**. El piso pasa a aplicarse en runtime al arrancar (`openzonda.baseline`), leyendo el build por una vía que no miente y comparándolo como entero, con el valor crudo registrado en el log; cubre además el modo portable, que no pasa por el instalador. Del MSI se retira la condición rota y se conserva solo el preflight de arquitectura x64. Decisión y encaje con ADR-001 en **ADR-009**.
- Los contratos de `import-linter` se ejecutaban en CI pero nada demostraba que rechazasen una violación real; un contrato mal escrito habría pasado en verde indefinidamente (ADR-003).
- Protección de rama en `main`: ambos checks de CI son obligatorios, lo que convierte la matriz en una barrera real en lugar de un informe.
- `SECURITY.md` afirmaba que las releases se publican con «artefactos firmados». Es falso: no hay certificado de firma de código y SmartScreen advertirá. Se documenta qué se publica en su lugar —SHA256SUMS y SBOM— y por qué.
- `BUILD.md` usaba `pwsh` en sus ejemplos, que es PowerShell 7 y no viene con Windows: quien siguiera la guía al pie de la letra se encontraba con «comando no reconocido» en el primer intento.
- El instalador empaquetaba los residuos de ejecución del bundle (`logs/`, `settings.json`). Con un `portable.marker` presente, toda instalación habría arrancado en modo portable. Se construye desde un staging limpio y el build falla si algún residuo sobrevive.

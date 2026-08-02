# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto sigue [Versionado Semántico](https://semver.org/lang/es/).

## [No publicado]

### Añadido
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

### Cambiado
- Toolchain del instalador: WiX v4 → **v5**. El elemento `<Files>`, que cosecha el árbol del bundle automáticamente, solo existe desde v5; en v4 habría que enumerar a mano las dependencias de Qt, una lista que se desincroniza en silencio al cambiar de versión.
- Rutas de aplicación y códigos de error adoptan el nombre definitivo del producto: `%APPDATA%\OpenZonda\`, prefijo `OZD-` para errores (no `OZ-`, que colisiona con las claves de tarjeta) y CLI de fixtures `oz-capture`. El renombrado nunca se había propagado al diseño §18 y §19.

### Corregido
- Los contratos de `import-linter` se ejecutaban en CI pero nada demostraba que rechazasen una violación real; un contrato mal escrito habría pasado en verde indefinidamente (ADR-003).
- Protección de rama en `main`: ambos checks de CI son obligatorios, lo que convierte la matriz en una barrera real en lugar de un informe.
- `SECURITY.md` afirmaba que las releases se publican con «artefactos firmados». Es falso: no hay certificado de firma de código y SmartScreen advertirá. Se documenta qué se publica en su lugar —SHA256SUMS y SBOM— y por qué.
- El instalador empaquetaba los residuos de ejecución del bundle (`logs/`, `settings.json`). Con un `portable.marker` presente, toda instalación habría arrancado en modo portable. Se construye desde un staging limpio y el build falla si algún residuo sobrevive.

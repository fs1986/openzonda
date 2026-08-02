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

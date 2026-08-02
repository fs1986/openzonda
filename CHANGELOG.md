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

### Corregido
- Los contratos de `import-linter` se ejecutaban en CI pero nada demostraba que rechazasen una violación real; un contrato mal escrito habría pasado en verde indefinidamente (ADR-003).
- Protección de rama en `main`: ambos checks de CI son obligatorios, lo que convierte la matriz en una barrera real en lugar de un informe.

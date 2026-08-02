# ADR-003 — Arquitectura hexagonal con verificación automática

- **Estado:** Aceptado
- **Fecha:** 2026-08-02
- **Decisores:** architect

## Contexto

Se busca portabilidad futura (macOS/Linux), testabilidad del núcleo sin radio real
y una frontera limpia para plugins.

## Decisión

Capas **UI → Application → Domain** con la infraestructura como **adaptadores de
ports**, verificadas por `import-linter` en CI:

- La UI nunca importa infraestructura ni APIs de Windows directamente.
- El dominio no importa nada externo salvo stdlib y NumPy.

## Consecuencias

- **Positivas:** núcleo testeable sin hardware; portabilidad; aislamiento de plugins.
- **Aceptadas:** más ceremonia inicial (ports/adapters) que un monolito.
- **Alternativas descartadas:** MVC monolítico (rápido al inicio, deuda estructural
  inmediata).

## Verificación

Contratos `import-linter` en `pyproject.toml` (`[tool.importlinter]`), ejecutados en
CI con `uv run lint-imports`. Un contrato roto **bloquea** el merge.

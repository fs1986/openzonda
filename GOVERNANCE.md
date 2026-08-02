# Gobernanza

OpenZonda es un proyecto open source (Apache-2.0) en fase temprana con un
**mantenedor fundador**. Este documento describe cómo se toman las decisiones
mientras el proyecto crece.

## Roles

- **Fundador / mantenedor:** aprueba merges, corta releases y ejecuta las
  validaciones que requieren hardware real (marcadas `[HW]`).
- **Contribuidores:** cualquiera que envíe PRs siguiendo `CONTRIBUTING.md`.

## Decisiones

- Las decisiones de arquitectura significativas se registran como **ADR** en `ADR/`.
- Un ADR aceptado es **inmutable**; cambiarlo requiere un ADR nuevo que lo supersede.
- Las "decisiones que no se cambian sin ADR" (§25 del diseño) son vinculantes.

## Releases

- Versionado semántico.
- Builds reproducibles con SBOM y artefactos firmados.
- El `CHANGELOG.md` se mantiene en cada cambio relevante.

## Código de conducta

Se espera un trato respetuoso y profesional en issues, PRs y discusiones. El
comportamiento abusivo puede resultar en la exclusión de la participación.

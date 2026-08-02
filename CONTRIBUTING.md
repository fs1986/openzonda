# Contribuir a OpenZonda

Gracias por tu interés. OpenZonda es Apache-2.0 y se desarrolla con una disciplina
deliberada: el núcleo RF es determinista y versionado, y la honestidad metrológica
es un invariante (ver [ADR-006](ADR/ADR-006-honestidad-metrologica.md)).

## Requisitos previos

- Python 3.13 y [uv](https://docs.astral.sh/uv/).
- `uv sync` para preparar el entorno.

## Flujo de trabajo

1. Una **rama por unidad de trabajo**: `feature/<slug>` (o `feature/openzonda-N-slug` si hay tarjeta).
2. **Tests primero**: el contrato se escribe fallando antes de implementar.
3. Antes de abrir PR, en verde localmente:

   ```bash
   uv run ruff check .
   uv run mypy packages/domain packages/rf_engine --strict
   uv run pytest
   uv run lint-imports
   ```

4. **Commits convencionales** con scope de paquete:
   `feat(wifi): ...`, `test(rf): ...`, `fix(persistence): ...`, `docs: ...`, `chore(ci): ...`.
5. Abre PR. La revisión valida capas (import-linter), tipos, tests y decisiones inmutables.

## Reglas no negociables

- **No** conviertas una estimación en medición sin marcarla como derivada.
  No estimes noise/SNR y lo presentes como observado.
- **No** accustombres la UI a una API de Windows: pasa por los ports.
- **Ninguna dependencia nueva** entra sin revisión de seguridad (lockfile con hashes vía `uv`).
- **No** cambies un modelo RF sin actualizar sus fixtures/golden y subir su versión.
- Cambiar una **decisión inmutable** (§25 del diseño / `ADR/`) requiere un **ADR nuevo**.

## DCO

Cada commit debe ir firmado con `Signed-off-by` (`git commit -s`), certificando el
[Developer Certificate of Origin](https://developercertificate.org/).

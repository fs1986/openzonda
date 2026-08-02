# ADR-006 — Honestidad metrológica como invariante de producto

- **Estado:** Aceptado
- **Fecha:** 2026-08-02
- **Decisores:** architect

## Contexto

Es el fundamento de la confianza profesional en una herramienta que no usa hardware
calibrado, y el principal diferenciador defendible frente a herramientas gratuitas
que colorean píxeles sin declarar su origen.

## Decisión

La clasificación **observado / derivado / estimado / predictivo** es parte del
**modelo de datos** (no solo de la UI), y su **degradación silenciosa está
prohibida**. En particular: no se estima noise/SNR y se presenta como observado.

## Consecuencias

- **Positivas:** trazabilidad total (cada píxel de un heatmap rastreable hasta sus
  muestras); credibilidad frente a usuarios profesionales.
- **Aceptadas:** más disciplina en el modelo y en los tests; a veces mostrar "no
  disponible" en vez de un número atractivo pero engañoso.
- **Alternativas descartadas:** clasificar la procedencia solo en la capa de UI
  (se pierde en export/import y es fácil de degradar en silencio).

## Verificación

Materializado en `packages/domain/measurement.py` (`Measured`, `Provenance`): el
valor viaja con su procedencia, es inmutable, y "mejorar" la procedencia lanza error.
Tests de contrato en `tests/unit/test_measurement.py`.

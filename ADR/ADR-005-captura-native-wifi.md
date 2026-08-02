# ADR-005 — Captura vía Native Wi-Fi API con parsing propio de IEs

- **Estado:** Aceptado
- **Fecha:** 2026-08-02
- **Decisores:** architect, dev-core

## Contexto

Se necesitan dBm reales y capacidades PHY reales para un análisis profesional, sin
depender de monitor mode (no usable con NICs consumer en Windows).

## Decisión

`WlanGetNetworkBssList` + **parser propio de Information Elements (IEs)** como fuente
primaria. `netsh` queda **solo para diagnóstico**.

## Consecuencias

- **Positivas:** dBm y capacidades reales; BSS Load (QBSS) habilita análisis de
  capacidad sin monitor mode.
- **Aceptadas:** mantener el parser de IEs al día frente a 802.11be y sucesores.
- **Alternativas descartadas:** scraping de `netsh` (frágil; su % no es dBm).

## Verificación

Fixtures de beacons/IEs con golden files; el parser se testea por regresión. `netsh`
no alimenta el modelo de datos, solo el diagnóstico exportable.

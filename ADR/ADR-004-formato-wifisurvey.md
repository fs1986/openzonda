# ADR-004 — Formato de proyecto `.wifisurvey` como ZIP autocontenido

- **Estado:** Aceptado
- **Fecha:** 2026-08-02
- **Decisores:** architect, dev-core

## Contexto

Un proyecto de survey debe ser portable entre equipos, compartible como un solo
archivo y robusto ante migraciones de esquema.

## Decisión

Contenedor **ZIP** con `manifest.json` + base **SQLite** + assets embebidos, con
**escritura atómica**.

## Consecuencias

- **Positivas:** portabilidad total; un archivo compartible; migraciones controladas.
- **Aceptadas:** coste de empaquetar/desempaquetar al abrir y guardar.
- **Alternativas descartadas:** carpeta suelta (frágil al mover/comprimir); SQLite
  único con blobs (los planos grandes degradan la DB).

## Verificación

El formato no se cambia sin migración de esquema versionada (regla inmutable). Tests
de round-trip (guardar/abrir) y de migración por versión.

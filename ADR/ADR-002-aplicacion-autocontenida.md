# ADR-002 — Aplicación autocontenida

- **Estado:** Aceptado
- **Fecha:** 2026-08-02
- **Decisores:** architect, devops

## Contexto

El usuario final no debe necesitar instalar Python, Node ni Qt. La variabilidad
del entorno del usuario es una fuente enorme de fallos de soporte.

## Decisión

Distribuir el runtime de Python y Qt **dentro del bundle** (PyInstaller onedir).

## Consecuencias

- **Positivas:** cero dependencias externas en el equipo del usuario; arranque predecible.
- **Aceptadas:** instalador de ~150–250 MB.
- **Alternativas descartadas:** onefile (desempaqueta a temp en cada arranque: lento,
  dispara antivirus y complica la firma).

## Verificación

Build reproducible en CI que produce un onedir firmable; smoke test de arranque en
una imagen limpia de Windows.

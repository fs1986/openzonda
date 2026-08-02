# ADR-001 — Baseline Windows

- **Estado:** Aceptado
- **Fecha:** 2026-08-02
- **Decisores:** architect

## Contexto

Hay que fijar la plataforma mínima soportada sin atarse a APIs exclusivas de una
versión concreta de Windows, para maximizar la base instalada.

## Decisión

Windows 10 22H2 x64 como **mínimo** (compatibilidad técnica, no garantía de
soporte del OS, cuyo ciclo general terminó en octubre de 2025) y Windows 11 x64
como plataforma **principal**. Toda API se comprueba por disponibilidad en
runtime, **nunca** por número de versión.

## Consecuencias

- **Positivas:** máxima base instalada; degradación explicable cuando falta una API.
- **Aceptadas:** dar soporte técnico a un OS fuera de soporte general (documentado).
- **Alternativas descartadas:** exigir Windows 11 (reduce alcance sin ganancia clara).

## Verificación

Detección de capacidades en runtime (`capabilities()` del scanner); sin comprobaciones
de versión hardcodeadas en el código.

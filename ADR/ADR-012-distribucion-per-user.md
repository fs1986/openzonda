# ADR-012 — Distribución solo per-user (MSI); modo portable fuera de alcance en alpha

- **Estado:** Propuesto (decisión de producto ya tomada por el PO; formalización pendiente de merge)
- **Fecha:** 2026-08-03
- **Decisores:** fundador (PO), architect
- **Relacionado:** acota ADR-002 y el diseño §18; difiere OZ-27.

## Contexto

El diseño §18 y ADR-002 contemplan dos modos de ejecución: **instalado** (per-user vía MSI) y
**portable** (detectado por `portable.marker`, con config/logs/datos junto al ejecutable). El
canal ZIP portable estaba planificado en OZ-27, con el argumento de servir a equipos
corporativos donde el usuario no puede instalar software.

En la etapa **alpha**, sostener el modo portable como caso de diseño cuesta más de lo que
aporta: multiplica los caminos de **rutas y almacenamiento** —dónde viven los `.wifisurvey`, los
working dirs de extracción del proyecto (OZ-8), los recientes, los settings— y obliga a probar
cada flujo en dos disposiciones distintas, sin usuarios reales que todavía lo pidan.

## Decisión

**El único escenario de distribución soportado en la alpha es la instalación per-user vía MSI.**

- El **modo portable queda fuera de alcance**: no se empaqueta, no se prueba y no se trata como
  caso soportado. OZ-27 (ZIP portable) se **difiere** (no es deuda pendiente de hacer).
- El diseño y el código nuevo **pueden asumir per-user**: no se ramifica `app_paths` ni la
  resolución del working dir por modo portable, no se añade detección de portable ni código
  defensivo para ese caso. Si una tarea futura *obliga* a considerarlo, se para y se consulta al
  PO antes de asumir.
- Lo que **ya** existe y lo tolera —la detección de `portable.marker` en `app_paths`, cubierta
  por el guard de baseline de ADR-009— **se conserva**. Esto **no** es «quitar el soporte
  portable del código»: es no empaquetarlo, no probarlo y no garantizarlo. Eliminarlo sería
  trabajo destructivo sin beneficio.

## Consecuencias

- **Positivas:** una sola disposición de rutas/almacenamiento que diseñar y validar `[HW]`; foco
  en el flujo per-user real; menos superficie de bugs.
- **Aceptadas:** se pospone el canal para equipos sin permisos de instalación (el argumento de
  OZ-27). El `portable.marker` en `app_paths` queda como código *tolerado pero no soportado*, que
  puede degradarse (bit-rot) sin que un test lo advierta, dado que deja de ejercitarse como caso.
- **Alternativas descartadas:**
  - *Implementar OZ-27 ahora* — coste alto en rutas/almacenamiento sin usuarios que lo pidan.
  - *Eliminar el soporte portable del código* — innecesario y destructivo; el runtime ya lo
    tolera y quitarlo no aporta.

## Si algún día se retoma

Se decide de nuevo, con contexto, resolviendo al menos: dónde viven los datos de proyecto
(`.wifisurvey`, working dirs de extracción de OZ-8 —hoy bajo `cache_dir`, que en portable caería
junto al ejecutable—, recientes) en portable vs per-user; el empaquetado del ZIP con
`portable.marker` y la verificación de que el MSI **nunca** lo lleva (OZ-27); y re-probar el
invariante de no-escape de rutas del modo portable.

## Verificación

- Revisión de PR: el código nuevo no introduce ramas por modo portable.
- OZ-27 queda **diferida** en Jira (fuera de alcance), no en el backlog activo.
- El guard de arranque (ADR-009) sigue cubriendo el arranque en cualquier modo tolerado.

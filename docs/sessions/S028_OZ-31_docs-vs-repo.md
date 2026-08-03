# S028 · OZ-31 · Alinear la documentación con el repositorio real

Fecha: 2026-08-02 · Duración: ~30 min · Fase: F0 (deuda) · Rama: `feature/oz-31-docs-vs-repo`

## Objetivo (copiado de la tarjeta)

Contrastar el plan operativo §2 y el diseño §7.3 contra el repo real y corregirlos. Barrido
de coherencia buscando otras afirmaciones que ya no se cumplan.

## Por qué esta tarjeta existe

Documentación que describe algo inexistente es **peor** que documentación ausente: quien la
lee toma decisiones sobre una realidad falsa, y no tiene forma de saber que lo está
haciendo.

Ya había provocado un coste medible. El DoD de OZ-1 exigía carpetas `retros/` y
`templates/` que nadie creó, en parte porque la ruta citada apuntaba a un repositorio que
no existía. Varias tarjetas del catálogo heredaron rutas igualmente inválidas.

## Qué se encontró

Los dos problemas de la tarjeta, y **cinco más** que aparecieron al barrer.

| # | Afirmación de la documentación | Realidad |
| --- | --- | --- |
| 1 | El plan §2 describe un repo separado `openzonda-docs` con su estructura | Nunca se creó; la documentación vive en el monorepo |
| 2 | El diseño §7.3 enumera los paquetes | Falta `apps/openzonda`, introducido por ADR-008 |
| 3 | El diseño §7.3 nombra la raíz `wifi-survey-ai/` | **El nombre anterior del producto.** Tercera instancia del renombrado sin propagar, tras las rutas de §18 y los códigos de error de §19 corregidos en OZ-3 |
| 4 | El catálogo cita las tarjetas como `OPENZONDA-N` | Las tarjetas reales son `OZ-N`. **40 ocurrencias** |
| 5 | La convención de ramas es `feature/OPENZONDA-N-slug` | Es `feature/oz-N-slug` |
| 6 | El checklist de arranque pide instalar **Node LTS** «para tooling» | El proyecto no usa nada de Node |
| 7 | El checklist pide crear el repo `openzonda-docs` bajo una org de GitHub | El repo vive en `github.com/fs1986/openzonda`; la org sigue sin crearse |

Los puntos 3 a 7 no estaban en el alcance de la tarjeta. Se corrigen porque son
exactamente el mismo defecto y separarlos habría producido otro PR sobre los mismos
archivos.

## Decisiones tomadas (y si requirieron ADR)

Ninguna requiere ADR. Los ADR **no se editan**: cuando el diseño contradice a un ADR se
corrige el diseño, nunca al revés.

### El repo documental separado se declara descartado, con su razón

No basta con borrar la mención: hay que decir **por qué** se descartó, o el mismo debate
vuelve dentro de seis meses.

El argumento original era poder compartir la documentación sin dar acceso al código en
fases tempranas. **Ese argumento dejó de aplicar** cuando el repositorio se hizo público
bajo Apache-2.0: ya no hay nada que proteger separando historias.

A cambio, el monorepo aporta algo que el repo separado impedía: un cambio de diseño y su
implementación viajan en el mismo commit y el mismo PR. Eso es justo lo que hace auditable
la cadena tarjeta → decisión → código.

Queda escrito como nota de corrección dentro del §2, fechada y con referencia a esta
tarjeta, en lugar de reescribir el texto como si nunca hubiera dicho otra cosa.

### Se explica por qué existen dos paquetes en `apps/`

`apps/openzonda` y `apps/desktop` separados parecen redundantes hasta que se entiende el
motivo. Tanto el diseño §7.3 como el README y `CLAUDE.md` lo explican ahora en una frase:
el contrato de capas prohíbe que la UI importe infraestructura, alguien tiene que instanciar
los adaptadores, y ese alguien vive fuera de la UI para que la prohibición no necesite
excepciones.

### `ADR/` se queda en la raíz

El §2 original lo situaba bajo `docs/`. Se documenta la ruta real y por qué no se mueve:
`CLAUDE.md` y varios documentos ya la referencian, y moverla rompería enlaces por un
beneficio cosmético.

### `hardware/HARDWARE.md` no se crea todavía

El §2 lo listaba. Se anota que llegará en F2, cuando existan NICs validadas que registrar.
Crear una carpeta vacía hoy solo añadiría otra ruta que documentar sin contenido.

## Artefactos

| Archivo | Cambio |
| --- | --- |
| `docs/design/plan-operativo-sesiones.md` | §2 reescrito con nota de corrección; 40 claves `OPENZONDA-N` → `OZ-N`; convención de ramas; checklist de arranque; rutas de session logs y retros |
| `docs/design/software-design-v0.2.md` | §7.3 con la estructura real, `apps/openzonda` y el porqué de la separación |
| `README.md` | Bloque de estructura actualizado; sección de desarrollo con los comandos que de verdad funcionan; estado F0 completada / F1 en curso |
| `CLAUDE.md` | Lista de paquetes y diagrama de capas con el composition root |

## DoD: checklist con estado real (no aspiracional)

Contrastado con `grep` sobre el repositorio, no de memoria:

- [x] **No queda ninguna referencia a `openzonda-docs` como repositorio separado** — las
      únicas ocurrencias restantes están en los session logs de S001 y S025, que describen
      históricamente lo que el documento decía **entonces**, y en la propia nota de
      corrección del §2. Las tres son correctas y deben permanecer.
- [x] **§7.3 enumera `apps/openzonda` y explica su papel** — con referencia a ADR-008.
- [x] **Cero ocurrencias de `OPENZONDA-<dígitos>`**, conservando `Key Jira: OPENZONDA`,
      que sí es correcto: la clave del proyecto.
- [x] **Un lector nuevo puede navegar del diseño al repositorio sin encontrar rutas
      inexistentes** — verificado recorriendo §7.3 y §2 contra `git ls-files`.

## Validaciones [HW] pendientes del fundador

Ninguna. Trabajo puramente documental.

## Desvíos / deuda registrada

- **La org de GitHub sigue sin crearse.** El checklist de arranque la pedía; el repositorio
  vive en la cuenta personal del fundador. No se convierte en tarjeta porque es una decisión
  suya, no trabajo pendiente; queda anotado en el propio checklist con su estado real.
- El renombrado del producto ha aparecido ya **tres veces** en sitios distintos (rutas de
  instalación, códigos de error, raíz del árbol del repositorio). Merece la pena asumir que
  quedan más instancias latentes y buscarlas al tocar cada documento, en lugar de esperar a
  tropezarse con ellas.

## Próxima sesión sugerida

**OZ-6 · S006 · Migraciones SQLite + repositorio**, continuación natural de OZ-5: las
entidades de dominio ya existen y necesitan dónde vivir.

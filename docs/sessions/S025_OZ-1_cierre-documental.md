# S025 · OZ-1 · Cierre real del DoD documental

Fecha: 2026-08-02 · Duración: ~30 min · Fase: F0 · Rama: `feature/oz-1-cierre-documental`

## Objetivo (copiado de la tarjeta)

Crear el repo documental según §2 del plan operativo, migrar diseño y planes a Markdown,
ADR-001..007 y templates.

El grueso se hizo en el bootstrap original (ver `S001_OZ-1_bootstrap-documental.md`). Esta
sesión cierra los cuatro puntos del DoD que quedaron sin cumplir.

## Cómo se detectó

Al cerrar OZ-23 se movió OZ-1 a *Done* junto con OZ-2, asumiendo que su trabajo estaba
completo por estar mergeado en `main`. Al contrastar el DoD línea por línea —la disciplina
que la propia OZ-23 acababa de recomendar— aparecieron cuatro puntos incumplidos. Se
revirtió la tarjeta a *In Progress*.

El cierre erróneo lo cometió el agente inmediatamente después de documentar ese mismo
patrón de fallo en OZ-2. Vale la pena registrarlo: enunciar una regla no basta para
aplicarla; hace falta ejecutarla como paso explícito, no como intención.

## Agentes utilizados y salidas clave

Sesión ejecutada por el agente principal sin delegar en subagentes, por decisión del
fundador. Roles cubiertos en secuencia: `architect` (ADR-007), `docs` (templates y logs),
`pm-jira` (transiciones y comentarios).

## Decisiones tomadas (y si requirieron ADR)

1. **ADR-007 se redacta con estado *Aceptado*, no *Propuesto*.** La decisión (binding vía
   `ctypes`) ya estaba tomada y razonada en `plan-implementacion.md` §4.1; el ADR la
   materializa, no la abre. Registrarla como *Propuesto* daría a entender que está en
   discusión cuando F2 ya depende de ella.
2. **Los logs de S001 y S002 se reconstruyen, marcados como reconstrucción.** Decisión
   explícita del fundador entre tres opciones. Cada log lleva un aviso en el encabezado
   indicando que no es registro contemporáneo, y marca como "no recuperable" lo que el
   historial de git no permite reconstruir —en particular qué subagentes actuaron y el
   razonamiento detrás de cada decisión. Un log reconstruido sirve para saber qué se hizo,
   no por qué; presentarlo como bitácora contemporánea sería fabricar evidencia.
3. **Se mantiene la división S001 / S002 pese a que no fueron dos sesiones.** El historial
   muestra un único commit de bootstrap (`d0351c5`, 45 archivos) y cinco commits en 21
   minutos, todos directos a `main`. La separación se conserva porque las tarjetas existen
   por separado, pero ambos logs lo declaran abiertamente en su nota previa.
4. **Los ADR se quedan en `ADR/` (raíz), no en `docs/adr/`.** El DoD nombra `adr/` dentro
   de la estructura documental, pero `CLAUDE.md` ya referencia la ruta actual. Mover el
   directorio rompería referencias por un beneficio puramente cosmético.

## Artefactos

Archivos nuevos:

- `ADR/ADR-007-binding-ctypes.md` — decisión de binding, derivada de §4.1 del plan de
  implementación, con las tres alternativas evaluadas y su verificación obligatoria
  (tests de `sizeof`/offsets por struct y fixtures grabados).
- `docs/templates/session-log.md`, `jira-card.md`, `retro.md`.
- `docs/retros/.gitkeep`.
- `docs/sessions/S001_OZ-1_bootstrap-documental.md` — reconstrucción.
- `docs/sessions/S002_OZ-2_monorepo.md` — reconstrucción.
- `docs/sessions/S025_OZ-1_cierre-documental.md` — este log.

Archivos modificados: `ADR/README.md` (índice), `CHANGELOG.md`.

## DoD: checklist con estado real (no aspiracional)

- [x] **Repo navegable con estructura `design/ adr/ sessions/ retros/ templates/`** —
      `docs/design/`, `ADR/`, `docs/sessions/`, `docs/retros/`, `docs/templates/`. Los ADR
      viven en la raíz, desvío documentado arriba.
- [x] **Diseño v0.2 legible en Markdown** — ya cumplido en el bootstrap.
- [x] **ADR-001..007 numerados** — ADR-007 creado y añadido al índice.
- [x] **Template de session log usado en S001** — template creado y aplicado a S001, S002 y
      a este log. Salvedad honesta: en S001 y S002 se aplicó retroactivamente, de modo que
      el punto se cumple en la letra pero no en el espíritu. No hay forma de arreglar eso
      a posteriori.

## Validaciones [HW] pendientes del fundador

Ninguna. Sesión puramente documental.

## Desvíos / deuda registrada

- **`pre-commit` sigue sin configurar.** La instrucción de arranque de S002 lo pedía, nunca
  se hizo, y no lo recoge ninguna tarjeta. Detectado al reconstruir el log de S002.
- **El plan operativo §2 describe un repo documental separado (`openzonda-docs`) que no
  existe**; la documentación vive en el monorepo. El documento debería corregirse para no
  seguir describiendo una estructura ficticia.
- **El session log de OZ-23 tiene una casilla desactualizada**: marca como pendiente "CI
  verde en Windows y Linux", que se cumplió minutos después al mergear el PR #1. Se corrige
  en esta rama.
- Las sesiones de limpieza que produjeron `7acd8ec` y `66f8383` tampoco tienen log ni
  tarjeta propia. Quedan absorbidas en el log reconstruido de S001.

## Próxima sesión sugerida

**OZ-3 · S003 · Walking skeleton Qt + PyInstaller [HW]**, siguiente del catálogo. OZ-24
(SBOM) puede intercalarse: es barata y no bloquea. Conviene incorporar `pre-commit` a
OZ-24 o abrirle tarjeta.

# S001 · OZ-1 · Bootstrap del repositorio documental

Fecha: 2026-08-02 · Duración: no recuperable · Fase: F0 · Rama: **ninguna** (commits directos a `main`)

> ⚠️ **Este log es una reconstrucción a posteriori, no un registro contemporáneo.**
> Se redactó el 2026-08-02 durante la sesión S025 (OZ-1), a partir del historial de git.
> La sesión original se ejecutó sin bitácora, incumpliendo la regla de oro del plan
> operativo §3. Todo lo que sigue está respaldado por commits verificables; **el
> razonamiento que llevó a cada decisión no quedó registrado y no es recuperable**, y así
> se marca donde corresponde. Un log reconstruido tiene menos valor probatorio que uno
> escrito en el momento: sirve para saber qué se hizo, no para saber por qué.

## Nota previa: S001 y S002 no fueron dos sesiones

El historial no muestra dos sesiones separadas. La totalidad del bootstrap —documentación
y monorepo -- entró en **un solo commit**, `d0351c5` (45 archivos, 2357 inserciones), y el
trabajo de F0 completo ocupa cinco commits en una ventana de 21 minutos (01:49 a 02:10),
todos directamente sobre `main` y sin rama de tarjeta.

La separación entre este log y el de S002 es, por tanto, **una atribución posterior por
alcance**, no un reflejo de dos bloques de trabajo distintos. Se mantiene la división
porque las tarjetas OZ-1 y OZ-2 existen por separado y el catálogo §5.1 las define así.

## Objetivo (copiado de la tarjeta)

Crear el repo documental según §2 del plan operativo. Convertir los `.docx` a Markdown
fiel, generar templates de session log / tarjeta / retro, y producir el session log de esta
misma sesión como primer ejemplo. Inicializar git con commits convencionales.

## Agentes utilizados y salidas clave

**No recuperable.** El historial no registra qué subagentes se invocaron. Los commits van
firmados como `Co-Authored-By: Claude Opus 4.8`, lo que indica ejecución con Claude Code,
pero no permite distinguir si `docs`, `architect` o `pm-jira` actuaron por separado o si la
sesión principal hizo todo el trabajo.

## Decisiones tomadas (y si requirieron ADR)

Ninguna decisión nueva: la sesión materializó decisiones ya tomadas en el diseño v0.2 §25
como ADR-001..006. Ninguna requirió ADR nuevo por definición, al ser transcripción.

Dos desviaciones respecto al plan que **no se registraron en su momento** y se documentan
aquí retroactivamente:

1. **No se creó un repo documental separado.** El plan operativo §2 preveía `openzonda-docs`
   como repositorio aparte. En la práctica la documentación vive dentro del monorepo, en
   `docs/`. El motivo no quedó registrado. La consecuencia es que la documentación y el
   código comparten historia y control de acceso, que es justo lo que §2 quería evitar; a
   cambio, se elimina el coste de mantener dos repos sincronizados. No requiere ADR
   (no toca ninguna decisión inmutable), pero **el plan operativo §2 sigue describiendo una
   estructura que no existe** y debería corregirse.
2. **Los ADR viven en `ADR/` en la raíz**, no en `docs/adr/` como indica la estructura del
   DoD. Se mantiene así porque `CLAUDE.md` ya referencia esa ruta.

## Artefactos

Commits (todos en `main`, sin PR):

| Commit | Fecha | Qué aportó a OZ-1 |
| --- | --- | --- |
| `d0351c5` | 01:49 | Diseño y planes convertidos a Markdown en `docs/design/`; ADR-001..006 en `ADR/`; gobernanza OSS (`LICENSE` Apache-2.0, `CONTRIBUTING`, `SECURITY`, `GOVERNANCE`) |
| `7acd8ec` | 02:05 | Retirada de menciones a marcas de terceros del repo público; `.docx` originales fuera del control de versiones por contener metadatos personales (pasan a `.private/`, ignorado). El Markdown queda como única fuente de verdad |
| `66f8383` | 02:10 | Convenio de tarjetas alineado a `OZ-N` y ramas `feature/oz-N-slug` |

## DoD: checklist con estado real

Contrastado contra el repositorio el 2026-08-02, durante S025.

- [x] **Diseño v0.2 legible en Markdown** — `docs/design/software-design-v0.2.md`,
      `plan-implementacion.md`, `plan-operativo-sesiones.md`.
- [ ] **Repo navegable con estructura `design/ adr/ sessions/ retros/ templates/`** —
      incumplido en su momento: faltaban `retros/` y `templates/`. Cerrado en S025.
- [ ] **ADR-001..007 numerados** — incumplido en su momento: solo llegaban hasta ADR-006.
      Faltaba ADR-007 (binding `ctypes`), cuya decisión estaba redactada en
      `plan-implementacion.md` §4.1 pero nunca se materializó como ADR. Cerrado en S025.
- [ ] **Template de session log usado en S001** — incumplido en su momento: no existía ni
      el template ni este log. Cerrado en S025, con la salvedad de que este log es una
      reconstrucción y no cumple el espíritu del punto, solo su letra.

## Validaciones [HW] pendientes del fundador

Ninguna. Sesión puramente documental.

## Desvíos / deuda registrada

- La tarjeta OZ-1 quedó en *In Progress* y su DoD nunca se contrastó. Se detectó el
  2026-08-02, durante el cierre de OZ-23.
- Trabajo sin rama de tarjeta ni PR, contra la regla de `CLAUDE.md` "una rama por tarjeta".
- Sin session log, contra la regla de oro del §3.
- El plan operativo §2 describe un repo documental separado que no existe. Pendiente de
  corregir el documento.

## Próxima sesión sugerida

Registrado a posteriori: la continuación real fue S002 (monorepo y tooling), ejecutada de
hecho en el mismo bloque de trabajo.

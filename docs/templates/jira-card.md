# Template de tarjeta Jira (proyecto OPENZONDA, key `OZ`)

**Título:** `F#.# · S0NN · <verbo + entregable>`

**Labels:** fase (`F0`..`F9`) · tipo (`feat` / `infra` / `docs` / `qa` / `hw`) ·
`hw-validation` si requiere validación física del fundador.

---

## Contexto

<Qué fuerza esta tarjeta. Si nace de deuda detectada en otra tarjeta, enlazarla y decir
qué punto de su DoD quedó sin cerrar.>

## Alcance

<Lista de entregables concretos.>

<Y explícitamente lo que queda **fuera** de alcance, con quién lo decidió. Un alcance que
no dice qué excluye se expande solo.>

## Criterios de aceptación

<Una casilla por criterio, redactada de forma **verificable**: alguien ajeno a la sesión
debe poder ejecutar algo y saber si se cumple. "Funciona bien" no es un criterio.>

- [ ] <criterio verificable>
- [ ] Session log en `docs/sessions/` y CHANGELOG actualizado.

## Dependencias

<Tarjetas que deben estar cerradas antes. Enlazarlas en Jira, no solo nombrarlas.>

## Decisiones inmutables

<Cuál de las nueve decisiones inmutables de `CLAUDE.md` podría verse afectada y por qué no
lo está. Si alguna sí lo está, la tarjeta no arranca sin ADR nuevo aprobado.>

---

## Comentario de cierre (lo publica pm-jira)

```
VERDICT: PASS | FAIL

PR #N mergeado en `main` (<sha>). <Resultado real de CI, con números.>

<Qué se cerró, punto por punto del DoD.>

<Deuda registrada.>

Session log: docs/sessions/S0NN_OZ-N_slug.md
```

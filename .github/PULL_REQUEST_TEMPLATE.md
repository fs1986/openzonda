<!--
  Gracias por contribuir. Rellena lo que aplique y borra lo que no.
  Si el PR corresponde a una tarjeta, enlázala.
-->

## Qué cambia y por qué

<!-- El "por qué" importa más que el "qué": el diff ya cuenta el qué. -->

## Cómo se ha verificado

<!--
  Comandos ejecutados y su resultado real, no "debería funcionar".
  Si algo no se ha podido probar, dilo: es información útil, no una falta.
-->

```
uv run ruff check .
uv run mypy packages/domain packages/rf_engine --strict
uv run lint-imports
uv run pytest
```

## Checklist

- [ ] Los tests cubren el comportamiento nuevo, y **fallarían** si se revirtiera el cambio.
- [ ] `lint-imports` en verde: no se ha roto ninguna barrera entre capas.
- [ ] Si se añade una dependencia, está en `uv.lock` y se justifica por qué es necesaria.
- [ ] `CHANGELOG.md` actualizado si el cambio es visible para quien usa OpenZonda.

## Decisiones inmutables

<!--
  Ver la lista en CLAUDE.md. Si alguna se ve afectada, el PR necesita un ADR aprobado
  antes de poder mergearse. Si ninguna lo está, basta con decirlo.
-->

- [ ] Ninguna decisión inmutable se ve afectada.

## Honestidad metrológica

<!--
  Solo si el cambio toca datos de medición. ADR-006 exige que la clasificación
  observado / derivado / estimado / predictivo viva en el modelo de datos y nunca se
  degrade en silencio.
-->

- [ ] No aplica: el cambio no toca datos de medición.
- [ ] Aplica, y la procedencia de cada dato se conserva explícitamente.

## Validación en hardware

<!-- Marca esto si el cambio necesita una NIC real, una VM o un survey de campo. -->

- [ ] No requiere validación física.
- [ ] Requiere validación física: <!-- describe qué hay que comprobar y con qué -->

# ADR-014 — Cancelación lógica del I/O de proyecto (no abortar a mitad)

- **Estado:** Propuesto (decisión de OZ-34; formalización pendiente de merge)
- **Fecha:** 2026-08-03
- **Decisores:** architect
- **Relacionado:** OZ-34 (worker de I/O); límite registrado como sub-deuda **OZ-37**.

## Contexto

OZ-34 movió el I/O de abrir/guardar a un worker (`TaskExecutor` / `QtTaskExecutor`). El DoD
pedía «cancelación cooperativa (diseño §7.2): cerrar un proyecto cancela trabajos pendientes».
Hay dos maneras de cumplirlo:

1. **Cancelación lógica**: la operación sigue corriendo en el worker, pero su **resultado se
   descarta** si quedó obsoleta (el usuario cerró o cambió de proyecto).
2. **Cancelación real del I/O**: abortar el `read_container`/`write_container` a mitad.

La opción 2 exige que esas funciones chequeen un token de cancelación **dentro de sus loops**
de extracción/escritura. Eso obliga a re-tocar `packages/persistence/container.py`, que es la
superficie más endurecida del producto (OZ-7, escalado a opus): escritura atómica con
kill-test, y apertura defensiva contra zip-bomb, path-traversal, enlaces y hashes. Meter mano
ahí por una ganancia marginal en alpha es un mal negocio de riesgo.

## Decisión

**Cancelación lógica por generación.** Cada operación async lleva una *generación*; si el
usuario cierra o cambia de proyecto, la generación avanza y el resultado que llega tarde se
**descarta**, limpiando el working dir que hubiera abierto. El I/O en curso **no se aborta**:
termina por dentro y su efecto se ignora.

Con archivos que hoy tardan menos de ~1 s, descartar el resultado cubre por completo el caso
de uso (cerrar cancela que se aplique) sin tocar el contenedor.

## Consecuencias

- **Positivas:** no se toca el código endurecido de OZ-7; implementación simple y verificable
  headless (executor diferido); ningún hilo se mata de forma insegura.
- **Aceptadas:** una operación grande (decenas/cientos de MB) sigue corriendo en el worker
  aunque el usuario cancele, desperdiciando CPU/disco hasta que termina y se limpia el working
  dir. Con planos grandes (F1.5+) esto se vuelve perceptible. **Límite registrado como sub-deuda
  OZ-37**, con disparador explícito (planos de decenas de MB o feedback de usuario).
- **Alternativas descartadas:**
  - *Cancelación cooperativa del I/O* (opción 2): re-toca `container.py` hostil-endurecido;
    riesgo alto para el alpha. Es lo que hará OZ-37 si el disparador se cumple.
  - *Matar el hilo del worker*: inseguro (deja archivos a medias, corrompe estado); descartado.

## Verificación

- `tests/unit/test_project_service.py`: con un executor diferido, cerrar durante una apertura
  descarta el resultado y limpia el working dir; abrir otro mientras abre deja el último, no el
  obsoleto.
- El destino de un guardado sigue protegido por la escritura atómica del contenedor (OZ-7),
  independientemente de la cancelación.

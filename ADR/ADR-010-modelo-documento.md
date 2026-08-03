# ADR-010 — Proyecto como documento (extraer / re-empaquetar)

- **Estado:** Propuesto (pendiente de aceptación del fundador en el PR de OZ-8)
- **Fecha:** 2026-08-03
- **Decisores:** architect
- **Relacionado:** implementa la persistencia de ADR-004 (`.wifisurvey`) en el ciclo de vida
  de F1.4; motivado por OZ-8.

## Contexto

OZ-8 integra por primera vez el dominio, el repositorio SQLite (OZ-6) y el contenedor
`.wifisurvey` (OZ-7). Hay que decidir **qué es un proyecto abierto**. Dos modelos:

1. **Documento**: el `.wifisurvey` *es* el archivo del usuario. Abrir lo extrae a un
   directorio de trabajo temporal; guardar re-empaqueta atómicamente sobre el mismo archivo.
2. **Base viva**: una base SQLite persistente por proyecto en el perfil del usuario; el
   `.wifisurvey` es solo un formato de export/import.

El diseño §14.1 define el guardado **atómico** del contenedor (temporal + `fsync` + rename) y
§24 exige un **round-trip verificado por hash**. El modelo mental del usuario —y de un
formato pensado para compartirse por correo— es «el archivo es el proyecto».

## Decisión

**Modelo documento.**

- **Abrir** = `read_container` a un working dir bajo `cache_dir/projects/` → `open_database`
  sobre la base extraída → `repo.load`.
- **Guardar** = `repo.save` → `PRAGMA wal_checkpoint(TRUNCATE)` (para empaquetar un `.sqlite`
  de un solo archivo, sin `-wal`) → `write_container` **atómico** sobre el destino.
- **Sin autosave en la alpha**: el guardado es explícito. Un survey es trabajo de campo; el
  usuario decide cuándo lo confía a disco.
- Los working dirs de sesiones muertas se **barren al arrancar**, de forma conservadora: cada
  uno mantiene abierto un `session.lock` y no se toca un directorio cuyo lock esté vivo (otra
  instancia). Ver `persistence/project_store.py`.

## Consecuencias

- **Positivas:** encaja con el guardado atómico de §14.1 y el round-trip de §24; el archivo
  es autocontenido y trasladable; un crash a mitad de guardado **nunca** destruye el original
  (temporal + `os.replace`), verificado con un kill-test.
- **Aceptadas:** extraer/re-empaquetar cuesta I/O proporcional al tamaño del proyecto. Con
  payloads grandes (plano, captura) hay que moverlo a un worker con cancelación —**deuda
  OZ-34**—; el servicio ya está diseñado para que ese cambio no lo afecte. Quedan working
  dirs temporales en `cache_dir` que hay que barrer. WAL obliga a un checkpoint antes de
  empaquetar.
- **Alternativas descartadas:** *base viva persistente* — añade estado en el perfil, el
  `.wifisurvey` deja de ser la verdad, el *dirty* se vuelve ambiguo y contradice el modelo
  «archivo = documento».

## Verificación

- `tests/integration/test_project_store.py`: round-trip por igualdad de datos de dominio y
  kill-test del guardado (atómico).
- `[HW]` El flujo desde el ejecutable congelado ejercita por primera vez `importlib.resources`
  (migraciones empaquetadas) en frozen — verificación diferida heredada de OZ-6/OZ-7.

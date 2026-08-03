# S007 · OZ-7 · Contenedor `.wifisurvey` ★opus

Fecha: 2026-08-02 · Duración: ~1 h 30 min · Fase: F1 · Rama: `feature/oz-7-contenedor-wifisurvey`

★ Sesión marcada para escalado a opus por su superficie hostil y por la atomicidad.

## Objetivo (copiado de la tarjeta)

Implementa el contenedor de proyecto: guardar = temp+fsync+rename; abrir valida rutas,
tamaños y manifest. qa: test de round-trip por hash y test que mata el proceso durante el
guardado. security: fixtures de zip bomb y path traversal que deben rechazarse.

## DoD: contrastado ANTES de cerrar

La tarjeta declara **3 puntos de DoD**; el PO añadió **4 puntos de atención**. Los siete se
tratan como vinculantes y se verifican con comando y resultado.

| # | Punto | Comando | Resultado |
| --- | --- | --- | --- |
| 1 | **DoD** Round-trip idéntico por hash | `pytest -k "RoundTrip or Determinismo"` | **12 passed** |
| 2 | **DoD** Kill-test sin corrupción | `pytest -k KillTest` | **2 passed** |
| 3 | **DoD** 3 fixtures hostiles rechazados | `pytest tests/integration/test_container_hostile.py` | **30 passed** — 8 familias de ataque, no 3 |
| 4 | **PO** Escritura atómica de verdad | `pytest -k EscrituraAtomica` | **3 passed** |
| 5 | **PO** Validar antes de confiar; techo de bomba | incluido en el 3 | **passed** |
| 6 | **PO** Fallo limpio que distingue el caso | `pytest -k Taxonomia` | **6 passed** |
| 7 | **PO** Fixture hostil con test de control | `pytest -k control` | **3 passed** |

Gate completo antes de abrir el PR:

```
uv run ruff check .                      All checks passed!
uv run ruff format --check .             88 files already formatted
uv run mypy packages/domain --strict     Success: no issues found in 8 source files
uv run lint-imports                      Contracts: 4 kept, 0 broken
uv run pytest                            204 passed
```

Tests: 157 → **204**.

## Tres hallazgos: defensas que no defendían

El valor de esta sesión no está en el código escrito sino en tres cosas que **parecían
funcionar y no funcionaban**. Las tres salieron de ejecutar sondas contra el comportamiento
real de `zipfile`, no de razonar sobre él.

### 1. El fixture de traversal salía saneado antes de llegar al lector

En Windows, `zipfile.ZipInfo("a\\b.txt")` convierte la barra invertida en barra normal al
construirse. Un ZIP hostil escrito de la forma obvia se guardaba ya inofensivo, y el test
habría pasado sin probar nada.

Corregido con un ayudante que asigna `info.filename` **después** de construir el `ZipInfo`.
Un atacante construye el archivo en la máquina que quiera, con los bytes que quiera; el
fixture tiene que poder hacer lo mismo.

### 2. La comprobación de barra invertida es código muerto por esa vía

Sonda directa:

```
al escribir: ['carpeta\\con\\backslash.txt', '..\\padre.txt', 'C:\\unidad.txt']
al leer:     ['carpeta/con/backslash.txt',   '../padre.txt',  'C:/unidad.txt']
```

**`zipfile` normaliza `\` a `/` al leer el directorio central.** La regla de la barra
invertida no puede dispararse nunca a través de un ZIP. Los casos peligrosos los atrapan
otras reglas —la de `..` y la de letra de unidad—, así que la protección real existía, pero
no era la que yo creía.

Dos consecuencias, ambas aplicadas:

- Se retiró de la lista de variantes el caso `carpeta\con\backslash.txt`: tras la
  normalización es una ruta anidada legítima, no un ataque. Mantenerlo habría sido un test
  que exige rechazar algo inofensivo.
- La regla se conserva —vale para cualquier otro origen de nombres— pero se **expuso el
  validador como función pública** y se probó directamente. Una defensa que nadie ejercita
  es una que nadie sabe si funciona.

### 3. `a//b.txt` pasaba, y era explotable

`PurePosixPath` **colapsa las barras duplicadas**, así que la comprobación de «componentes
vacíos» tampoco podía dispararse.

Y no era inocuo: `a/b` y `a//b` son cadenas **distintas** —esquivan el control de nombres
duplicados— pero designan el **mismo archivo** en disco. Un contenedor podía declarar dos
entradas que se pisan, y la verificada por hash no ser la extraída.

Sustituido por una regla de **forma canónica**: si `PurePosixPath(nombre).as_posix()` no es
idéntico al nombre recibido, se rechaza. Cubre de una vez la doble barra, el `./` y la
barra final, en lugar de enumerar casos y dejarse alguno.

## Decisiones tomadas (y si requirieron ADR)

Ninguna requiere ADR: ADR-004 ya fija el formato.

### La regla que gobierna el lector

**Nada de lo que dice el archivo se cree hasta haberlo comprobado leyendo.**

En concreto, `ZipInfo.file_size` lo escribe quien construyó el archivo. Se usa solo como
rechazo temprano barato; el límite real se aplica **contando los bytes que salen del
descompresor**, y se aborta a mitad. Llegar al final para entonces decir que era demasiado
grande ya habría llenado el disco, que es justo lo que busca una bomba.

### Orden de las comprobaciones

No es casual: primero lo que se puede saber **sin descomprimir nada** (firma, listado,
nombres, duplicados, número de entradas), luego el manifest con su techo, y solo al final
el contenido. El manifest se lee antes que nada, así que sin techo propio sería el primer
vector.

### Doble barrera en las rutas

Se valida el nombre **y** se comprueba el resultado de unirlo al destino. Si la primera
regla se dejara un caso, la segunda lo atrapa. Es la lección de los tres hallazgos de
arriba: una sola capa de validación de rutas es demasiado fácil de eludir por un camino que
no se anticipó.

### Suelo para el límite de ratio

El ratio de compresión solo se aplica por encima de 8 MiB. Una base SQLite recién creada es
casi toda ceros y comprime muchísimo sin ser una amenaza; una bomba, para hacer daño, tiene
que ser grande **y** comprimir mucho. Sin este suelo el lector rechazaría proyectos
legítimos, y una defensa que da falsos positivos acaba desactivada.

### Cuatro tipos de error, no uno

`NotAContainerError`, `ContainerTooNewError`, `CorruptContainerError` y
`HostileContainerError`. La acción del usuario es distinta en cada caso: buscar otro
archivo, actualizar OpenZonda, intentar una copia de seguridad, o desconfiar de quien se lo
envió.

`HostileContainerError` se separa de «corrupto» a propósito: un archivo corrupto es un
accidente y sugerir un reintento es razonable; el otro caso significa que **alguien lo
construyó así**, y el mensaje no debe invitar a insistir.

### Escritura determinista

Fecha fija en las entradas y orden estable. Dos guardados del mismo contenido producen
**bytes idénticos**. Sin esto, el reloj se filtraría en cada guardado y las copias
incrementales y los diffs dejarían de servir aunque no hubiera cambiado nada.

### Una apertura fallida no deja nada detrás

Se anota lo escrito para poder deshacerlo, en lugar de borrar el directorio de destino
entero: puede ser un espacio de trabajo del llamante con contenido previo. Hay un test que
comprueba justamente que lo preexistente sobrevive.

### Barrido de temporales abandonados

Un proceso muerto no puede limpiar tras de sí, así que lo hace el siguiente guardado
correcto, y solo sobre los temporales de **ese** destino.

## Sobre el kill-test: qué prueba y qué no

Se mata el proceso con `os._exit`, que termina de inmediato sin ejecutar `finally`, ni
`atexit`, ni vaciar buffers de Python. Es lo más cercano a un `kill -9` que se puede
provocar de forma determinista, y ataca el instante peor: entre el `fsync` del temporal y
el `rename`.

**No simula un corte de energía.** Ahí se perderían además las escrituras que el sistema
operativo aún no ha bajado a disco, y de eso protege el `fsync`, no este test. La
afirmación honesta es: *ante una muerte abrupta del proceso, el proyecto anterior sobrevive
intacto y sigue siendo legible*, verificado por hash y reabriéndolo.

## Artefactos

| Archivo | Contenido |
| --- | --- |
| `packages/persistence/container.py` | `write_container`, `read_container`, `require_safe_entry_name`, `ContainerLimits`, cuatro tipos de error |
| `tests/integration/test_container.py` | Round-trip, determinismo, atomicidad, kill-test, taxonomía |
| `tests/integration/test_container_hostile.py` | 8 familias de ataque con sus controles |

Familias hostiles cubiertas: path traversal (6 variantes), zip bomb por ratio, tamaño
mentido en el encabezado, exceso de entradas, nombres duplicados, enlaces simbólicos,
manifest desproporcionado, y nombres degenerados a nivel de validador.

## Validaciones [HW] pendientes del fundador

Ninguna. El contenedor no depende de hardware.

## Desvíos / deuda registrada

- **El contenedor todavía no se conecta con el repositorio de OZ-6.** `write_container`
  recibe la ruta de una base ya construida; quién la construye y cuándo se guarda es
  trabajo de la shell de UI (F1.4). El pegamento aún no existe.
- **`exports/` del diseño §14.1 no se produce**, solo se toleraría al leer. Llega en F4 con
  el reporting.
- **El kill-test no cubre el corte de energía**, como se explica arriba.
- Verificación diferida heredada de OZ-6: el camino de `importlib.resources` desde el
  ejecutable congelado sigue sin ejercitarse hasta F1.4.

## Próxima sesión sugerida

**OZ-8 · S008 · Shell UI: proyectos [HW]**, que es donde el contenedor, el repositorio y el
dominio se juntan por primera vez y donde se cerrarán las dos verificaciones diferidas.

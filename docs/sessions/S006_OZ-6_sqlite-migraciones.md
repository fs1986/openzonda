# S006 · OZ-6 · Migraciones SQLite + repositorio

Fecha: 2026-08-02 · Duración: ~1 h · Fase: F1 · Rama: `feature/oz-6-sqlite-migraciones`

## Objetivo (copiado de la tarjeta)

Runner de migraciones minimalista y esquema 0001 según §8.2 del diseño. Tests: migración
parcial hace rollback; DB de user_version futura falla con mensaje claro; `trusted_schema=OFF`
y `foreign_keys=ON` verificados.

## DoD: contrastado ANTES de cerrar, punto por punto

> Regla de proceso adoptada tras OZ-5: la verificación va **antes** de la transición de
> estado, con el comando y su resultado escritos aquí. En OZ-5 se cerró primero y se
> verificó después; salió bien por suerte, no por método.

La tarjeta declara **2 puntos de DoD**, y su instrucción de arranque añade **3 requisitos de
test**. Se tratan los cinco como vinculantes.

| # | Punto | Comando | Resultado |
| --- | --- | --- | --- |
| 1 | Suite de persistencia verde | `uv run pytest tests/integration/test_migrations.py tests/integration/test_project_repository.py` | **31 passed** |
| 2 | Apertura defensiva demostrada con fixture hostil | `uv run pytest -k "EsquemaHostil or AperturaDefensiva"` | **8 passed** |
| 3 | Migración parcial hace rollback | `uv run pytest -k Atomicidad` | **3 passed** |
| 4 | `user_version` futura falla con mensaje claro | `uv run pytest -k ForwardIncompatible` | **2 passed** |
| 5 | `trusted_schema=OFF` y `foreign_keys=ON` verificados | Incluido en el punto 2 | **passed** |

Gate completo, ejecutado antes de abrir el PR:

```
uv run ruff check .                      All checks passed!
uv run ruff format --check .             84 files already formatted
uv run mypy packages/domain --strict     Success: no issues found in 8 source files
uv run lint-imports                      Contracts: 4 kept, 0 broken
uv run pytest                            157 passed
```

Tests: 126 → **157**.

## Un test que pasaba por la razón equivocada

El primer fixture hostil creaba una vista con `load_extension('malicioso')` y comprobaba que
consultarla fallaba con `trusted_schema=OFF`. **Pasaba, y no probaba nada.**

Se verificó ejecutando el mismo caso con el PRAGMA encendido y apagado:

```
trusted_schema=ON:  OperationalError: unsafe use of load_extension()
trusted_schema=OFF: OperationalError: unsafe use of load_extension()
```

Python bloquea `load_extension` siempre, porque no habilita la carga de extensiones. El
test habría seguido verde aunque alguien borrara el PRAGMA.

**Fixture corregido**: una vista que invoca una función registrada por la aplicación
(`create_function`). Ahí sí hay diferencia observable:

```
trusted_schema=ON:  SE EJECUTO -> [('ok',)], efectos=['x']
trusted_schema=OFF: BLOQUEADA -> OperationalError: unsafe use de la función
```

Y modela mejor la amenaza real de §17.3: el atacante no ejecuta código directamente, pero
**controla el esquema** del `.wifisurvey` que te envía. Si la aplicación registra funciones
propias —y OpenZonda las registrará— una vista puede invocarlas en cuanto alguien consulte.

Los dos tests se dejan **como par**: el primero demuestra que el ataque funciona sin la
mitigación; el segundo, que con ella no. Si el de control dejara de pasar, el otro habría
dejado de probar algo y el par lo delata.

## Decisiones tomadas (y si requirieron ADR)

Ninguna requiere ADR.

### 1. Una transacción por migración, no una global

Si la migración 5 falla, las 1–4 están confirmadas y `user_version` vale 4: reabrir el
proyecto reintenta solo desde la 5. Con una transacción global, un fallo tardío obligaría a
rehacer todo el trabajo en cada intento, y sobre una base grande eso convierte un error
recuperable en uno que bloquea el proyecto.

### 2. El control de transacción va DENTRO del script SQL

Encontrado al ver fallar el test de rollback, no razonando: `executescript()` hace un
**COMMIT implícito** de cualquier transacción pendiente antes de empezar. Un `BEGIN`
externo queda anulado y la migración corre sin protección.

La corrección es construir el script como `BEGIN; <sql>; PRAGMA user_version = N; COMMIT;`
y hacer `ROLLBACK` guardado por `connection.in_transaction` si algo falla. Se abre la
conexión con `isolation_level=None` para que el driver no intercale transacciones propias.

Es exactamente el tipo de fallo que un test escrito después de la implementación no habría
detectado: el código *parecía* transaccional.

### 3. Sin migraciones hacia atrás, a propósito

Un downgrade sobre datos de campo es pérdida de información silenciosa. El diseño §8.2
prefiere fallar al abrir, y eso hace `SchemaTooNewError`. El mensaje dice **ambas**
versiones —la que trae el archivo y la que entendemos— porque «versión incompatible» a
secas no le dice al usuario si debe actualizar OpenZonda o pedir el archivo en otro formato.

Y no se toca el archivo: hay un test que lo comprueba comparando las tablas antes y después
del intento fallido.

### 4. Numeración lineal exigida

`discover_migrations()` rechaza huecos y duplicados. Un hueco casi siempre significa que un
merge perdió una migración, y detectarlo al abrir es infinitamente mejor que descubrirlo
cuando una tabla no existe en producción.

### 5. `save()` reemplaza, no acumula

El agregado en memoria es la verdad: quitar un sitio y guardar debe eliminarlo del archivo.
Se implementa borrando el proyecto y dejando que `ON DELETE CASCADE` limpie, todo dentro de
una transacción. Acumular produciría el fallo más difícil de diagnosticar de un
repositorio: **datos que reaparecen tras haberlos borrado**.

### 6. La calibración se embebe en `floor_plan`, con `CHECK`

Cuatro columnas nullable con un `CHECK` que exige que estén **todas** presentes o **todas**
ausentes. `NULL` significa «plano sin calibrar», que es un estado legítimo y distinto de una
escala de cero — la misma distinción que el dominio hace con `Unavailable`. Sin el `CHECK`,
una fila a medias produciría una escala inventada.

### 7. Tablas `STRICT`

SQLite acepta por defecto un texto en una columna `INTEGER`. Con `STRICT` no. Para un
producto cuyo invariante es la honestidad del dato, aceptar tipos arbitrarios en el
almacenamiento sería contradictorio.

## Un fallo latente cerrado de paso

Las migraciones son archivos `.sql`, no módulos: **el análisis de imports de PyInstaller no
las ve**. El bundle se habría construido sin ellas y `discover_migrations()` habría fallado
al abrir el primer proyecto — ya en la máquina del usuario, no en CI.

Se añadieron como `datas` al spec y se verificó reconstruyendo:

```
_internal\persistence\migrations\0001_init.sql
```

Salvedad honesta: se verificó que el archivo **está** en la ruta donde `importlib.resources`
lo buscará. El camino completo —abrir un proyecto desde el ejecutable congelado— no se
ejercita hasta que la UI lo haga, en F1.4.

## Artefactos

| Archivo | Contenido |
| --- | --- |
| `packages/persistence/migrations/0001_init.sql` | Esquema §8.2: project, site, floor_plan, floor, adapter_profile, survey_session, bss, measurement, más los índices |
| `packages/persistence/migrations/__init__.py` | `Migration`, `discover_migrations`, `apply_migrations` |
| `packages/persistence/database.py` | `open_database` con PRAGMAs defensivos, `SchemaTooNewError`, `CorruptDatabaseError` |
| `packages/persistence/project_repository.py` | `SQLiteProjectRepository` |
| `packages/application/projects.py` | Port `ProjectRepository` |
| `packaging/openzonda.spec` | Migraciones incluidas como datos del bundle |

## Validaciones [HW] pendientes del fundador

Ninguna. Persistencia pura, sin dependencia de hardware.

## Desvíos / deuda registrada

- **El esquema declara tablas que todavía no usa nadie**: `survey_session`, `measurement`,
  `bss` y `adapter_profile` existen en 0001 porque el diseño §8.2 las especifica y porque
  las claves foráneas de `measurement` no tienen sentido sin ellas. Sus repositorios llegan
  en OZ-18. Alternativa descartada: crearlas en una migración posterior, lo que habría
  dejado el esquema inicial incompleto respecto al documento de diseño.
- **`FloorPlan` no tiene identidad en el dominio** pero sí una fila con `id` técnico en la
  base. Es una fuga menor del modelo relacional hacia el almacenamiento, contenida dentro
  del adaptador: el dominio no se entera.
- **El round-trip no cubre `SurveySession`** — depende de OZ-18.
- La ejecución real de migraciones **desde el bundle congelado** no se ejercita hasta F1.4.

## Próxima sesión sugerida

**OZ-7 · S007 · Contenedor `.wifisurvey` ★opus**, que es la continuación natural: la base de
datos ya existe y necesita empaquetarse en el contenedor ZIP con escritura atómica y
validación anti path-traversal. Está marcada para escalar a opus por su superficie hostil.

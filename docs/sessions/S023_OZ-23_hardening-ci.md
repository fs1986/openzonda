# S023 · OZ-23 · Hardening de CI: lockfile con hashes, matriz Windows y test de contratos de capas

Fecha: 2026-08-02 · Duración: ~1 h · Fase: F0 · Rama: `feature/oz-23-hardening-ci`

## Objetivo (copiado de la tarjeta)

Cerrar los tres gaps detectados al revisar OZ-2 (Monorepo + calidad + CI):

1. Sin `uv.lock` versionado → builds no reproducibles, sin base para el SBOM.
2. CI solo en `ubuntu-latest` → el SO objetivo del producto nunca se ejercita.
3. Los contratos de capas no están probados → `lint-imports` corre, pero nada
   demuestra que un import ilegal rompa el build.

Fuera de alcance por decisión explícita del fundador: generación de SBOM en CI.

## Hallazgo de partida: esto es el DoD de S002 sin cerrar

El catálogo §5.1 fija para S002 / OZ-2 la instrucción literal *"CI en ubuntu+windows.
qa debe demostrar que un import ilegal entre capas rompe CI con un test"*, y su DoD
*"CI verde en ambos OS < 5 min; violación de capas rechazada; lockfile con hashes"*.
Los tres puntos estaban sin hacer. **OZ-23 no añade alcance: paga la deuda de OZ-2.**

Corolario para el proceso: OZ-2 llegó a *In Progress* sin que nadie contrastara su DoD
línea por línea. El DoD del catálogo es una checklist verificable, no prosa de contexto.

## Agentes utilizados y salidas clave

Sesión ejecutada por el agente principal sin delegar en subagentes (decisión del
fundador para esta sesión). Los roles se cubrieron en secuencia:

- **pm-jira** — creada OZ-23 con contexto, alcance y criterios de aceptación; movida a
  *In Progress*. Detectado de paso que OZ-1 y OZ-2 siguen en *In Progress* sin pasar por
  *Review*, y que las tarjetas de F6 aún no existen.
- **architect** — verificado que la sesión no toca ninguna decisión inmutable: es tooling
  puro, no altera el formato `.wifisurvey`, ni introduce cloud, ni afecta a la
  clasificación observado/derivado/estimado, ni acopla la UI a Windows.
- **qa** — escritos los tests de contrato de capas y validados por mutación (ver abajo).
- **devops** — `uv.lock`, matriz de CI, `--locked`, versión de uv fijada.

## Decisiones tomadas (y si requirieron ADR)

Ninguna requiere ADR. Todas son de tooling y reversibles:

1. **`uv sync --locked` en vez de `uv sync`.** Sin `--locked`, uv actualiza el lockfile en
   silencio cuando no concuerda con `pyproject.toml`, y el lock deja de garantizar nada.
   Con `--locked`, la discrepancia rompe el build, que es el punto de tener lockfile.
2. **Versión de uv fijada a `0.11.32` en CI.** El `uv.lock` declara `revision = 3`; un uv
   más nuevo podría reescribirlo y erosionar la reproducibilidad que esta tarjeta busca.
   Subirla es un cambio deliberado, con regeneración del lock. Coste asumido: hay que
   subirla a mano.
3. **`fail-fast: false` en la matriz.** Si Windows rompe queremos ver igualmente el
   resultado de Linux, para distinguir "fallo del SO" de "fallo del cambio".
4. **Los tests de capas inyectan en el árbol real, no en un sandbox.** Un sandbox con
   paquetes de mentira probaría import-linter, no *nuestros* contratos. Además la
   instalación es editable y el finder del paquete real ensombrecería al del sandbox.
   Se inyecta un módulo sonda con nombre descriptivo y se retira en un `finally`.
5. **`--no-cache` obligatorio en los tests.** Con la caché de import-linter activa, un
   grafo antiguo puede ocultar el módulo infractor y el test pasaría por la razón
   equivocada.

## Artefactos

Archivos nuevos:

- `uv.lock` — 931 líneas, 583 hashes `sha256`, 39 paquetes resueltos.
- `tests/integration/test_contratos_de_capas.py` — 6 tests.
- `docs/sessions/S023_OZ-23_hardening-ci.md` — este log.

Archivos modificados:

- `.github/workflows/ci.yml` — matriz `ubuntu-latest` + `windows-latest`, `uv sync --locked`,
  versión de uv fijada.
- `.gitignore` — `.import_linter_cache/` (lo crea `lint-imports` al ejecutarse).
- `CHANGELOG.md`.

Tests agregados (`tests/integration/test_contratos_de_capas.py`):

| Test | Qué prueba |
| --- | --- |
| `test_el_arbol_limpio_cumple_los_contratos` | Canario: sin violaciones, exit 0. Si falla, las demás aserciones no prueban nada |
| `…rompe_los_contratos[dominio-importa-persistencia]` | Pureza del dominio vs. infraestructura |
| `…rompe_los_contratos[dominio-importa-application]` | Capa inferior importando superior |
| `…rompe_los_contratos[ui-importa-persistencia]` | UI vs. infraestructura |
| `…rompe_los_contratos[ui-importa-ctypes]` | UI vs. API de Windows (decisión inmutable nº 4) |
| `test_la_sonda_no_sobrevive_al_contexto` | La limpieza del módulo sonda es parte del contrato |

## DoD: checklist con estado real (no aspiracional)

- [x] `uv.lock` versionado, con hashes, y CI usando `uv sync --locked`.
      Verificado localmente: `uv sync --locked --group dev` → *Resolved 39 packages, Checked 25*.
- [x] Existe un test que falla si `lint-imports` deja de detectar una violación de capas.
      **Validado por mutación**: al quitar `"persistence"` de `forbidden_modules` del
      contrato de dominio, `lint-imports` reporta *3 kept, 0 broken* pese al import ilegal
      y el test `dominio-importa-persistencia` falla. Restaurado el contrato, vuelve a verde.
      Un test que no puede fallar no es un test.
- [x] Gate completo en verde **en Windows** (local): ruff check, ruff format --check,
      mypy --strict, lint-imports (3 kept, 0 broken), pytest 10 passed, cobertura 99 %.
- [x] **CI verde en Windows y Linux.** Verificado tras el merge del PR #1 (run
      `30736884454` sobre `main`): `ubuntu-latest` 15 s, `windows-latest` 27 s, ambos en
      verde. El log del job de Windows confirma `uv sync --locked` → *Resolved 39 packages*,
      ruff, mypy, *Contracts: 3 kept, 0 broken* y *10 passed*. Muy por debajo del umbral de
      5 min del DoD de S002.
- [x] **Job de Windows requerido para el merge.** Protección de rama activada sobre `main`:
      ambos checks requeridos, `strict` (la rama debe estar al día), sin force-push ni
      borrado, y aplicada también a administradores.
- [x] Session log y CHANGELOG.

## Validaciones pendientes del fundador

Ninguna al cierre. Ambas quedaron resueltas en la misma sesión:

1. ~~Branch protection~~ — activada; ver DoD arriba. Revertible con
   `gh api -X DELETE repos/fs1986/openzonda/branches/main/protection`.
2. ~~Revisar el PR y comprobar que ambos jobs pasan en < 5 min~~ — PR #1 revisado y
   mergeado por el fundador (`94a244c`); ambos jobs verdes.

> Nota: esta sección y la casilla de CI del DoD se actualizaron en la sesión S025, una vez
> conocido el resultado real de CI. En el momento de escribir el log original ambas
> estaban legítimamente pendientes.

## Desvíos / deuda registrada

- **No había toolchain en la máquina de desarrollo.** Ni Python ni `uv`: solo el alias stub
  de la Microsoft Store. Es decir, hasta esta sesión *nada* del repo se había ejecutado
  localmente; todo lo que se sabía venía de CI. Instalado `uv 0.11.32` vía winget con
  autorización del fundador; uv descargó CPython 3.13.14. Esto explica cómo OZ-2 pudo
  cerrarse sin lockfile: nunca se ejecutó un `uv sync`.
- **OZ-1 y OZ-2 siguen en *In Progress***, sin pasar por *Review* ni *Done*. Contradice el
  protocolo §3 (etapas 7 y 8). Pendiente de decisión del fundador.
- **SBOM sin hacer**, fuera de alcance por decisión explícita. Ahora es barato: `uv.lock`
  ya existe y es la entrada natural para CycloneDX. Merece tarjeta propia.
- **Cobertura de una línea sin cubrir** (`test_contratos_de_capas.py:46`): la rama de
  respaldo que invoca el linter vía `python -c` cuando `lint-imports` no está en el PATH.
  Solo se ejercita en entornos sin venv activo. Deuda aceptada.

## Próxima sesión sugerida

**OZ-3 · S003 · Walking skeleton Qt + PyInstaller [HW]**, que es la siguiente en el
catálogo y ahora arranca sobre una base verificable en el SO objetivo. Antes conviene
resolver el estado de OZ-1/OZ-2 y decidir si el SBOM va en tarjeta propia dentro de F0.

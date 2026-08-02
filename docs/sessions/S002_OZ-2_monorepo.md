# S002 · OZ-2 · Monorepo + calidad + CI

Fecha: 2026-08-02 · Duración: no recuperable · Fase: F0 · Rama: **ninguna** (commits directos a `main`)

> ⚠️ **Este log es una reconstrucción a posteriori, no un registro contemporáneo.**
> Se redactó el 2026-08-02 durante la sesión S025 (OZ-1), a partir del historial de git.
> La sesión original se ejecutó sin bitácora. Todo lo que sigue está respaldado por commits
> verificables; **el razonamiento detrás de cada decisión no quedó registrado y no es
> recuperable**. Ver la nota de S001 sobre por qué S001 y S002 no fueron dos sesiones
> distintas: todo el bootstrap entró en un único commit, `d0351c5`.

## Objetivo (copiado de la tarjeta)

Crear el monorepo según §7.3 del diseño con uv workspace y paquetes vacíos pero
importables. Configurar ruff, mypy `--strict` en domain, import-linter con los contratos de
capas, pre-commit y CI en ubuntu+windows. qa debe demostrar que un import ilegal entre
capas rompe CI con un test.

## Agentes utilizados y salidas clave

**No recuperable.** El catálogo asignaba `devops` como líder con `dev-core`, `qa` y
`security`. El historial no permite confirmar que se invocara ninguno.

Sí es verificable el efecto de su ausencia: los dos puntos que el catálogo asignaba
explícitamente a `qa` ("demostrar que un import ilegal rompe CI con un test") y a
`security` (lockfile con hashes, revisión de dependencias iniciales) son exactamente los
que quedaron sin hacer.

## Decisiones tomadas (y si requirieron ADR)

Ninguna requirió ADR: la arquitectura hexagonal ya estaba fijada en ADR-003 y esta sesión
la instrumentó. Decisiones de tooling verificables en el historial:

1. **Contratos de capas con `import-linter`** — tres contratos en `pyproject.toml`: capas
   `desktop → application → domain`, pureza del dominio y prohibición de que la UI toque
   infraestructura o `ctypes`. Instrumenta ADR-003 y la decisión inmutable nº 4.
2. **`include_external_packages = true`** (`7abe2a7`) — necesario porque los contratos
   `forbidden` nombran módulos externos (PySide6, scipy, matplotlib, sqlite3, ctypes).
   Sin esta opción import-linter no puede validarlos. Se descubrió por fallo de CI, no por
   diseño.
3. **mypy `--strict` limitado al núcleo determinista** (`domain`, `rf_engine`) en lugar de
   todo el repo. El motivo no quedó registrado; presumiblemente para no bloquear la UI y
   los adapters, aún inexistentes.
4. **Sintaxis de genéricos PEP 695 en `Measured[T]`** (`5dbe736`), adoptada al resolver
   avisos de ruff (UP046), no como decisión deliberada.

## Artefactos

Commits (todos en `main`, sin PR):

| Commit | Fecha | Qué aportó a OZ-2 |
| --- | --- | --- |
| `d0351c5` | 01:49 | Estructura hexagonal (`packages/` × 11, `apps/desktop`, `native/windows`); `pyproject.toml` con uv, ruff, mypy, pytest y contratos import-linter; CI en GitHub Actions; invariante de honestidad metrológica en `domain/measurement.py` con 4 tests de contrato |
| `5dbe736` | 01:55 | Corrección de lint (E501, UP046, UP037) tras fallo de CI |
| `7abe2a7` | 01:57 | `include_external_packages` en import-linter tras segundo fallo de CI |

Los dos primeros runs de CI del proyecto fallaron (`30734837107` y `30734965565`); el
tercero (`30735011141`) pasó.

## DoD: checklist con estado real

Contrastado contra el repositorio el 2026-08-02, durante el cierre de OZ-23.

- [ ] **CI verde en ambos OS < 5 min** — incumplido en su momento: el workflow corría solo
      en `ubuntu-latest`. Windows, que es el SO objetivo del producto, no se compilaba
      nunca. **Cerrado en OZ-23**: matriz `ubuntu` (15 s) + `windows` (27 s), ambas verdes.
- [ ] **Violación de capas rechazada por CI** — incumplido en su momento. `lint-imports`
      se ejecutaba, pero nada demostraba que rechazase una violación real: un contrato mal
      escrito habría pasado en verde indefinidamente. **Cerrado en OZ-23** con seis tests
      en `tests/integration/test_contratos_de_capas.py`, validados por mutación.
- [ ] **Lockfile con hashes vía uv** — incumplido en su momento: no existía `uv.lock`.
      **Cerrado en OZ-23**: 583 hashes `sha256`, y CI usa `uv sync --locked`.
- [ ] **`pre-commit`** — mencionado en la instrucción de arranque del catálogo, nunca
      configurado. **Sigue pendiente** y no lo recoge ninguna tarjeta.

## Validaciones [HW] pendientes del fundador

Ninguna.

## Desvíos / deuda registrada

- Los tres puntos del DoD quedaron sin cumplir y la tarjeta pasó igualmente a
  *In Progress* sin contraste. Se detectaron el mismo 2026-08-02 al revisar la tarjeta, y
  se cerraron en OZ-23.
- **Causa raíz identificable**: no había toolchain en la máquina de desarrollo. Ni Python
  ni `uv` estaban instalados (solo el alias stub de la Microsoft Store), lo que se descubrió
  en OZ-23. Es materialmente imposible generar un `uv.lock` sin `uv`, y explica por qué la
  sesión pudo darse por terminada sin él: nada se ejecutó localmente, todo el feedback
  venía de CI.
- `pre-commit` sigue sin configurar. Merece tarjeta propia o incorporarse a OZ-24.
- Trabajo sin rama de tarjeta ni PR, y sin session log.

## Próxima sesión sugerida

Registrado a posteriori: la deuda de esta tarjeta se cerró en **OZ-23** (F0.5 · S023).

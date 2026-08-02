# Compilar OpenZonda

El objetivo de este documento es que puedas construir OpenZonda desde cero sin preguntar
nada a nadie. Si algo aquí no funciona, es un bug de este archivo: abre una issue.

## Requisitos

| Herramienta | Versión | Para qué | Obligatoria |
| --- | --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | 0.11.32 | Entorno, dependencias y ejecución | Sí |
| Git | cualquiera reciente | Fuentes; la versión del build sale de `git describe` | Sí |
| [.NET SDK](https://dotnet.microsoft.com/download) | 8.0 | Solo para instalar WiX | Solo para el MSI |
| [WiX Toolset](https://wixtoolset.org/) | 5.x | Construir el instalador | Solo para el MSI |

**No necesitas instalar Python.** `uv` descarga la versión correcta (3.13) por su cuenta.

La versión de `uv` está fijada a propósito, la misma que usa CI: `uv.lock` declara un
formato de lock concreto y una versión más nueva podría reescribirlo, con lo que los
builds dejarían de ser reproducibles.

## Entorno de desarrollo

```bash
git clone https://github.com/fs1986/openzonda.git
cd openzonda
uv sync --locked --group dev --extra ui
```

`--locked` hace que el comando **falle** si `uv.lock` no concuerda con `pyproject.toml`,
en lugar de actualizarlo en silencio. Es lo que hace que el lockfile signifique algo.

En Linux, PySide6 necesita además algunas bibliotecas del sistema:

```bash
sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libdbus-1-3 libglib2.0-0
```

## Ejecutar desde fuentes

```bash
uv run python -m openzonda
```

## Comprobaciones de calidad

Son exactamente las que ejecuta CI. Si pasan en local, pasan allí.

```bash
uv run ruff check .                                      # lint
uv run ruff format --check .                             # formato
uv run mypy packages/domain packages/rf_engine --strict  # tipos en el núcleo
uv run lint-imports                                      # contratos de capas
uv run pytest                                            # tests
```

`lint-imports` no es cosmético: verifica que la UI no importe infraestructura y que el
dominio no dependa de nada externo (ADR-003, ADR-008). Los tests de
`tests/integration/test_contratos_de_capas.py` comprueban que esos contratos de verdad
rechazan una violación, no solo que el comando existe.

Sin escritorio (servidor, contenedor, SSH), los tests de UI necesitan:

```bash
QT_QPA_PLATFORM=offscreen uv run pytest
```

## Construir el bundle

```bash
uv run --group build pyinstaller packaging/openzonda.spec --noconfirm
```

Produce `dist/OpenZonda/` (onedir, ~113 MB). La versión se resuelve desde el tag de git y
se congela en `apps/openzonda/_build_info.py`, que **no se versiona**: se regenera en cada
build. Sin tags, el bundle se identifica como `0.0.0+dev` o con el hash del commit, nunca
con un número inventado que parezca una release.

Verifícalo:

```powershell
pwsh -File scripts/smoke_local.ps1
```

Comprueba tamaño, código de salida y que el log sea JSON lines válido, arrancando el
ejecutable de verdad con su event loop.

## Construir el instalador (solo Windows)

```powershell
dotnet tool install --global wix --version 5.*
pwsh -File packaging/windows/build_msi.ps1
```

Produce `dist/OpenZonda-<version>.msi` (~37 MB). El script copia el bundle a un staging
limpio antes de empaquetar: si has ejecutado el smoke test, `dist/OpenZonda/` contiene
`logs/`, `settings.json` y posiblemente `portable.marker`, y ninguno de ellos puede
acabar dentro del instalador. Un `portable.marker` colado haría que **toda** instalación
arrancase en modo portable.

Se usa WiX **v5** y no v4 porque el elemento `<Files>` (cosecha automática de un árbol de
archivos) solo existe desde v5. En v4 habría que enumerar a mano las dependencias de Qt,
una lista que se desincroniza en silencio en cuanto cambia una versión de PySide6.

### Qué instala y qué no

| Ruta | Contenido | Lo toca el instalador |
| --- | --- | --- |
| `%LOCALAPPDATA%\Programs\OpenZonda\` | Binarios | Sí |
| `%APPDATA%\OpenZonda\settings.json` | Preferencias | **No** |
| `%LOCALAPPDATA%\OpenZonda\{logs,cache}\` | Logs y caché | **No** |
| Carpetas de proyectos | Tus surveys | **No** |

El instalador escribe únicamente en la primera fila. De ahí se sigue que desinstalar no
puede destruir datos de usuario, que es como se satisface la decisión inmutable nº 6.

## Modo portable

Coloca un archivo vacío llamado `portable.marker` junto a `OpenZonda.exe`. La aplicación
lo detecta al arrancar y pasa a guardar configuración, logs y caché **junto al
ejecutable**, sin escribir nada en el perfil del usuario. Es el modo pensado para llevar
OpenZonda en un pendrive a una máquina ajena.

## Release

Las releases las dispara un tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

`release.yml` construye el bundle, lo somete al smoke test, empaqueta el MSI, genera el
SBOM CycloneDX, audita las dependencias de runtime, calcula los SHA256SUMS y crea una
**release en borrador**. El borrador es deliberado: la validación de
install → upgrade → uninstall en una VM limpia no la puede hacer CI.

## Verificar una release descargada

```powershell
Get-FileHash .\OpenZonda-0.1.0.msi -Algorithm SHA256
```

Compara el resultado con la línea correspondiente de `SHA256SUMS.txt`. El SBOM
(`openzonda-sbom.cdx.json`) lista todas las dependencias de terceros que viajan dentro del
instalador, con versión y licencia.

**El instalador no está firmado.** Windows SmartScreen mostrará una advertencia. Es la
razón por la que publicamos hashes y SBOM: para que puedas comprobar qué estás
instalando sin depender de nuestra palabra.

## Estructura del repositorio

```
packages/     domain, application, wifi, rf_engine, ...   (lógica)
apps/desktop  UI PySide6 — no importa infraestructura
apps/openzonda composition root — el único que cablea adaptadores (ADR-008)
native/windows bindings ctypes de wlanapi (ADR-007)
packaging/    spec de PyInstaller y autoría WiX
scripts/      utilidades de verificación
ADR/          decisiones de arquitectura, inmutables
docs/         diseño, session logs, retros, plantillas
```

Las dependencias permitidas entre paquetes están en `[tool.importlinter]` de
`pyproject.toml` y se verifican en CI.

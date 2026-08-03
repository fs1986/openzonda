# OpenZonda

**Site surveys WiFi de nivel profesional, open source, para Windows 10/11 — sin hardware propietario.**

[![CI](https://github.com/openzonda/openzonda/actions/workflows/ci.yml/badge.svg)](https://github.com/openzonda/openzonda/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Estado](https://img.shields.io/badge/estado-F1%20en%20curso-orange)
![Plataforma](https://img.shields.io/badge/plataforma-Windows%2010%2F11%20x64-informational)

OpenZonda es una aplicación desktop para **survey pasivo, heatmapping y diseño
predictivo** de redes WiFi, con la ambición de una paridad progresiva con
las herramientas comerciales de referencia — usando cualquier NIC con driver WLAN
estándar de Windows, sin depender de hardware dedicado en el caso base.

## Principio rector: honestidad metrológica

El diferenciador y el invariante no negociable del proyecto. Todo dato se
clasifica como **observado / derivado / estimado / predictivo**, y esa
clasificación vive en el **modelo de datos**, no solo en la interfaz. Un heatmap
nunca colorea un píxel sin declarar de dónde viene su valor. Degradar esta
distinción en silencio está prohibido (ver [ADR-006](ADR/ADR-006-honestidad-metrologica.md)).

## Qué hace (y qué no)

| En alcance (v0.1 → 1.0) | Fuera de alcance explícito |
|---|---|
| Survey pasivo con NIC estándar de Windows | Spectrum analysis de capa física (requiere SDR) |
| Heatmaps de RSSI, cobertura, canal, densidad de APs | Packet capture / monitor mode (no usable en NICs consumer) |
| Diseño predictivo log-distance y multi-wall | Survey activo (iperf) — llega como plugin en F6 |
| Análisis de canal, capacidad (BSS Load), roaming | Backends macOS/Linux en 1.0 (interfaces previstas, impl. diferida) |
| Reporting PDF/HTML y export CSV/JSON/GeoJSON | |

## Restricciones físicas asumidas (Windows)

OpenZonda no promete lo que el stack WLAN de Windows no puede dar:

- **Permiso de ubicación** obligatorio: sin él, `WlanGetNetworkBssList` devuelve vacío.
- **RSSI no calibrado**: cada NIC difiere; el reporte declara el adaptador usado.
- **Throttling de escaneo** (~4 s/interfaz) → cadencia objetivo 3–5 s.
- **Sin noise floor** en la mayoría de drivers → SNR "no disponible", **nunca estimado**.
- **Sin monitor mode** → capacidad estimada vía BSS Load (IE QBSS), declarado como heurística.

## Instalación

Descarga el instalador `.msi` de la [última release](https://github.com/openzonda/openzonda/releases).
Es **per-user**: no pide permisos de administrador y se instala en
`%LOCALAPPDATA%\Programs\OpenZonda`. No toca tus proyectos ni tu configuración.

### Windows va a advertirte, y es esperable

Al ejecutar el instalador verás una pantalla azul de **Windows SmartScreen**:

> *Windows protegió su PC — Microsoft Defender SmartScreen impidió el inicio de una
> aplicación desconocida.*

Para continuar: **Más información → Ejecutar de todas formas**.

Esa advertencia **no significa que el archivo esté infectado**. Significa que el
instalador no está firmado con un certificado de firma de código, algo que cuesta entre
200 y 600 USD al año y que OpenZonda no paga mientras esté en versión 0.x. Es la
situación normal de casi todo el software open source distribuido por particulares.

### Verifica antes de instalar, en lugar de confiar

Precisamente porque no hay firma, cada release publica lo necesario para que compruebes
qué estás instalando sin depender de nuestra palabra:

```powershell
Get-FileHash .\OpenZonda-0.0.1.msi -Algorithm SHA256
```

Compara el resultado con la línea correspondiente de `SHA256SUMS.txt`, publicado junto al
instalador. Si coincide, el archivo es byte a byte el que produjo CI a partir del código
de este repositorio.

El archivo `openzonda-sbom.cdx.json` de la misma release es un **SBOM CycloneDX**: lista
todas las dependencias de terceros que viajan dentro del instalador, con su versión y su
licencia. Se genera desde el mismo lockfile con el que se compila, así que no puede
desincronizarse de lo que realmente se distribuye.

Si algo de esto no cuadra, **no instales** y abre una issue.

### Sin instalar nada: modo portable

Si trabajas en un equipo donde no puedes instalar software —situación habitual haciendo
surveys en redes ajenas—, coloca un archivo vacío llamado `portable.marker` junto a
`OpenZonda.exe`. La aplicación guardará configuración, logs y caché **junto al
ejecutable**, sin escribir nada en el perfil del usuario.

## Arquitectura

Hexagonal (ports & adapters), verificada en CI con `import-linter`:

```
UI (PySide6) → Application → Domain
Infraestructura (wifi, persistence, native/windows) implementa los ports
```

- La **UI nunca importa** infraestructura ni APIs de Windows directamente.
- El **dominio no importa nada** externo salvo stdlib y NumPy.

Ver el diseño completo en [`docs/design/software-design-v0.2.md`](docs/design/software-design-v0.2.md).

## Estructura del repositorio

```
apps/openzonda/        composition root: cablea adaptadores y lanza la app
apps/desktop/          UI PySide6 — vistas y ViewModels, nada más
packages/              domain · application · wifi · rf_engine · geometry
                       heatmap · analytics · reporting · interop · ai · persistence
native/windows/        adaptador Native Wi-Fi (ctypes)
docs/                  design · sessions · retros · templates
ADR/                   decisiones de arquitectura, inmutables
tests/                 unit · integration · rf · fixtures
packaging/             spec de PyInstaller · windows/ con WiX, MSI e icono
scripts/               verificación local (smoke test del bundle)
```

`apps/openzonda` y `apps/desktop` están separados a propósito ([ADR-008](ADR/ADR-008-composition-root.md)):
el contrato de capas prohíbe que la UI importe infraestructura, y alguien tiene que
instanciar los adaptadores concretos. Ese alguien es el composition root, y vive fuera de
la UI para que la prohibición no necesite excepciones.

## Desarrollo

Requiere [uv](https://docs.astral.sh/uv/). **No necesitas instalar Python**: uv descarga
la versión correcta (3.13) por su cuenta.

```bash
uv sync --locked --group dev --extra ui        # entorno + dependencias
uv run python -m openzonda                     # ejecutar desde fuentes
uv run pytest                                  # tests
uv run mypy packages/domain packages/rf_engine --strict
uv run ruff check .
uv run lint-imports                            # contratos de capas
```

La guía completa —construir el bundle y el instalador, verificar una release— está en
[`BUILD.md`](BUILD.md).

## Estado

**F0 completada · F1 en curso.** Existe un instalador MSI funcional, un pipeline de release
por tag con SBOM y hashes, y el núcleo de dominio con su modelo de procedencia.

La hoja de ruta F0–F9 está en [`docs/design/plan-implementacion.md`](docs/design/plan-implementacion.md),
y cada sesión de trabajo deja su bitácora en [`docs/sessions/`](docs/sessions/).

## Licencia

[Apache License 2.0](LICENSE).

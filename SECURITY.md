# Política de seguridad

## Reportar una vulnerabilidad

Por favor **no** abras un issue público para vulnerabilidades. Usa los
[GitHub Security Advisories](https://github.com/openzonda/openzonda/security/advisories/new)
del repositorio para un reporte privado. Intentamos responder en un plazo razonable
y coordinar la divulgación.

## Alcance y postura

- **Privacidad del dato de survey:** los BSSIDs son datos geolocalizables. OpenZonda
  no añade telemetría de ningún tipo y opera sin requerir Internet.
- **Supply chain:** dependencias con lockfile de hashes vía `uv`; releases con SBOM
  CycloneDX y SHA256SUMS. Ninguna dependencia nueva entra sin revisión.
- **Plugins:** no se cargan automáticamente desde un archivo de proyecto.

## Verificar lo que instalas

Cada release publica tres cosas junto al instalador:

| Archivo | Para qué sirve |
| --- | --- |
| `SHA256SUMS.txt` | Comprobar que el MSI descargado es exactamente el que produjo CI |
| `openzonda-sbom.cdx.json` | SBOM CycloneDX 1.6: todas las dependencias de terceros que viajan dentro del instalador, con versión y licencia |
| Notas de la release | Qué verificó CI y qué **no** |

```powershell
Get-FileHash .\OpenZonda-0.1.0.msi -Algorithm SHA256
```

El SBOM se genera a partir del mismo `uv.lock` con el que se construyó el artefacto, no de
una lista mantenida a mano, así que no puede desincronizarse de lo que realmente se
distribuye.

**El instalador no está firmado con un certificado de firma de código.** Windows
SmartScreen mostrará una advertencia al ejecutarlo. Publicar hashes y SBOM es precisamente
la alternativa a pedirte que confíes en nuestra palabra: puedes comprobar qué estás
instalando. Adquirir un certificado de firma queda pendiente para una fase posterior, y se
anunciará cuando ocurra.

## Auditoría de dependencias

CI ejecuta `pip-audit` en cada cambio, con dos criterios distintos:

- **Dependencias de runtime** (las que viajan en el MSI): un CVE **rompe el build**. Son
  las que llegan a tu máquina.
- **Dependencias de desarrollo** (pytest, mypy, ruff, PyInstaller): un CVE se reporta pero
  no bloquea. No llegan a ningún usuario, y bloquear releases por ellas empuja a
  desactivar la comprobación, que es peor que no tenerla.

## Datos sensibles

Los proyectos `.wifisurvey` pueden contener información de la red del usuario y no se
versionan (ver `.gitignore`). Trátalos como confidenciales.

# Política de seguridad

## Reportar una vulnerabilidad

Por favor **no** abras un issue público para vulnerabilidades. Usa los
[GitHub Security Advisories](https://github.com/fs1986/openzonda/security/advisories/new)
del repositorio para un reporte privado. Intentamos responder en un plazo razonable
y coordinar la divulgación.

## Alcance y postura

- **Privacidad del dato de survey:** los BSSIDs son datos geolocalizables. OpenZonda
  no añade telemetría de ningún tipo y opera sin requerir Internet.
- **Supply chain:** dependencias con lockfile de hashes vía `uv`; releases con SBOM y
  artefactos firmados. Ninguna dependencia nueva entra sin revisión.
- **Plugins:** no se cargan automáticamente desde un archivo de proyecto.

## Datos sensibles

Los proyectos `.wifisurvey` pueden contener información de la red del usuario y no se
versionan (ver `.gitignore`). Trátalos como confidenciales.

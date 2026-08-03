# S027 · OZ-26 y OZ-29 · Cierre de deuda de empaquetado

Fecha: 2026-08-02 · Duración: ~40 min · Fase: F0 (deuda) · Ramas:
`feature/oz-26-sin-firma-alpha`, `feature/oz-29-icono-versioninfo`

> **Desvío del protocolo, declarado.** Este log cubre **dos tarjetas**, contra la regla
> "1 sesión = 1 tarjeta = 1 session log". Ambas son pequeñas, se ejecutaron en un bloque
> continuo y comparten contexto (empaquetado y presentación del producto ante el usuario).
> Cada una tuvo su rama y su PR, así que la trazabilidad tarjeta → commits se mantiene
> intacta; lo que se comparte es la bitácora. Se anota aquí para que quien audite no lo
> descubra por su cuenta.

## Objetivo

Ejecutar dos decisiones del PO que desbloqueaban deuda de F0:

- **OZ-26**: no se compra certificado de firma; v0.x se distribuye sin firmar.
- **OZ-29**: el PO aportó el icono, lo que desbloquea la parte que estaba parada.

## OZ-26 — Firma de código: cerrada por decisión

### Decisión

v0.x se distribuye **sin firmar**. Se revisita **Azure Trusted Signing** cuando haya
usuarios reales. La tarjeta se cierra **por decisión, no por implementación**: el trabajo
técnico de firmar sigue sin hacerse y sigue siendo válido.

Se añadió Azure Trusted Signing a la tabla de opciones de la tarjeta, que faltaba. Es la
mejor alternativa de pago para el futuro por tres razones concretas: ~10 USD/mes frente a
200–600 USD/año; sin token hardware, porque la clave vive en un HSM gestionado y permite
firmar desde CI; y con la reputación SmartScreen gestionada por Microsoft, lo que elimina
el periodo de acumulación que penaliza a un certificado OV nuevo justo durante sus primeras
descargas — que son las de la alpha.

### Qué se hizo en su lugar

Sección de instalación en `README.md`. El criterio al redactarla: **explicar la advertencia,
no pedir que se ignore**.

La pantalla de SmartScreen es un aviso de seguridad legítimo. Decirle a alguien "haz clic
en Ejecutar de todas formas" sin explicarle qué significa es exactamente cómo se entrena a
la gente para ignorar los avisos que sí importan. Así que la sección dice qué significa
—que el instalador no está firmado, lo cual es cierto— y qué no significa —que el archivo
esté infectado—.

Y da la alternativa real: verificar el SHA-256 contra `SHA256SUMS.txt` y consultar el SBOM.
**Una firma le pediría al usuario confiar; los hashes le permiten comprobar.** Esa es la
compensación por no firmar, no un consuelo.

Se documentó también el modo portable como salida para quien no puede instalar software en
su equipo, situación habitual haciendo surveys en redes ajenas.

## OZ-29 — Icono y VERSIONINFO

### Icono

El PO aportó `packaging/windows/ico/openzonda.ico` (multirresolución 16–256). Integrado en
dos sitios:

- **Ejecutable**, vía `icon=` en el spec de PyInstaller. El atajo del menú Inicio lo hereda
  automáticamente, porque apunta al `.exe`.
- **Entrada de "Aplicaciones instaladas"**, vía `<Icon>` y `ARPPRODUCTICON` en WiX. Este sí
  hay que declararlo aparte: no se deduce del ejecutable.

**El icono es PROVISIONAL.** Se reemplaza cuando exista el logotipo definitivo. Está
anotado en el `.wxs` junto al elemento `<Icon>`, que es donde lo verá quien vaya a
cambiarlo, y no solo en la tarjeta.

### VERSIONINFO

Generado en el spec desde la misma versión que usa el resto del build, no escrito a mano en
un segundo sitio donde pudiera desincronizarse.

El detalle interesante es la **traducción de versión**. Windows exige una cuaterna de
enteros, y `git describe` produce cosas como `0.0.1-6-g0d47d7f-dirty`. La solución:

| Campo | Contenido | Por qué |
| --- | --- | --- |
| `filevers` / `prodvers` | `(0, 0, 1, 0)` | Numérico obligatorio. Sin tag reconocible → `(0,0,0,0)`, nunca un número inventado |
| `FileVersion` (texto) | `0.0.1-6-g0d47d7f-dirty` | Texto libre: se conserva la cadena exacta, con el `-dirty` incluido |

Así el ejecutable declara con precisión de qué commit salió, sin que la parte numérica
mienta sobre ser una release que no existe.

### Fallo rápido si falta el icono

Tanto el spec como `build_msi.ps1` abortan con un mensaje explícito si el `.ico` no está.
Sin esa comprobación, PyInstaller construiría igual con el icono por defecto y el fallo
aparecería como "el instalador se ve raro", que es difícil de atribuir.

## DoD: checklist con estado real (no aspiracional)

Verificado inspeccionando los artefactos, no confiando en que el build saliera en verde:

- [x] **`VERSIONINFO` en el ejecutable** — `Get-Item ... .VersionInfo` devuelve
      ProductName `OpenZonda`, FileVersion `0.0.1-6-g0d47d7f-dirty`, CompanyName,
      LegalCopyright con Apache-2.0 y FileDescription.
- [x] **Cuaterna numérica correcta** — `0.0.1.0`.
- [x] **Icono en el ejecutable** — extraído con `System.Drawing.Icon.ExtractAssociatedIcon`.
- [x] **Icono en el MSI** — consultada la base de datos del instalador por COM: la tabla
      `Icon` contiene `OpenZondaIcon` y la propiedad `ARPPRODUCTICON` apunta a él.
      Extraer el MSI con `msiexec /a` no habría bastado: esas tablas no aparecen en el
      árbol de archivos.
- [x] **`ProductVersion` del MSI** — `0.0.1`.
- [x] **Smoke test** — PASS; el bundle sigue arrancando.
- [x] **README documenta SmartScreen** (OZ-26).

## Validaciones [HW] pendientes del fundador

Ninguna bloqueante. Cuando valides el MSI de OZ-4 en la VM, comprueba de paso que el icono
aparece en "Aplicaciones instaladas" y en el atajo del menú Inicio.

## Desvíos / deuda registrada

- **El icono es provisional**, por decisión explícita: es un placeholder hasta que exista el
  logotipo definitivo. No debe tratarse como identidad visual final.
- La firma de código sigue sin hacerse, ahora como decisión consciente y documentada en tres
  sitios coherentes: `README.md`, `SECURITY.md` y `packaging/release-notes.md`.
- El bloque de estructura del repositorio del `README.md` tampoco menciona `apps/openzonda`.
  Es el mismo problema que OZ-31 y se corrige allí.

## Próxima sesión sugerida

**OZ-5 · S005 · Dominio: entidades y value objects**, ya en marcha en paralelo por decisión
del PO, que no quiso serializar F1 detrás de la validación en VM de OZ-4.

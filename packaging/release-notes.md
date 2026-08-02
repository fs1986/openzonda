Release generada automáticamente por `release.yml` a partir del tag.

**Se publica como borrador a propósito.** El instalador requiere validación manual de
install → upgrade → uninstall en una VM Windows 11 limpia antes de hacerse público, y esa
comprobación no la puede ejecutar CI.

### Artefactos

| Archivo | Qué es |
| --- | --- |
| `OpenZonda-*.msi` | Instalador per-user, sin elevación. Instala en `%LOCALAPPDATA%\Programs\OpenZonda` |
| `openzonda-sbom.cdx.json` | SBOM CycloneDX 1.6 de las dependencias que viajan dentro del instalador |
| `SHA256SUMS.txt` | Hashes SHA-256 de los artefactos anteriores |

### Verificado automáticamente

- El bundle arranca y cierra con código de salida 0 — smoke test sobre el ejecutable real,
  con su event loop, no una simulación.
- El log de arranque es JSON lines válido.
- Sin vulnerabilidades conocidas en las dependencias de runtime (`pip-audit`).
- El instalador no contiene residuos de ejecución (logs, settings ni `portable.marker`).
- `ruff`, `mypy --strict` en el núcleo, contratos de capas y la suite de tests, en Windows
  y Linux.

### Sin verificar

- **Instalación, actualización y desinstalación en una VM limpia.**
- **El aspecto real de la ventana**: CI ejecuta Qt en modo `offscreen`, así que la interfaz
  no se ha renderizado en ninguna pantalla.
- Comportamiento con hardware WiFi real: la captura llega en F2.

### El instalador no está firmado

Windows SmartScreen mostrará una advertencia al ejecutarlo. Publicamos hashes y SBOM
precisamente para que puedas comprobar qué estás instalando sin depender de nuestra
palabra:

```powershell
Get-FileHash .\OpenZonda-*.msi -Algorithm SHA256
```

Compara el resultado con `SHA256SUMS.txt`.

### Qué instala y qué no

El MSI escribe **solo** en `%LOCALAPPDATA%\Programs\OpenZonda`. No toca tus preferencias
(`%APPDATA%\OpenZonda\`), ni tus logs, ni tus proyectos. Por eso desinstalar no puede
destruir datos tuyos.

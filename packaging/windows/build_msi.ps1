<#
.SYNOPSIS
    Construye el MSI de OpenZonda a partir del bundle onedir de PyInstaller.

.DESCRIPTION
    Traduce la versión de git a un ProductVersion válido para Windows Installer y llama a
    `wix build`. Se usa igual en local y en CI, para que un fallo de empaquetado no aparezca
    por primera vez durante una release.

.PARAMETER BundleDir
    Bundle onedir ya construido. Por defecto dist/OpenZonda.

.PARAMETER OutputPath
    Ruta del MSI resultante. Por defecto dist/OpenZonda-<version>.msi.

.PARAMETER Version
    ProductVersion explícito. Si se omite se deriva del tag de git.

.EXAMPLE
    pwsh -File packaging/windows/build_msi.ps1
#>
[CmdletBinding()]
param(
    [string]$BundleDir,
    [string]$OutputPath,
    [string]$Version
)

$ErrorActionPreference = 'Stop'

$raizRepo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $BundleDir) { $BundleDir = Join-Path (Join-Path $raizRepo 'dist') 'OpenZonda' }

if (-not (Test-Path -LiteralPath $BundleDir)) {
    throw "No existe el bundle en $BundleDir. Constrúyelo primero con: uv run --group build pyinstaller packaging/openzonda.spec --noconfirm"
}

function Resolve-ProductVersion {
    <#
        Windows Installer solo admite versiones numéricas x.y.z (máximo 255.255.65535) y
        **ignora la cuarta parte** al comparar. Un `git describe` como
        "0.0.1-3-gc85ecf9-dirty" no le sirve, así que se traduce:

          v0.0.1            -> 0.0.1     (tag limpio: es una release)
          v0.0.1-3-gc85ecf9 -> 0.0.1     (commits por encima del tag)
          sin tags          -> 0.0.0     (build de desarrollo)

        Se prefiere 0.0.0 antes que inventar un número: un MSI que se hace pasar por una
        release que no existe es peor que uno que se declara de desarrollo.
    #>
    $descripcion = & git -C $raizRepo describe --tags --always --dirty 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $descripcion) { return '0.0.0' }

    if ($descripcion -match '^v?(\d+)\.(\d+)\.(\d+)') {
        return "$($Matches[1]).$($Matches[2]).$($Matches[3])"
    }
    return '0.0.0'
}

if (-not $Version) { $Version = Resolve-ProductVersion }
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "ProductVersion inválido para MSI: '$Version'. Debe ser x.y.z numérico."
}

if (-not $OutputPath) {
    $OutputPath = Join-Path (Join-Path $raizRepo 'dist') "OpenZonda-$Version.msi"
}

$wxs = Join-Path $PSScriptRoot 'OpenZonda.wxs'
$intermedios = Join-Path $PSScriptRoot 'obj'

# --- Staging limpio ---------------------------------------------------------------------
# Ejecutar el bundle (smoke test, o simplemente abrirlo) deja logs/, settings.json y —lo
# peligroso— puede dejar un portable.marker dentro de dist/. Harvestear esa carpeta tal
# cual mete esos residuos en el instalador: se distribuirían logs de la máquina de quien
# compila y, con un marker presente, TODA instalación arrancaría en modo portable.
#
# Copiar a un staging y limpiarlo hace que el orden de construcción deje de importar.
$RESIDUOS_DE_EJECUCION = @('logs', 'cache', 'settings.json', 'portable.marker')

$staging = Join-Path (Join-Path $raizRepo 'build') 'msi-staging'
if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null
Copy-Item -LiteralPath $BundleDir -Destination $staging -Recurse
$stagingApp = Join-Path $staging (Split-Path -Leaf $BundleDir)

foreach ($residuo in $RESIDUOS_DE_EJECUCION) {
    $ruta = Join-Path $stagingApp $residuo
    if (Test-Path -LiteralPath $ruta) {
        Write-Host "    Excluido del instalador: $residuo" -ForegroundColor Yellow
        Remove-Item -LiteralPath $ruta -Recurse -Force
    }
}

# Comprobación explícita: si algo se cuela, el build falla en vez de publicar un MSI sucio.
foreach ($residuo in $RESIDUOS_DE_EJECUCION) {
    if (Test-Path -LiteralPath (Join-Path $stagingApp $residuo)) {
        throw "El staging sigue conteniendo '$residuo'; no se construye un MSI con residuos de ejecución."
    }
}

Write-Host "==> Construyendo MSI" -ForegroundColor Cyan
Write-Host "    Bundle:  $BundleDir"
Write-Host "    Staging: $stagingApp"
Write-Host "    Versión: $Version"
Write-Host "    Salida:  $OutputPath"

& wix build $wxs `
    -arch x64 `
    -d "ProductVersion=$Version" `
    -d "BundleDir=$stagingApp" `
    -intermediateFolder $intermedios `
    -out $OutputPath

if ($LASTEXITCODE -ne 0) { throw "wix build falló con código $LASTEXITCODE" }

$mb = [math]::Round((Get-Item -LiteralPath $OutputPath).Length / 1MB, 1)
Write-Host "    OK  MSI de $mb MB en $OutputPath" -ForegroundColor Green

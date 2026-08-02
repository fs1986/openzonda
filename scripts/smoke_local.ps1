<#
.SYNOPSIS
    Smoke test del bundle de OpenZonda (DoD de OZ-3).

.DESCRIPTION
    Arranca el bundle construido por PyInstaller, espera a que termine solo y comprueba
    tres cosas:

      1. El proceso sale con código 0.
      2. El bundle no excede el presupuesto de tamaño del DoD (180 MB).
      3. El log es JSON lines válido y contiene el registro de arranque.

    El arranque es real: se ejecuta el event loop de Qt y la ventana se muestra. El
    modificador --smoke solo programa el cierre, no simula nada.

.PARAMETER BundleDir
    Carpeta del bundle. Por defecto dist/OpenZonda.

.PARAMETER TimeoutSeconds
    Tiempo máximo de espera antes de considerar el arranque colgado.

.EXAMPLE
    pwsh -File scripts/smoke_local.ps1
#>
[CmdletBinding()]
param(
    [string]$BundleDir,
    [int]$TimeoutSeconds = 60,
    [int]$MaxSizeMB = 180
)

$ErrorActionPreference = 'Stop'

# Join-Path con más de dos segmentos es sintaxis de PowerShell 7; se encadena para que el
# script también corra en el Windows PowerShell 5.1 que trae Windows de fábrica.
if (-not $BundleDir) {
    $raizRepo = Split-Path -Parent $PSScriptRoot
    $BundleDir = Join-Path (Join-Path $raizRepo 'dist') 'OpenZonda'
}

function Write-Paso($mensaje) { Write-Host "==> $mensaje" -ForegroundColor Cyan }
function Write-Ok($mensaje)   { Write-Host "    OK  $mensaje" -ForegroundColor Green }
function Write-Fallo($mensaje) {
    Write-Host "    FALLO  $mensaje" -ForegroundColor Red
    exit 1
}

$BundleDir = (Resolve-Path -LiteralPath $BundleDir -ErrorAction SilentlyContinue)
if (-not $BundleDir) {
    Write-Fallo "No existe el bundle. Constrúyelo primero: uv run --group build pyinstaller packaging/openzonda.spec --noconfirm"
}

$exe = Join-Path $BundleDir 'OpenZonda.exe'
if (-not (Test-Path -LiteralPath $exe)) { Write-Fallo "No se encuentra $exe" }

# --- 1. Tamaño del bundle -------------------------------------------------------------
Write-Paso 'Comprobando el tamaño del bundle'
$bytes = (Get-ChildItem -LiteralPath $BundleDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$mb = [math]::Round($bytes / 1MB, 1)
if ($mb -gt $MaxSizeMB) { Write-Fallo "El bundle pesa $mb MB, por encima del presupuesto de $MaxSizeMB MB" }
Write-Ok "$mb MB (presupuesto $MaxSizeMB MB)"

# --- 2. Arranque en modo portable aislado ---------------------------------------------
# Se fuerza modo portable con un marker: así el smoke test no escribe en el perfil real
# del usuario ni contamina la configuración de una instalación existente.
Write-Paso 'Arrancando el bundle en modo portable aislado'
$marker = Join-Path $BundleDir 'portable.marker'
$markerYaExistia = Test-Path -LiteralPath $marker
if (-not $markerYaExistia) { New-Item -ItemType File -Path $marker | Out-Null }

$logsDir = Join-Path $BundleDir 'logs'
if (Test-Path -LiteralPath $logsDir) { Remove-Item -LiteralPath $logsDir -Recurse -Force }

try {
    $inicio = Get-Date
    $proceso = Start-Process -FilePath $exe -ArgumentList '--smoke', '1500' -PassThru -WindowStyle Minimized
    if (-not $proceso.WaitForExit($TimeoutSeconds * 1000)) {
        $proceso.Kill()
        Write-Fallo "El proceso no terminó en $TimeoutSeconds s"
    }
    $duracion = [math]::Round(((Get-Date) - $inicio).TotalSeconds, 1)

    if ($proceso.ExitCode -ne 0) { Write-Fallo "Código de salida $($proceso.ExitCode)" }
    Write-Ok "Arrancó y cerró limpio en $duracion s (incluye el cierre programado de 1,5 s)"

    # --- 3. Log JSON lines ------------------------------------------------------------
    Write-Paso 'Verificando el log estructurado'
    $log = Join-Path $logsDir 'openzonda.log'
    if (-not (Test-Path -LiteralPath $log)) { Write-Fallo "No se generó $log" }

    $lineas = Get-Content -LiteralPath $log -Encoding utf8 | Where-Object { $_.Trim() }
    if ($lineas.Count -eq 0) { Write-Fallo 'El log está vacío' }

    $registros = @()
    foreach ($linea in $lineas) {
        try { $registros += ($linea | ConvertFrom-Json) }
        catch { Write-Fallo "Línea de log que no es JSON válido: $linea" }
    }
    Write-Ok "$($registros.Count) líneas, todas JSON válido"

    foreach ($campo in 'timestamp', 'level', 'logger', 'message') {
        if ($null -eq $registros[0].$campo) { Write-Fallo "Falta el campo '$campo' en el log" }
    }
    Write-Ok 'Campos timestamp/level/logger/message presentes'

    $arranque = $registros | Where-Object { $_.message -like '*arrancando*' }
    if (-not $arranque) { Write-Fallo 'No se encontró el registro de arranque' }
    Write-Ok "Registro de arranque: $($arranque[0].message)"

    if ($arranque[0].message -notlike '*modo portable*') {
        Write-Fallo 'El bundle no detectó el modo portable pese al marker'
    }
    Write-Ok 'Modo portable detectado correctamente'
}
finally {
    if (-not $markerYaExistia -and (Test-Path -LiteralPath $marker)) {
        Remove-Item -LiteralPath $marker -Force
    }
}

Write-Host ''
Write-Host 'SMOKE TEST: PASS' -ForegroundColor Green

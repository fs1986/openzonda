@echo off
REM ---------------------------------------------------------------------------
REM  Lanzador de doble clic para smoke_local.ps1.
REM
REM  Existe porque Windows bloquea los .ps1 por politica de ejecucion: al hacer
REM  doble clic sobre el script directamente, aparece una consola negra que se
REM  cierra al instante sin dejar leer el error. Este .cmd aplica la politica
REM  correcta, mantiene la ventana abierta al terminar -tanto si pasa como si
REM  falla- y propaga el codigo de salida para que siga sirviendo en scripts.
REM
REM  Uso:
REM    Doble clic                -> verificacion rapida
REM    smoke_local.cmd -Visible  -> muestra la ventana (validacion [HW])
REM
REM  Sin acentos a proposito: los .cmd se interpretan con la codepage de la
REM  consola, que en Windows en espanol suele ser 850 y los mostraria rotos.
REM ---------------------------------------------------------------------------

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0smoke_local.ps1" %*
set "CODIGO=%ERRORLEVEL%"

echo.
if "%CODIGO%"=="0" (
    echo El smoke test ha pasado.
) else (
    echo El smoke test ha FALLADO con codigo %CODIGO%.
)
echo.
pause
exit /b %CODIGO%

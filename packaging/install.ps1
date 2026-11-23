# Instala ktool desde el codigo fuente (requiere Python en el PATH).
# Copia el paquete a la carpeta de usuario, crea el comando 'ktool' (y el alias 'kmap') y lo agrega al PATH.
#
# Se corre asi (Windows trae los scripts deshabilitados; -ExecutionPolicy Bypass
# los permite solo para esta vez, sin cambiar la configuracion de la compu):
#     powershell -ExecutionPolicy Bypass -File packaging\install.ps1

$ErrorActionPreference = "Stop"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "No se encontro Python en el PATH. Instalalo desde https://python.org y reintenta." -ForegroundColor Red
    exit 1
}

$src = Join-Path $PSScriptRoot ".."
$dir = Join-Path $env:LOCALAPPDATA "Programs\ktool"

Write-Host "Instalando ktool en: $dir"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

Copy-Item -Recurse -Force (Join-Path $src "ktool") $dir
Copy-Item -Force (Join-Path $PSScriptRoot "ktool_launcher.py") $dir

$cmd = @"
@echo off
python "%~dp0ktool_launcher.py" %*
"@
Set-Content -Path (Join-Path $dir "kmap.cmd") -Value $cmd -Encoding ASCII
Set-Content -Path (Join-Path $dir "ktool.cmd") -Value $cmd -Encoding ASCII

# El PATH del usuario se lee y se escribe CRUDO, directo del registro.
# [Environment]::GetEnvironmentVariable lo devuelve ya expandido, y al volverlo a
# escribir las entradas como %USERPROFILE%\... quedaban fijas y el valor pasaba de
# REG_EXPAND_SZ a REG_SZ. Se compara entrada por entrada (no por subcadena) para
# no agregar la carpeta dos veces.
$clave = "HKCU:\Environment"
$crudo = (Get-Item $clave).GetValue("Path", "", "DoNotExpandEnvironmentNames")
$entradas = @($crudo -split ";" | Where-Object { $_.Trim() -ne "" })
$ya = $entradas | Where-Object { $_.TrimEnd("\") -ieq $dir.TrimEnd("\") }
if ($ya) {
    Write-Host "Ya estaba en el PATH."
} else {
    $nuevo = (@($entradas) + $dir) -join ";"
    New-ItemProperty -Path $clave -Name "Path" -Value $nuevo -PropertyType ExpandString -Force | Out-Null
    # Escribir el registro no avisa a Windows; crear y borrar una variable con
    # SetEnvironmentVariable si manda el aviso (WM_SETTINGCHANGE), y asi las
    # terminales que se abran desde el Explorador ya ven la carpeta.
    [Environment]::SetEnvironmentVariable("KTOOL_AVISO", "1", "User")
    [Environment]::SetEnvironmentVariable("KTOOL_AVISO", $null, "User")
    Write-Host "Agregado al PATH del usuario." -ForegroundColor Green
}

Write-Host ""
Write-Host "Listo. Abre una terminal nueva y prueba:" -ForegroundColor Green
Write-Host "    ktool -e `"A'B + C`" --open"
Write-Host "    ktool gui"
Write-Host "    (el comando 'kmap' sigue funcionando como alias)"

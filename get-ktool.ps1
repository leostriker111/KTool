# Descarga y ejecuta el instalador mas reciente de ktool desde GitHub Releases.
# Uso:  irm https://raw.githubusercontent.com/leostriker111/ktool/main/get-ktool.ps1 | iex

$ErrorActionPreference = "Stop"
$repo = "leostriker111/ktool"

Write-Host "Buscando la version mas reciente de ktool..."
try {
    $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" `
        -Headers @{ "User-Agent" = "ktool-installer" }
} catch {
    Write-Host "No se pudo consultar Releases. ¿Ya hay una version publicada?" -ForegroundColor Red
    Write-Host "Mira https://github.com/$repo/releases"
    exit 1
}

$asset = $rel.assets | Where-Object { $_.name -like "*setup*.exe" } | Select-Object -First 1
if (-not $asset) {
    Write-Host "El release $($rel.tag_name) no trae instalador (.exe)." -ForegroundColor Red
    exit 1
}

$dest = Join-Path $env:TEMP $asset.name
Write-Host "Descargando $($asset.name) ($($rel.tag_name))..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $dest

Write-Host "Ejecutando el instalador..."
Start-Process -FilePath $dest -Wait
Write-Host "Listo. Abre una terminal NUEVA y ejecuta, desde cualquier carpeta: ktool -h" -ForegroundColor Green

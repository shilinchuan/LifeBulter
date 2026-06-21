$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -m venv .venv
}

$Python = ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt
& $Python -m pip install pyinstaller pillow

if (-not (Test-Path "resources\icon\LifeButler.ico")) {
    if (-not (Test-Path "resources\icon\LifeButler-icon.png")) {
        throw "Missing resources\icon\LifeButler-icon.png. Confirm an icon candidate first, then export it before Windows packaging."
    }
    & $Python -c "from PIL import Image; img=Image.open('resources/icon/LifeButler-icon.png').convert('RGBA'); img.save('resources/icon/LifeButler.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
}

Remove-Item -Recurse -Force "build\lifebutler-windows" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "dist\LifeButler-Windows" -ErrorAction SilentlyContinue
Remove-Item -Force "dist\LifeButler-Windows.zip" -ErrorAction SilentlyContinue

& $Python -m PyInstaller `
    --clean `
    --noconfirm `
    --workpath "build\lifebutler-windows" `
    "packaging\lifebutler-windows.spec"

Compress-Archive -Path "dist\LifeButler-Windows" -DestinationPath "dist\LifeButler-Windows.zip" -Force

Write-Host "Windows portable package created:"
Write-Host "  dist\LifeButler-Windows"
Write-Host "  dist\LifeButler-Windows.zip"

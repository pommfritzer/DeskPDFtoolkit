$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Create .venv and install the project with .[dev] first.' }
& $python scripts/make_icon.py
if ($LASTEXITCODE) { throw 'Icon generation failed.' }
& $python -m pytest -q
if ($LASTEXITCODE) { throw 'Tests failed.' }
& $python scripts/collect_licenses.py
if ($LASTEXITCODE) { throw 'License collection failed.' }
$originalPath = $env:PATH
try {
    $basePython = & $python -c 'import sys; print(sys.base_prefix)'
    # Unrelated tools can put incompatible copies of Qt's system DLLs on PATH.
    $env:PATH = @((Split-Path $python), $basePython, "$env:SystemRoot\System32", $env:SystemRoot) -join ';'
    & $python -m PyInstaller --noconfirm --clean DeskPDF.spec
    if ($LASTEXITCODE) { throw 'Application packaging failed.' }
} finally {
    $env:PATH = $originalPath
}
& $python scripts/check_bundle.py
if ($LASTEXITCODE) { throw 'Packaged application startup failed.' }
$compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$candidates = @('.tools\Inno\ISCC.exe', "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")
$iscc = if ($compiler) { $compiler.Source } else { $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1 }
if (-not $iscc) { throw 'Install Inno Setup 6, or add ISCC.exe to PATH. Portable app is ready in dist\DeskPDF.' }
& $iscc installer/DeskPDF.iss
if ($LASTEXITCODE) { throw 'Installer compilation failed.' }

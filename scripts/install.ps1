param([switch]$NoLaunch)
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
Set-Location $project
$version = & "$project\.venv\Scripts\python.exe" -c 'import tomllib; from pathlib import Path; print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])'
if ($LASTEXITCODE) { throw 'Could not read the project version. Run this script from the project folder.' }
$installer = Join-Path $project "releases\PDFtoolkit26-$version-Setup.exe"
if (-not (Test-Path -LiteralPath $installer)) { throw 'Build the installer first with scripts/build.ps1.' }
$destination = Join-Path $env:LOCALAPPDATA 'Programs\PDFtoolkit26'
$arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS', '/NORESTARTAPPLICATIONS', ('/DIR="{0}"' -f $destination))
$setup = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($setup.ExitCode) { throw "Installation failed with code $($setup.ExitCode)." }
if (-not $NoLaunch) { Start-Process -FilePath (Join-Path $destination 'PDFtoolkit26.exe') -ArgumentList '--tool', 'merge' }

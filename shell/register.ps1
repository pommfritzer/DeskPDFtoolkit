$ErrorActionPreference = 'Stop'
$application = Split-Path $PSScriptRoot -Parent
$package = Join-Path $PSScriptRoot 'PDFtoolkit26.ContextMenu.msix'
if (-not (Test-Path -LiteralPath $package)) { exit 0 }
Add-AppxPackage -Path $package -ExternalLocation $application -ForceTargetApplicationShutdown -ErrorAction Stop

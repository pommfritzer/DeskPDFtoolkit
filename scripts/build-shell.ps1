param([string]$SigningThumbprint = $env:PDFTOOLKIT26_SHELL_CERT_THUMBPRINT)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$visualStudio = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $visualStudio) { throw 'Install the Visual C++ x64 build tools.' }
$sdk = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.*\x64\makeappx.exe" | Sort-Object FullName | Select-Object -Last 1
if (-not $sdk) { throw 'Install the Windows SDK packaging tools.' }
 $version = & "$root\.venv\Scripts\python.exe" -c 'import tomllib; from pathlib import Path; print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])'
$dllName = "PDFCommand-$version.dll"
$packageVersion = "1.$version"
New-Item -ItemType Directory -Force build/Shell,build/shell-package/Assets | Out-Null
$batch = @"
@call "$visualStudio\VC\Auxiliary\Build\vcvars64.bat"
cl /nologo /LD /EHsc /std:c++17 /MT /O2 shell\OpenCommand.cpp /Fobuild\Shell\OpenCommand.obj /Febuild\Shell\$dllName /link /DEF:shell\PDFCommand.def shlwapi.lib shell32.lib ole32.lib uuid.lib runtimeobject.lib
"@
$batch | Set-Content build/Shell/compile.cmd
& build/Shell/compile.cmd
if ($LASTEXITCODE) { throw 'Shell command compilation failed.' }
(Get-Content shell/AppxManifest.xml -Raw).Replace('Version="1.0.0.0"', 'Version="' + $packageVersion + '"').Replace('Shell\PDFCommand.dll', 'Shell\' + $dllName) | Set-Content -Encoding utf8 build/shell-package/AppxManifest.xml
Copy-Item deskpdf/assets/icon.png build/shell-package/Assets/icon.png
$package = 'build/Shell/PDFtoolkit26.ContextMenu.msix'
& $sdk.FullName pack /d build/shell-package /p $package /nv /o
if ($LASTEXITCODE) { throw 'Shell package creation failed.' }
if ($SigningThumbprint) {
    if ($SigningThumbprint -notmatch '^[A-Fa-f0-9]{40}$') { throw 'Invalid signing certificate thumbprint.' }
    & (Join-Path $sdk.DirectoryName 'signtool.exe') sign /fd SHA256 /sha1 $SigningThumbprint /s My $package
    if ($LASTEXITCODE) { throw 'Shell package signing failed.' }
} else {
    Move-Item -LiteralPath $package -Destination build/Shell/PDFtoolkit26.ContextMenu.unsigned.msix -Force
    Write-Output 'Unsigned shell package prepared. Signing is required before registration.'
}

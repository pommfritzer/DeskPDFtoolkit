$ErrorActionPreference = 'Stop'
Get-AppxPackage -Name PDFtoolkit26.ContextMenu | Remove-AppxPackage -ErrorAction Stop

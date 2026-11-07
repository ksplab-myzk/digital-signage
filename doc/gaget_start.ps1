$bat = Join-Path $PSScriptRoot "bat\run_all.bat"

Write-Host $bat
Write-Host (Test-Path $bat)

Start-Process `
    -FilePath $bat `
    -WindowStyle Hidden `
    -WorkingDirectory (Split-Path $bat)


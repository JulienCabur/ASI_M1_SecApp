$current_path = ($MyInvocation.MyCommand.Path).replace("clean-secrets.ps1", "")
Write-Host "Cleaning secrets files from secrets folder but keeping subfolders..."

Get-ChildItem -Path "$current_path\secrets" -File -Recurse | Remove-Item -Force
Write-Host "Done!"


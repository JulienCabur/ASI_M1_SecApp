$current_path = ($MyInvocation.MyCommand.Path).replace("env-creation.ps1", "")

Write-Host "Creating .env file from env.example..."

if (Test-Path "$current_path\.env") {
    Write-Host ".env file already exists. Do you want to overwrite it? (y/n)"
    $response = Read-Host
    if ($response -ne "y") {
        Write-Host "Aborting."
        exit
    }
}

Copy-Item -Path "$current_path\env.example" -Destination "$current_path\.env" -Force

Write-Host "Done!"
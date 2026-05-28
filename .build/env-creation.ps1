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

$envFile = "$current_path\.env"
$acl = Get-Acl $envFile
$acl.SetAccessRuleProtection($true, $false) 
$acl.Access | ForEach-Object { $acl.RemoveAccessRule($_) | Out-Null }
$owner = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule($owner, "FullControl", "Allow")
$acl.AddAccessRule($rule)
Set-Acl -Path $envFile -AclObject $acl

Write-Host "Done!"
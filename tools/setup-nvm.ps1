$ErrorActionPreference = 'Stop'

function Test-NvmInstalled {
    try {
        nvm version | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Install-Nvm {
    $nvmUrl = 'https://github.com/coreybutler/nvm-windows/releases/download/1.1.12/nvm-setup.exe'
    $installer = Join-Path $env:TEMP 'nvm-setup.exe'
    Write-Host "Downloading NVM from $nvmUrl..."
    Invoke-WebRequest -Uri $nvmUrl -OutFile $installer
    Write-Host 'Running NVM installer...'
    Start-Process -FilePath $installer -ArgumentList '/SILENT' -Wait
}

if (-not (Test-NvmInstalled)) {
    Install-Nvm
    if (-not (Test-NvmInstalled)) {
        Write-Error 'NVM installation failed.'
        exit 1
    }
}

Write-Host 'Ensuring Node 20 is installed via NVM...'
nvm install 20 | Out-Null
nvm use 20 | Out-Null

$nodeVersion = node -v
Write-Host "Active Node version: $nodeVersion"

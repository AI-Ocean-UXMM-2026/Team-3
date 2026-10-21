param([ValidateRange(1024, 65535)][int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$backendRoot = Join-Path $projectRoot 'backend'
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'

if ($env:LANNPYA_ENVIRONMENT -and $env:LANNPYA_ENVIRONMENT -notin @('local', 'test')) {
    throw 'Dashboard is disabled in a production environment.'
}

Push-Location -LiteralPath $backendRoot
try {
    if (-not (Test-Path -LiteralPath $python)) {
        Write-Host 'Creating the local backend virtual environment.'
        if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv .venv }
        elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv .venv }
        else { throw 'Python is unavailable. No environment or firewall settings were changed.' }
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    # Windows PowerShell can promote redirected native stderr to a terminating error.
    # Capture the import probe's exit code so a missing package reaches the repair step.
    $probePreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $python -c 'import fastapi, uvicorn, sqlalchemy, alembic; from fastapi.testclient import TestClient; from app.main import create_app' 2>$null
        $probeExitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $probePreference }
    if ($probeExitCode -ne 0) {
        Write-Host 'Installing the project-pinned development dependencies required by this tool.'
        & $python -m pip install -r requirements-dev.lock
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Dashboard was not started.' }
    }
    & $python -m tools.backend_test_dashboard --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Dashboard stopped with a startup/runtime error; see the safe message above.' }
}
finally { Pop-Location }

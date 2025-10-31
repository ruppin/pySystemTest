<#
Simple helper to run tests in PowerShell.
Assumes a virtualenv at .venv (created with: python -m venv .venv)
#>

$venvActivate = Join-Path -Path $PSScriptRoot -ChildPath "..\.venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Output "Activating venv..."
    & $venvActivate
} else {
    Write-Output "No venv activation script found at $venvActivate. Continuing without venv."
}

Write-Output "Running pytest..."
pytest -q
exit $LASTEXITCODE
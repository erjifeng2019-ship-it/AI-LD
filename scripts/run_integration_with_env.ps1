Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python virtual environment not found: $python"
}

$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
    $lines = Get-Content $envFile
    foreach ($line in $lines) {
        if ($line -match '^\s*#' -or $line -notmatch '=') {
            continue
        }
        $parts = $line.Split('=', 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (-not [string]::IsNullOrWhiteSpace($key)) {
            $existing = [System.Environment]::GetEnvironmentVariable($key, "Process")
            if ([string]::IsNullOrWhiteSpace($value)) {
                if ([string]::IsNullOrWhiteSpace($existing)) {
                    Set-Item -Path ("Env:" + $key) -Value ""
                }
            } else {
                Set-Item -Path ("Env:" + $key) -Value $value
            }
        }
    }
}

Write-Host "Running integration tests with current env..." -ForegroundColor Cyan
& $python -m pytest -m integration -rs
if ($LASTEXITCODE -ne 0) {
    throw "Integration tests failed with exit code $LASTEXITCODE"
}

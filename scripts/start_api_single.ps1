Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python virtual environment not found: $python"
}

$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and
    (
        ($_.CommandLine -match "uvicorn" -and $_.CommandLine -match "ai_chain_radar\.api\.app") -or
        ($_.CommandLine -match "scripts[\\\\/]start_api_single\.py")
    )
}
foreach ($proc in $procs) {
    if (Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue) {
        Stop-Process -Id $proc.ProcessId -Force
    }
}

Start-Sleep -Seconds 1
$newProc = Start-Process -FilePath $python -WorkingDirectory $repoRoot -ArgumentList @(
    "scripts/start_api_single.py"
) -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 2
if (-not (Get-Process -Id $newProc.Id -ErrorAction SilentlyContinue)) {
    throw "API process exited immediately. Please run '.venv\\Scripts\\python.exe scripts/start_api_single.py' for foreground logs."
}
try {
    $health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/health" -TimeoutSec 5
    if ($health.StatusCode -ne 200) {
        throw "Unexpected health status code: $($health.StatusCode)"
    }
} catch {
    Stop-Process -Id $newProc.Id -Force -ErrorAction SilentlyContinue
    throw "API failed health check after startup: $($_.Exception.Message)"
}

$active = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and
    (
        ($_.CommandLine -match "uvicorn" -and $_.CommandLine -match "ai_chain_radar\.api\.app") -or
        ($_.CommandLine -match "scripts[\\\\/]start_api_single\.py")
    )
})
$activeIds = @($active | ForEach-Object { [int]$_.ProcessId })
$roots = @(
    $active | Where-Object {
        $activeIds -notcontains [int]$_.ParentProcessId
    }
)
if ($roots.Count -gt 1) {
    Write-Warning "Detected more than one API process tree after startup. Please stop all API processes and retry."
}
Write-Host "API started. process_trees=$($roots.Count), raw_processes=$($active.Count), URL=http://127.0.0.1:8000/ui" -ForegroundColor Green

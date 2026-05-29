param(
    [string]$Date = "2026-05-28",
    [string]$FinmindStart = "2026-01-01",
    [string]$FinmindEnd = "2026-05-28",
    [string]$FinmindSymbols = "2330",
    [string]$SecTickers = "NVDA",
    [string]$OpenDartSymbols = "005930",
    [switch]$PreferCache,
    [switch]$StopApiBeforeRun,
    [switch]$SkipValidate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python virtual environment not found: $python"
}

function Import-DotEnv {
    param([string]$EnvFilePath)
    if (-not (Test-Path $EnvFilePath)) {
        return
    }
    $lines = Get-Content $EnvFilePath
    foreach ($line in $lines) {
        if ($line -match '^\s*#' -or $line -notmatch '=') {
            continue
        }
        $parts = $line.Split('=', 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ([string]::IsNullOrWhiteSpace($key)) {
            continue
        }
        $existing = [System.Environment]::GetEnvironmentVariable($key, "Process")
        if ([string]::IsNullOrWhiteSpace($existing)) {
            Set-Item -Path ("Env:" + $key) -Value $value
        }
    }
    Write-Host "Loaded .env into current process (existing non-empty env vars preserved)." -ForegroundColor DarkGray
}

Import-DotEnv -EnvFilePath (Join-Path $repoRoot ".env")

function Get-ApiProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "python.exe" -and
        (
            ($_.CommandLine -match "uvicorn" -and $_.CommandLine -match "ai_chain_radar\.api\.app") -or
            ($_.CommandLine -match "scripts[\\\\/]start_api_single\.py")
        )
    }
}

function Stop-ApiProcesses {
    param([array]$Processes)
    foreach ($proc in $Processes) {
        if (Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue) {
            Stop-Process -Id $proc.ProcessId -Force
        }
    }
}

function Invoke-ApiPreflight {
    $apiProcs = @(Get-ApiProcesses)
    if ($apiProcs.Count -eq 0) {
        return
    }
    $apiProcIds = @($apiProcs | ForEach-Object { [int]$_.ProcessId })
    $apiRoots = @(
        $apiProcs | Where-Object {
            $apiProcIds -notcontains [int]$_.ParentProcessId
        }
    )
    Write-Host ""
    Write-Host "Detected running API process trees: $($apiRoots.Count) (raw processes: $($apiProcs.Count))" -ForegroundColor Yellow
    foreach ($p in $apiProcs) {
        Write-Host "  PID=$($p.ProcessId) CMD=$($p.CommandLine)" -ForegroundColor DarkYellow
    }
    if ($apiProcs.Count -gt $apiRoots.Count) {
        Write-Host "Note: raw process count may include python launcher + child interpreter in one API instance." -ForegroundColor DarkYellow
    }
    if ($StopApiBeforeRun) {
        Stop-ApiProcesses -Processes $apiProcs
        Start-Sleep -Seconds 1
        Write-Host "Stopped API processes before pipeline run." -ForegroundColor Yellow
    } else {
        Write-Host "Tip: use -StopApiBeforeRun to avoid DuckDB lock contention during sync/score/brief." -ForegroundColor Yellow
    }
}

Invoke-ApiPreflight

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$CommandArgs
    )
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $python @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Name (exit code: $LASTEXITCODE)"
    }
}

if (-not $SkipValidate) {
    Invoke-Step -Name "ruff check" -CommandArgs @("-m", "ruff", "check", ".")
    Invoke-Step -Name "mypy" -CommandArgs @("-m", "mypy", "src")
    Invoke-Step -Name "pytest" -CommandArgs @("-m", "pytest")
}

Invoke-Step -Name "init-db" -CommandArgs @("-m", "ai_chain_radar.cli", "init-db")

$tushareArgs = @("-m", "ai_chain_radar.cli", "sync", "tushare", "--date", $Date)
if (-not $PreferCache) {
    $tushareArgs += "--no-prefer-cache"
}
Invoke-Step -Name "sync tushare" -CommandArgs $tushareArgs

Invoke-Step -Name "sync finmind" -CommandArgs @(
    "-m", "ai_chain_radar.cli", "sync", "finmind",
    "--start", $FinmindStart,
    "--end", $FinmindEnd,
    "--symbols", $FinmindSymbols
)

Invoke-Step -Name "sync sec" -CommandArgs @(
    "-m", "ai_chain_radar.cli", "sync", "sec",
    "--tickers", $SecTickers
)

Invoke-Step -Name "sync opendart" -CommandArgs @(
    "-m", "ai_chain_radar.cli", "sync", "opendart",
    "--symbols", $OpenDartSymbols,
    "--date", $Date
)

Invoke-Step -Name "extract evidence" -CommandArgs @(
    "-m", "ai_chain_radar.cli", "extract", "evidence",
    "--date", $Date
)

Invoke-Step -Name "score" -CommandArgs @("-m", "ai_chain_radar.cli", "score", "--date", $Date)
Invoke-Step -Name "review" -CommandArgs @(
    "-m", "ai_chain_radar.cli", "review",
    "--date", $Date,
    "--lookback", "10"
)
Invoke-Step -Name "dq report" -CommandArgs @(
    "-m", "ai_chain_radar.cli", "dq", "report",
    "--date", $Date
)
Invoke-Step -Name "brief" -CommandArgs @("-m", "ai_chain_radar.cli", "brief", "--date", $Date, "--format", "md")

Write-Host ""
Write-Host "==> summary" -ForegroundColor Cyan
@'
from ai_chain_radar.settings import get_settings
from ai_chain_radar.db.repository import Repository
repo = Repository()
q = """
select source, job_name, status, rows_read, rows_written, started_at
from source_run_log
order by started_at desc
limit 20
"""
print(repo.query_dataframe(q).to_string(index=False))

print("\ncredential availability:")
settings = get_settings()
cred = {
    "tushare": bool(settings.tushare_token.strip()),
    "finmind": bool(settings.finmind_token.strip()),
    "sec": bool(settings.sec_user_agent.strip()),
    "opendart": bool(settings.opendart_api_key.strip()),
}
for k, v in cred.items():
    print(f"  {k}: {'available' if v else 'missing'}")

latest = repo.query_dataframe(
    """
    SELECT source, status
    FROM (
      SELECT source, status, started_at,
             row_number() OVER (PARTITION BY source ORDER BY started_at DESC) AS rn
      FROM source_run_log
    ) t
    WHERE rn = 1
    ORDER BY source
    """
)
missing = latest[latest["status"] == "missing_credentials"]["source"].tolist()
ok = latest[latest["status"] == "ok"]["source"].tolist()
print("\nlatest missing_credentials sources:", ", ".join(missing) if missing else "none")
print("latest network-success sources(status=ok):", ", ".join(ok) if ok else "none")
'@ | & $python -

Write-Host ""
Write-Host "Done. Briefing: data/briefings/$Date.md" -ForegroundColor Green

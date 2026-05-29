param(
    [string]$Date = "2026-05-28",
    [string]$AcceptanceDate = "",
    [int]$MaxLogRows = 60,
    [string]$Reviewer = "Codex",
    [switch]$SkipValidate,
    [switch]$StopApiBeforeRun,
    [switch]$DispatchCiFirstRun,
    [string]$CiRepo = "",
    [switch]$CiDryRunOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Invoke-NativeStep {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$CommandArgs
    )
    if (-not $CommandArgs -or $CommandArgs.Count -eq 0) {
        throw "Step failed: $Name (empty command args)"
    }
    & $FilePath @CommandArgs
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Step failed: $Name (exit code: $exitCode)"
    }
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python virtual environment not found: $python"
}

if ([string]::IsNullOrWhiteSpace($AcceptanceDate)) {
    $AcceptanceDate = [DateTime]::UtcNow.ToString("yyyy-MM-dd")
}

Write-Host ""
Write-Host "==> v0.2 local pipeline" -ForegroundColor Cyan
$runAllArgs = @{
    Date = $Date
}
if ($SkipValidate) {
    $runAllArgs["SkipValidate"] = $true
}
if ($StopApiBeforeRun) {
    $runAllArgs["StopApiBeforeRun"] = $true
}
& ".\run_all.ps1" @runAllArgs
if (-not $?) {
    throw "Step failed: run_all.ps1"
}

Write-Host ""
Write-Host "==> export network acceptance" -ForegroundColor Cyan
Invoke-NativeStep -Name "export network acceptance" -FilePath $python -CommandArgs @(
    "-m", "ai_chain_radar.cli", "export", "network-acceptance",
    "--date", $AcceptanceDate,
    "--target-date", $Date,
    "--reviewer", $Reviewer,
    "--max-log-rows", [string]$MaxLogRows
)

Write-Host ""
Write-Host "==> export v0.2 completion audit" -ForegroundColor Cyan
Invoke-NativeStep -Name "export v0.2 completion audit" -FilePath $python -CommandArgs @(
    "-m", "ai_chain_radar.cli", "export", "v02-audit",
    "--date", $Date,
    "--reviewer", $Reviewer
)

if ($DispatchCiFirstRun) {
    Write-Host ""
    Write-Host "==> dispatch ci first run" -ForegroundColor Cyan
    $ciArgs = @{
        TargetDate = $Date
        AcceptanceDate = $AcceptanceDate
    }
    if (-not [string]::IsNullOrWhiteSpace($CiRepo)) {
        $ciArgs["Repo"] = $CiRepo
    }
    if ($CiDryRunOnly) {
        $ciArgs["DryRunOnly"] = $true
    }
    & ".\scripts\ci_first_run_dispatch.ps1" @ciArgs
    if (-not $?) {
        throw "Step failed: dispatch ci first run"
    }

    Write-Host ""
    Write-Host "==> refresh v0.2 completion audit (after ci step)" -ForegroundColor Cyan
    Invoke-NativeStep -Name "refresh v0.2 completion audit (after ci step)" -FilePath $python -CommandArgs @(
        "-m", "ai_chain_radar.cli", "export", "v02-audit",
        "--date", $Date,
        "--reviewer", $Reviewer
    )
}

Write-Host ""
Write-Host "v0.2 close-out finished." -ForegroundColor Green
Write-Host "  - docs/NETWORK_ACCEPTANCE_$AcceptanceDate.md" -ForegroundColor Green
Write-Host "  - docs/V0_2_COMPLETION_AUDIT_$Date.md" -ForegroundColor Green
Write-Host "  - docs/CI_FIRST_RUN.md" -ForegroundColor Green

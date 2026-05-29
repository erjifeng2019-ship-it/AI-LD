param(
    [string]$Repo = "",
    [string]$TargetDate = "",
    [string]$AcceptanceDate = "",
    [bool]$RunPipeline = $true,
    [int]$MaxLogRows = 40,
    [int]$WaitMinutes = 60,
    [switch]$DryRunOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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
}

function Resolve-RepoFromGitRemote {
    try {
        $remote = git remote get-url origin 2>$null
        if (-not $remote) {
            return ""
        }
        if ($remote -match "github\.com[:/](?<name>[^/]+/[^/.]+)(\.git)?$") {
            return $Matches["name"]
        }
        return ""
    } catch {
        return ""
    }
}

function Resolve-RepoFromEnv {
    $fromProcess = [Environment]::GetEnvironmentVariable("GITHUB_REPOSITORY", "Process")
    if (-not [string]::IsNullOrWhiteSpace($fromProcess)) {
        return $fromProcess
    }
    $fromUser = [Environment]::GetEnvironmentVariable("GITHUB_REPOSITORY", "User")
    if (-not [string]::IsNullOrWhiteSpace($fromUser)) {
        return $fromUser
    }
    return ""
}

function Ensure-GhAvailable {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI (gh) not found. Install it first: https://cli.github.com/"
    }
    $ghToken = [Environment]::GetEnvironmentVariable("GH_TOKEN", "Process")
    if (-not [string]::IsNullOrWhiteSpace($ghToken)) {
        return
    }
    & gh auth status | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI not authenticated. Run: gh auth login or set GH_TOKEN."
    }
}

function Write-CiFirstRunDoc {
    param(
        [string]$Status,
        [string]$RepoName,
        [string]$Target,
        [string]$Acceptance,
        [string]$RunId = "",
        [string]$WorkflowUrl = "",
        [string]$CommitSha = "",
        [string]$Conclusion = "",
        [string]$Note = ""
    )
    $path = "docs/CI_FIRST_RUN.md"
    $content = @"
# CI_FIRST_RUN

status: $Status

## Context
- workflow: integration-optional
- trigger: workflow_dispatch
- repo: $RepoName
- target_date: $Target
- acceptance_date: $Acceptance

## Inputs
- run_pipeline: $RunPipeline
- max_log_rows: $MaxLogRows

## Result
- workflow_url: $WorkflowUrl
- run_id: $RunId
- commit_sha: $CommitSha
- conclusion: $Conclusion

## Artifacts
- docs/NETWORK_ACCEPTANCE_$Acceptance.md
- data/briefings/$Target.md
- data/briefings/latest.md

## Notes
- $Note
"@
    $content | Set-Content -Encoding UTF8 $path
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
Import-DotEnv -EnvFilePath (Join-Path $repoRoot ".env")

$utcNow = [DateTime]::UtcNow
if ([string]::IsNullOrWhiteSpace($AcceptanceDate)) {
    $AcceptanceDate = $utcNow.ToString("yyyy-MM-dd")
}
if ([string]::IsNullOrWhiteSpace($TargetDate)) {
    $TargetDate = $utcNow.AddDays(-1).ToString("yyyy-MM-dd")
}
if ([string]::IsNullOrWhiteSpace($Repo)) {
    $Repo = Resolve-RepoFromGitRemote
}
if ([string]::IsNullOrWhiteSpace($Repo)) {
    $Repo = Resolve-RepoFromEnv
}

if ($DryRunOnly) {
    $repoForDoc = if ([string]::IsNullOrWhiteSpace($Repo)) { "(unknown)" } else { $Repo }
    Write-CiFirstRunDoc `
        -Status "PENDING" `
        -RepoName $repoForDoc `
        -Target $TargetDate `
        -Acceptance $AcceptanceDate `
        -Note "DryRunOnly=true; no GitHub workflow dispatched."
    Write-Host "Dry run done. Updated docs/CI_FIRST_RUN.md with PENDING status." -ForegroundColor Yellow
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Repo)) {
    Write-CiFirstRunDoc `
        -Status "PENDING" `
        -RepoName "(unknown)" `
        -Target $TargetDate `
        -Acceptance $AcceptanceDate `
        -Note "Cannot resolve GitHub repo. Pass -Repo owner/name explicitly."
    throw "Cannot resolve GitHub repo. Pass -Repo owner/name explicitly."
}

try {
    Ensure-GhAvailable
} catch {
    Write-CiFirstRunDoc `
        -Status "PENDING" `
        -RepoName $Repo `
        -Target $TargetDate `
        -Acceptance $AcceptanceDate `
        -Note ("GitHub auth unavailable: " + $_.Exception.Message)
    throw
}

$runPipelineStr = if ($RunPipeline) { "true" } else { "false" }
Write-Host "Dispatch workflow: repo=$Repo target=$TargetDate acceptance=$AcceptanceDate run_pipeline=$runPipelineStr"

& gh workflow run integration-optional.yml `
    -R $Repo `
    -f run_pipeline=$runPipelineStr `
    -f target_date=$TargetDate `
    -f acceptance_date=$AcceptanceDate `
    -f max_log_rows=$MaxLogRows
if ($LASTEXITCODE -ne 0) {
    Write-CiFirstRunDoc `
        -Status "PENDING" `
        -RepoName $Repo `
        -Target $TargetDate `
        -Acceptance $AcceptanceDate `
        -Note "Workflow dispatch failed. Check gh auth / repo permission."
    throw "Workflow dispatch failed. Check gh auth / repo permission."
}

Start-Sleep -Seconds 3

$runsJson = & gh run list `
    -R $Repo `
    --workflow integration-optional.yml `
    --event workflow_dispatch `
    --limit 10 `
    --json databaseId,status,conclusion,url,headSha,createdAt

$runs = $runsJson | ConvertFrom-Json
if (-not $runs -or $runs.Count -eq 0) {
    Write-CiFirstRunDoc `
        -Status "PENDING" `
        -RepoName $Repo `
        -Target $TargetDate `
        -Acceptance $AcceptanceDate `
        -Note "Workflow dispatched, but no run found yet."
    throw "Workflow dispatched, but no run found yet."
}

$run = $runs[0]
$runId = [string]$run.databaseId

Write-Host "Watching run id=$runId (up to $WaitMinutes minutes)..."
$watchOk = $true
try {
    & gh run watch $runId -R $Repo --interval 20 --exit-status
} catch {
    $watchOk = $false
}

$viewJson = & gh run view $runId -R $Repo --json conclusion,url,headSha,status
$view = $viewJson | ConvertFrom-Json

$conclusion = [string]$view.conclusion
$status = if ($conclusion -eq "success") { "PASS" } elseif ($conclusion) { "FAIL" } else { "PENDING" }
$note = if ($status -eq "PASS") {
    "Workflow completed successfully."
} elseif (-not $watchOk) {
    "Workflow did not complete successfully. Check run URL for details."
} else {
    "Workflow status unresolved; check run URL."
}

Write-CiFirstRunDoc `
    -Status $status `
    -RepoName $Repo `
    -Target $TargetDate `
    -Acceptance $AcceptanceDate `
    -RunId $runId `
    -WorkflowUrl ([string]$view.url) `
    -CommitSha ([string]$view.headSha) `
    -Conclusion $conclusion `
    -Note $note

if ($status -eq "PASS") {
    Write-Host "CI first run recorded as PASS." -ForegroundColor Green
    exit 0
}

throw "CI first run did not pass. Status=$status, conclusion=$conclusion"

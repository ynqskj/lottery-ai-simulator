[CmdletBinding()]
param(
    [string]$DataDir = "data/normalized",
    [string]$ReportDir = "reports/latest",
    [string]$RecommendationDir = "data/recommendations",
    [string]$Game = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Utf8 = [System.Text.UTF8Encoding]::new()
[Console]::InputEncoding = $Utf8
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot
$env:PYTHONPATH = "src"
$PythonExecutable = $env:LOTTERY_PYTHON
if (-not $PythonExecutable -and -not $env:LOTTERY_CLI_EXE) {
    $LocalPython = Join-Path $RepoRoot ".venv/Scripts/python.exe"
    if (Test-Path -LiteralPath $LocalPython) { $PythonExecutable = $LocalPython }
    else { $PythonExecutable = (Get-Command python -ErrorAction Stop).Source }
}

$Games = @(
    [pscustomobject]@{ Code = "3d"; Csv = "$DataDir/fucai3d.csv"; Update = "update-3d"; Verify = "verify-recommend-3d"; Extra = @() },
    [pscustomobject]@{ Code = "pl3"; Csv = "$DataDir/pl3.csv"; Update = "update-pl3"; Verify = "verify-recommend-pl3"; Extra = @() },
    [pscustomobject]@{ Code = "pl5"; Csv = "$DataDir/pl5.csv"; Update = "update-pl5"; Verify = "verify-recommend-pl5"; Extra = @() },
    [pscustomobject]@{ Code = "qxc"; Csv = "$DataDir/qxc.csv"; Update = "update-qxc"; Verify = "verify-recommend-qxc"; Extra = @() },
    [pscustomobject]@{ Code = "qlc"; Csv = "$DataDir/qlc.csv"; Update = "update-qlc"; Verify = "verify-recommend-qlc"; Extra = @() },
    [pscustomobject]@{ Code = "kl8"; Csv = "$DataDir/kl8.csv"; Update = "update-kl8"; Verify = "verify-recommend-kl8"; Extra = @("--pick-size", "10") },
    [pscustomobject]@{ Code = "ssq"; Csv = "$DataDir/ssq.csv"; Update = "update-ssq"; Verify = "verify-recommend-ssq"; Extra = @() },
    [pscustomobject]@{ Code = "dlt"; Csv = "$DataDir/dlt.csv"; Update = "update-dlt"; Verify = "verify-recommend-dlt"; Extra = @() }
)

if (-not $Game) {
    throw "Please specify -Game <code>."
}

$AllowedGames = @($Games | ForEach-Object { $_.Code })
if ($AllowedGames -notcontains $Game) {
    throw "Unsupported -Game '$Game'. Allowed: $($AllowedGames -join ', ')"
}

$SelectedGame = @($Games | Where-Object { $_.Code -eq $Game })[0]

function Ensure-Directory {
    param([string]$Path)

    if (-not $DryRun) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Get-LotteryCommandText {
    param([string[]]$Arguments)

    if ($env:LOTTERY_CLI_EXE) {
        return "`"$env:LOTTERY_CLI_EXE`" --cli " + ($Arguments -join " ")
    }
    return "`"$PythonExecutable`" -m lottery_sim.cli " + ($Arguments -join " ")
}

function Invoke-LotteryCli {
    param([string[]]$Arguments)

    if ($env:LOTTERY_CLI_EXE) {
        & $env:LOTTERY_CLI_EXE --cli @Arguments
        return
    }
    & $PythonExecutable -m lottery_sim.cli @Arguments
}

function Invoke-LotteryCommand {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    $commandText = Get-LotteryCommandText -Arguments $Arguments
    Write-Host "[$Name] $commandText"

    if ($DryRun) {
        return
    }

    Invoke-LotteryCli -Arguments $Arguments
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        throw "Command failed with exit code $($exitCode): $Name"
    }
}

Ensure-Directory -Path $DataDir
Ensure-Directory -Path $ReportDir
Ensure-Directory -Path $RecommendationDir

Invoke-LotteryCommand -Name "update-$($SelectedGame.Code)" -Arguments @($SelectedGame.Update, "--csv", $SelectedGame.Csv)

$gameDir = Join-Path $RecommendationDir $SelectedGame.Code
$recordFiles = @()
if (Test-Path -LiteralPath $gameDir) {
    $recordFiles = @(Get-ChildItem -LiteralPath $gameDir -Filter "*.csv" | Sort-Object FullName)
}

if ($DryRun -and $recordFiles.Count -eq 0) {
    $sampleRecord = Join-Path $gameDir "<issue>.csv"
    Invoke-LotteryCommand -Name "verify-$($SelectedGame.Code)" -Arguments (@(
        $SelectedGame.Verify,
        "--csv",
        $SelectedGame.Csv,
        "--records",
        $sampleRecord,
        "--output",
        $sampleRecord
    ) + $SelectedGame.Extra)
}
else {
    foreach ($recordFile in $recordFiles) {
        Invoke-LotteryCommand -Name "verify-$($SelectedGame.Code)-$($recordFile.BaseName)" -Arguments (@(
            $SelectedGame.Verify,
            "--csv",
            $SelectedGame.Csv,
            "--records",
            $recordFile.FullName,
            "--output",
            $recordFile.FullName
        ) + $SelectedGame.Extra)
    }
}

$summaryPath = Join-Path $ReportDir "recommendation-summary.txt"
if ($DryRun) {
    Invoke-LotteryCommand -Name "summarize-recommendations" -Arguments @(
        "summarize-recommendations",
        "--records",
        "$RecommendationDir/*/*.csv",
        "--output",
        $summaryPath
    )
}
else {
    $recordPaths = @(Get-ChildItem -Path $RecommendationDir -Recurse -Filter "*.csv" | Sort-Object FullName)
    if ($recordPaths.Count -gt 0) {
        $summaryArgs = @("summarize-recommendations", "--records")
        foreach ($recordPath in $recordPaths) {
            $summaryArgs += $recordPath.FullName
        }
        $summaryArgs += @("--output", $summaryPath)
        Invoke-LotteryCommand -Name "summarize-recommendations" -Arguments $summaryArgs
    }
    else {
        Write-Host "[summarize-recommendations] no recommendation records found"
    }
}

Write-Host "Update workflow finished for: $($SelectedGame.Code)"

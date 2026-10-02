[CmdletBinding()]
param(
    [string]$DataDir = "data/normalized",
    [string]$ReportDir = "reports/latest",
    [int]$Seed = 20260505,
    [string]$Seeds = "1,2,3,4,5",
    [int]$Window = 30,
    [switch]$SkipNormalize,
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
if (-not $PythonExecutable) {
    $LocalPython = Join-Path $RepoRoot ".venv/Scripts/python.exe"
    if (Test-Path -LiteralPath $LocalPython) { $PythonExecutable = $LocalPython }
    else { $PythonExecutable = (Get-Command python -ErrorAction Stop).Source }
}

$fucai3dCsv = "$DataDir/fucai3d.csv"
$pl3Csv = "$DataDir/pl3.csv"
$pl5Csv = "$DataDir/pl5.csv"
$qxcCsv = "$DataDir/qxc.csv"
$qlcCsv = "$DataDir/qlc.csv"
$kl8Csv = "$DataDir/kl8.csv"
$ssqCsv = "$DataDir/ssq.csv"
$dltCsv = "$DataDir/dlt.csv"

function Ensure-Directory {
    param([string]$Path)

    if (-not $DryRun) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Assert-DataFile {
    param([string]$Path)

    if (-not $DryRun -and -not (Test-Path -LiteralPath $Path)) {
        throw "Data file not found: $Path. Run without -SkipNormalize first."
    }
}

function Invoke-LotteryCommand {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [string]$OutputFile = ""
    )

    $commandText = "`"$PythonExecutable`" -m lottery_sim.cli " + ($Arguments -join " ")
    if ($OutputFile) {
        $commandText = "$commandText > $OutputFile"
    }
    Write-Host "[$Name] $commandText"

    if ($DryRun) {
        return
    }

    if ($OutputFile) {
        $output = & $PythonExecutable -m lottery_sim.cli @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        $output | Set-Content -Path $OutputFile -Encoding UTF8
        Write-Host "  -> $OutputFile"
    }
    else {
        & $PythonExecutable -m lottery_sim.cli @Arguments
        $exitCode = $LASTEXITCODE
    }

    if ($exitCode -ne 0) {
        if ($OutputFile -and $output) {
            $output | Write-Host
        }
        throw "Command failed with exit code $($exitCode): $Name"
    }
}

Ensure-Directory -Path $DataDir
Ensure-Directory -Path $ReportDir

if (-not $SkipNormalize) {
    Invoke-LotteryCommand -Name "normalize-3d" -Arguments @("normalize-3d", "--output", $fucai3dCsv)
    Invoke-LotteryCommand -Name "normalize-pl3" -Arguments @("normalize-pl3", "--output", $pl3Csv)
    Invoke-LotteryCommand -Name "normalize-pl5" -Arguments @("normalize-pl5", "--output", $pl5Csv)
    Invoke-LotteryCommand -Name "normalize-qxc" -Arguments @("normalize-qxc", "--output", $qxcCsv)
    Invoke-LotteryCommand -Name "normalize-qlc" -Arguments @("normalize-qlc", "--output", $qlcCsv)
    Invoke-LotteryCommand -Name "normalize-kl8" -Arguments @("normalize-kl8", "--output", $kl8Csv)
    Invoke-LotteryCommand -Name "normalize-ssq" -Arguments @("normalize-ssq", "--output", $ssqCsv)
    Invoke-LotteryCommand -Name "normalize-dlt" -Arguments @("normalize-dlt", "--output", $dltCsv)
}
else {
    Assert-DataFile -Path $fucai3dCsv
    Assert-DataFile -Path $pl3Csv
    Assert-DataFile -Path $pl5Csv
    Assert-DataFile -Path $qxcCsv
    Assert-DataFile -Path $qlcCsv
    Assert-DataFile -Path $kl8Csv
    Assert-DataFile -Path $ssqCsv
    Assert-DataFile -Path $dltCsv
}

Invoke-LotteryCommand -Name "backtest-3d" -Arguments @("backtest-3d", "--csv", $fucai3dCsv, "--seed", "$Seed") -OutputFile "$ReportDir/backtest-3d.txt"
Invoke-LotteryCommand -Name "compare-3d" -Arguments @("compare-3d", "--csv", $fucai3dCsv, "--seed", "$Seed", "--window", "$Window") -OutputFile "$ReportDir/compare-3d.txt"
Invoke-LotteryCommand -Name "stability-3d" -Arguments @("stability-3d", "--csv", $fucai3dCsv, "--seeds", $Seeds, "--window", "$Window") -OutputFile "$ReportDir/stability-3d.txt"
Invoke-LotteryCommand -Name "recommend-3d" -Arguments @("recommend-3d", "--csv", $fucai3dCsv, "--seed", "$Seed", "--window", "$Window", "--count", "10") -OutputFile "$ReportDir/recommend-3d.txt"

Invoke-LotteryCommand -Name "backtest-pl3" -Arguments @("backtest-pl3", "--csv", $pl3Csv, "--seed", "$Seed") -OutputFile "$ReportDir/backtest-pl3.txt"
Invoke-LotteryCommand -Name "compare-pl3" -Arguments @("compare-pl3", "--csv", $pl3Csv, "--seed", "$Seed", "--window", "$Window") -OutputFile "$ReportDir/compare-pl3.txt"
Invoke-LotteryCommand -Name "stability-pl3" -Arguments @("stability-pl3", "--csv", $pl3Csv, "--seeds", $Seeds, "--window", "$Window") -OutputFile "$ReportDir/stability-pl3.txt"
Invoke-LotteryCommand -Name "recommend-pl3" -Arguments @("recommend-pl3", "--csv", $pl3Csv, "--seed", "$Seed", "--window", "$Window", "--count", "10") -OutputFile "$ReportDir/recommend-pl3.txt"

Invoke-LotteryCommand -Name "backtest-pl5" -Arguments @("backtest-pl5", "--csv", $pl5Csv, "--seed", "$Seed") -OutputFile "$ReportDir/backtest-pl5.txt"
Invoke-LotteryCommand -Name "compare-pl5" -Arguments @("compare-pl5", "--csv", $pl5Csv, "--seed", "$Seed", "--window", "$Window") -OutputFile "$ReportDir/compare-pl5.txt"
Invoke-LotteryCommand -Name "stability-pl5" -Arguments @("stability-pl5", "--csv", $pl5Csv, "--seeds", $Seeds, "--window", "$Window") -OutputFile "$ReportDir/stability-pl5.txt"
Invoke-LotteryCommand -Name "recommend-pl5" -Arguments @("recommend-pl5", "--csv", $pl5Csv, "--seed", "$Seed", "--window", "$Window", "--count", "10") -OutputFile "$ReportDir/recommend-pl5.txt"

Invoke-LotteryCommand -Name "backtest-qxc" -Arguments @("backtest-qxc", "--csv", $qxcCsv, "--seed", "$Seed") -OutputFile "$ReportDir/backtest-qxc.txt"
Invoke-LotteryCommand -Name "compare-qxc" -Arguments @("compare-qxc", "--csv", $qxcCsv, "--seed", "$Seed", "--window", "$Window") -OutputFile "$ReportDir/compare-qxc.txt"
Invoke-LotteryCommand -Name "stability-qxc" -Arguments @("stability-qxc", "--csv", $qxcCsv, "--seeds", $Seeds, "--window", "$Window") -OutputFile "$ReportDir/stability-qxc.txt"
Invoke-LotteryCommand -Name "recommend-qxc" -Arguments @("recommend-qxc", "--csv", $qxcCsv, "--seed", "$Seed", "--window", "$Window", "--count", "10") -OutputFile "$ReportDir/recommend-qxc.txt"

Invoke-LotteryCommand -Name "backtest-qlc" -Arguments @("backtest-qlc", "--csv", $qlcCsv, "--seed", "$Seed") -OutputFile "$ReportDir/backtest-qlc.txt"
Invoke-LotteryCommand -Name "compare-qlc" -Arguments @("compare-qlc", "--csv", $qlcCsv, "--seed", "$Seed", "--window", "$Window") -OutputFile "$ReportDir/compare-qlc.txt"
Invoke-LotteryCommand -Name "stability-qlc" -Arguments @("stability-qlc", "--csv", $qlcCsv, "--seeds", $Seeds, "--window", "$Window") -OutputFile "$ReportDir/stability-qlc.txt"
Invoke-LotteryCommand -Name "recommend-qlc" -Arguments @("recommend-qlc", "--csv", $qlcCsv, "--seed", "$Seed", "--window", "$Window", "--count", "10") -OutputFile "$ReportDir/recommend-qlc.txt"

Invoke-LotteryCommand -Name "backtest-kl8" -Arguments @("backtest-kl8", "--csv", $kl8Csv, "--pick-size", "10", "--seed", "$Seed") -OutputFile "$ReportDir/backtest-kl8.txt"
Invoke-LotteryCommand -Name "compare-kl8" -Arguments @("compare-kl8", "--csv", $kl8Csv, "--pick-size", "10", "--seed", "$Seed", "--window", "$Window") -OutputFile "$ReportDir/compare-kl8.txt"
Invoke-LotteryCommand -Name "stability-kl8" -Arguments @("stability-kl8", "--csv", $kl8Csv, "--pick-size", "10", "--seeds", $Seeds, "--window", "$Window") -OutputFile "$ReportDir/stability-kl8.txt"
Invoke-LotteryCommand -Name "recommend-kl8" -Arguments @("recommend-kl8", "--csv", $kl8Csv, "--pick-size", "10", "--seed", "$Seed", "--window", "$Window", "--count", "10") -OutputFile "$ReportDir/recommend-kl8.txt"

Invoke-LotteryCommand -Name "backtest-ssq" -Arguments @("backtest-ssq", "--csv", $ssqCsv, "--seed", "$Seed") -OutputFile "$ReportDir/backtest-ssq.txt"
Invoke-LotteryCommand -Name "compare-ssq" -Arguments @("compare-ssq", "--csv", $ssqCsv, "--seed", "$Seed", "--window", "$Window") -OutputFile "$ReportDir/compare-ssq.txt"
Invoke-LotteryCommand -Name "stability-ssq" -Arguments @("stability-ssq", "--csv", $ssqCsv, "--seeds", $Seeds, "--window", "$Window") -OutputFile "$ReportDir/stability-ssq.txt"
Invoke-LotteryCommand -Name "recommend-ssq" -Arguments @("recommend-ssq", "--csv", $ssqCsv, "--seed", "$Seed", "--window", "$Window", "--count", "10") -OutputFile "$ReportDir/recommend-ssq.txt"

Invoke-LotteryCommand -Name "backtest-dlt" -Arguments @("backtest-dlt", "--csv", $dltCsv, "--seed", "$Seed") -OutputFile "$ReportDir/backtest-dlt.txt"
Invoke-LotteryCommand -Name "compare-dlt" -Arguments @("compare-dlt", "--csv", $dltCsv, "--seed", "$Seed", "--window", "$Window") -OutputFile "$ReportDir/compare-dlt.txt"
Invoke-LotteryCommand -Name "stability-dlt" -Arguments @("stability-dlt", "--csv", $dltCsv, "--seeds", $Seeds, "--window", "$Window") -OutputFile "$ReportDir/stability-dlt.txt"
Invoke-LotteryCommand -Name "recommend-dlt" -Arguments @("recommend-dlt", "--csv", $dltCsv, "--seed", "$Seed", "--window", "$Window", "--count", "10") -OutputFile "$ReportDir/recommend-dlt.txt"

Write-Host "Reports written to: $ReportDir"

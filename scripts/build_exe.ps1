[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [string]$PythonPath
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$env:PYTHONPATH = "src"
$AppName = "lottery-ai-simulator"
$DistDir = Join-Path $RepoRoot "dist\$AppName"
$BuildDir = Join-Path $RepoRoot "build\$AppName"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PythonExe = if ($PythonPath) { $PythonPath } elseif (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }

function Test-PyInstaller {
    & $PythonExe -m PyInstaller --version *> $null
    return ($LASTEXITCODE -eq 0)
}

if (-not $SkipInstall) {
    Write-Host "Installing Python dependencies..."
    & $PythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Python dependencies."
    }
}

if (-not (Test-PyInstaller)) {
    if ($SkipInstall) {
        throw "PyInstaller is not installed. Run without -SkipInstall or install it manually."
    }
    Write-Host "Installing PyInstaller..."
    & $PythonExe -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install PyInstaller."
    }
}

foreach ($path in @($DistDir, $BuildDir)) {
    $resolvedTarget = [System.IO.Path]::GetFullPath($path)
    if (-not $resolvedTarget.StartsWith(([string]$RepoRoot + [System.IO.Path]::DirectorySeparatorChar), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Build target is outside the repository: $resolvedTarget"
    }
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

$pyinstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--onedir",
    "--name",
    $AppName,
    "--paths",
    "src",
    "--collect-submodules",
    "fastapi",
    "--collect-submodules",
    "starlette",
    "--collect-submodules",
    "uvicorn",
    "--collect-submodules",
    "pydantic",
    "--exclude-module",
    "tests",
    "launcher.py"
)

& $PythonExe -m PyInstaller @pyinstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

Copy-Item -Path "scripts" -Destination (Join-Path $DistDir "scripts") -Recurse -Force
# Windows PowerShell 5.1 needs a BOM to recognize UTF-8 script source.
Get-ChildItem -LiteralPath (Join-Path $DistDir "scripts") -Filter "*.ps1" | ForEach-Object {
    $scriptText = [System.IO.File]::ReadAllText($_.FullName, [System.Text.Encoding]::UTF8)
    [System.IO.File]::WriteAllText($_.FullName, $scriptText, [System.Text.UTF8Encoding]::new($true))
}
Copy-Item -LiteralPath "README.md", "LICENSE" -Destination $DistDir -Force
Copy-Item -LiteralPath "assets" -Destination $DistDir -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "data\normalized") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "data\users") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "reports\latest") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "reports\users") | Out-Null

Write-Host "EXE build finished:"
Write-Host (Join-Path $DistDir "$AppName.exe")

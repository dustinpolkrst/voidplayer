param(
    [switch]$Test,
    [switch]$NoRun,
    [string]$Launcher = "animeplayer",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$RustDir = Join-Path $RepoRoot "rust"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & $Command
}

Set-Location $RepoRoot

Invoke-Step "Sync Python dependencies" {
    uv sync --dev
}

Invoke-Step "Check Rust crate" {
    Push-Location $RustDir
    try {
        cargo check
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "Build and install voidplayer_core with maturin" {
    Push-Location $RustDir
    try {
        uv run maturin develop
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "Verify Rust core import" {
    uv run python -c "from ffmpeg_pywrapper._core import rust_available; import voidplayer_core; print('Rust available:', rust_available()); print('Native module:', voidplayer_core.__file__)"
}

if ($Test) {
    Invoke-Step "Run test suite with Rust core enabled" {
        uv run pytest
    }
}

if (-not $NoRun) {
    Invoke-Step "Run $Launcher" {
        if ($AppArgs -and $AppArgs.Count -gt 0) {
            uv run $Launcher @AppArgs
        }
        else {
            uv run $Launcher
        }
    }
}

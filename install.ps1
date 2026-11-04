# PDFTrans Pro installer (Windows PowerShell)
#
# Usage 1 (recommended, one-liner remote install) - copy & run in PowerShell:
#   irm https://raw.githubusercontent.com/palelunar/pdftrans-pro/main/install.ps1 | iex
#
# Usage 2 (local script, per-tool selection):
#   .\install.ps1                        # install into every detected tool
#   .\install.ps1 -Tool codex            # Codex only
#   .\install.ps1 -Tool claude           # Claude Code only
#   .\install.ps1 -Tool opencode         # opencode only
#   .\install.ps1 -Tool dsh -HarnessPath C:\path\to\deepseek-harness
param(
    [ValidateSet('all', 'codex', 'claude', 'opencode', 'dsh')]
    [string]$Tool = 'all',
    [string]$HarnessPath = $env:DSH_HOME
)

$ErrorActionPreference = 'Stop'

# ---- Locate sources: local script uses the repo copy; remote (irm|iex) mode downloads a GitHub archive ----
$ScriptPath = $MyInvocation.MyCommand.Path
$LocalSrc1 = $null; $LocalSrc2 = $null; $TmpClone = $null
if ($ScriptPath) {
    $ScriptDir = Split-Path -Parent $ScriptPath
    $LocalSrc1 = Join-Path $ScriptDir 'claude-code\pdftrans-pro'
    $LocalSrc2 = Join-Path $ScriptDir 'deepseek-harness\pdftrans-pro'
} else {
    $TmpClone = Join-Path $env:TEMP ('pdftrans-install-' + [guid]::NewGuid().ToString('N'))
    $RepoZip = Join-Path $TmpClone 'repo.zip'
    Write-Host '[install] remote mode: downloading skill repo...' -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $TmpClone | Out-Null
    Invoke-WebRequest -Uri 'https://github.com/palelunar/pdftrans-pro/archive/refs/heads/main.zip' -OutFile $RepoZip
    Expand-Archive -LiteralPath $RepoZip -DestinationPath $TmpClone -Force
    $RepoDir = Join-Path $TmpClone 'pdftrans-pro-main'
    if (-not (Test-Path $RepoDir)) { throw 'Download failed. Check your network/proxy and retry, or use local script mode.' }
    $LocalSrc1 = Join-Path $RepoDir 'claude-code\pdftrans-pro'
    $LocalSrc2 = Join-Path $RepoDir 'deepseek-harness\pdftrans-pro'
}

$installed = $false

function Install-Into([string]$Src, [string]$DstDir, [string]$ToolName) {
    if (-not (Test-Path $Src)) { Write-Warning "Source dir not found: $Src (skipped)"; return }
    New-Item -ItemType Directory -Force -Path $DstDir | Out-Null
    $dst = Join-Path $DstDir 'pdftrans-pro'
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    Copy-Item $Src $dst -Recurse -Force
    Write-Host "[install] $ToolName -> $dst (installed; takes effect after restarting the session)" -ForegroundColor Green
    $script:installed = $true
}

try {
    switch ($Tool) {
        'codex'    { Install-Into $LocalSrc1 "$HOME\.agents\skills" 'Codex' }
        'claude'   { Install-Into $LocalSrc1 "$HOME\.claude\skills" 'Claude Code' }
        'opencode' { Install-Into $LocalSrc1 "$HOME\.config\opencode\skill" 'opencode' }
        'dsh' {
            if (-not $HarnessPath) { throw 'Provide -HarnessPath <deepseek-harness checkout path> or set env var DSH_HOME' }
            Install-Into $LocalSrc2 (Join-Path $HarnessPath '.agents\skills') 'DeepSeek Harness'
        }
        default {
            if ((Test-Path "$HOME\.codex") -or (Test-Path "$HOME\.agents")) { Install-Into $LocalSrc1 "$HOME\.agents\skills" 'Codex' }
            if (Test-Path "$HOME\.claude") { Install-Into $LocalSrc1 "$HOME\.claude\skills" 'Claude Code' }
            if (Test-Path "$HOME\.config\opencode") { Install-Into $LocalSrc1 "$HOME\.config\opencode\skill" 'opencode' }
            if ($HarnessPath -and (Test-Path $HarnessPath)) { Install-Into $LocalSrc2 (Join-Path $HarnessPath '.agents\skills') 'DeepSeek Harness' }
            if (-not $installed) { Write-Warning 'No supported tool directories detected. Local mode: .\install.ps1 -Tool codex | claude | opencode | dsh -HarnessPath <path>' }
        }
    }
}
finally {
    if ($TmpClone -and (Test-Path $TmpClone)) { Remove-Item $TmpClone -Recurse -Force }
}

if ($installed) {
    Write-Host "[install] Done. Restart the tool's session, then say it in natural language (e.g. 'translate this PDF') and pdftrans-pro will be picked up automatically." -ForegroundColor Green
}

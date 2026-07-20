#!/usr/bin/env pwsh
# Install every ABP agent-skill plugin into Claude Code in one go (Windows / PowerShell).
#
# Most users only need a few plugins for the areas they work in (see README).
# This is a convenience for ABP-heavy setups that genuinely want all of them.
#
# Requires the `claude` CLI on PATH. Run:  pwsh -File scripts/install-all-plugins.ps1
# Override the source with:  $env:ABP_SKILLS_REPO = 'owner/repo'  before running.
$ErrorActionPreference = 'Stop'

$Repo   = if ($env:ABP_SKILLS_REPO) { $env:ABP_SKILLS_REPO } else { 'abpframework/abp-skills' }
$Market = 'abp-agent-skills'   # marketplace name from .claude-plugin/marketplace.json

Write-Host "==> Adding / refreshing the marketplace ($Repo)"
$addOut = claude plugin marketplace add $Repo 2>&1
if ($LASTEXITCODE -ne 0) {
    # An already-registered marketplace is fine; anything else is a real failure.
    if ($addOut -notmatch 'already (exists|added|installed|registered)') {
        Write-Error "Failed to add marketplace '$Repo': $addOut"
    }
}
claude plugin marketplace update $Market       # a stale cache won't list new plugins

Write-Host '==> Reading the plugin list from the local marketplace cache'
# Read from the on-disk cache (works for private repos and needs no network).
$configDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE '.claude' }
$manifest  = Join-Path $configDir "plugins\marketplaces\$Market\.claude-plugin\marketplace.json"
$plugins   = (Get-Content $manifest -Raw | ConvertFrom-Json).plugins.name
if (-not $plugins -or $plugins.Count -eq 0) {
    Write-Error "No plugins found in $manifest"
}

Write-Host '==> Installing'
$failed = @()
foreach ($p in $plugins) {
    claude plugin install "$p@$Market"
    if ($LASTEXITCODE -ne 0) { $failed += $p }
}

claude plugin list | Select-String $Market
if ($failed.Count -gt 0) {
    Write-Error "Failed to install: $($failed -join ', ')"
}
Write-Host '==> Done. Restart Claude Code (or run /reload-plugins) to load the skills.'

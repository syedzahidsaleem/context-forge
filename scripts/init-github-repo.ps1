<#
.SYNOPSIS
    Automated GitHub Repository Provisioning & Linking Script for ContextForge (PowerShell)
.DESCRIPTION
    Provisions remote repository under 'syedzahidsaleem', configures local Git credentials,
    sets default branch rules, and links origin.
.PARAMETER RepoName
    Optional custom repository name (defaults to 'context-forge' derived from project spec).
.PARAMETER Public
    Switch to make the repository public instead of private (default is private).
#>

[CmdletBinding()]
param (
    [string]$RepoName = "context-forge",
    [switch]$Public
)

$ErrorActionPreference = "Stop"

# User Identity Invariants
$TargetUser = "syedzahidsaleem"
$TargetEmail = "syedzahidsaleem2@gmail.com"

# Sanitization helper
$SanitizedRepoName = $RepoName.ToLower() -replace '[^a-z0-9\-]', '-' -replace '-+', '-' -replace '^-|-$', ''
if ([string]::IsNullOrWhiteSpace($SanitizedRepoName)) {
    $SanitizedRepoName = "context-forge"
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " ContextForge GitHub Repository Setup" -ForegroundColor Cyan
Write-Host " Target Owner: $TargetUser ($TargetEmail)" -ForegroundColor Cyan
Write-Host " Target Repo:  $SanitizedRepoName" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Enforce Local Git Configuration
Write-Host "[1/4] Configuring local Git identity and settings..." -ForegroundColor Yellow
git config user.name $TargetUser
git config user.email $TargetEmail
git config pull.rebase true
git config push.autoSetupRemote true
git config core.autocrlf false
git config core.eol lf
git branch -M main

Write-Host "  ✓ Local author: $(git config user.name) <$(git config user.email)>" -ForegroundColor Green
Write-Host "  ✓ Default branch: main" -ForegroundColor Green
Write-Host "  ✓ Core settings: pull.rebase=true, core.autocrlf=false, core.eol=lf" -ForegroundColor Green

# 2. Check GitHub CLI Status
Write-Host "`n[2/4] Checking GitHub CLI (gh) authentication..." -ForegroundColor Yellow
$ghAvailable = $false
$ghAuthed = $false

try {
    $null = Get-Command gh -ErrorAction Stop
    $ghAvailable = $true
    $authStatus = gh auth status 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0 -or $authStatus -match "Logged in to github.com") {
        $ghAuthed = $true
    }
} catch {
    $ghAvailable = $false
}

$VisibilityFlag = if ($Public) { "--public" } else { "--private" }
$RemoteUrl = "https://github.com/$TargetUser/$SanitizedRepoName.git"

# 3. Create or Link Remote Repository
if ($ghAvailable -and $ghAuthed) {
    Write-Host "[3/4] GitHub CLI authenticated. Provisioning remote repository..." -ForegroundColor Yellow
    
    # Check if repository already exists on GitHub
    $repoCheck = gh repo view "$TargetUser/$SanitizedRepoName" 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ℹ Remote repository '$TargetUser/$SanitizedRepoName' already exists." -ForegroundColor Cyan
    } else {
        Write-Host "  Creating $VisibilityFlag remote repo '$TargetUser/$SanitizedRepoName'..." -ForegroundColor Yellow
        gh repo create "$TargetUser/$SanitizedRepoName" $VisibilityFlag --confirm
        Write-Host "  ✓ Remote repository created successfully!" -ForegroundColor Green
    }
    
    # Configure Git Remote Origin
    $existingRemote = git remote get-url origin 2>$null
    if ($LASTEXITCODE -eq 0 -and $existingRemote) {
        git remote set-url origin $RemoteUrl
        Write-Host "  ✓ Updated existing 'origin' remote to $RemoteUrl" -ForegroundColor Green
    } else {
        git remote add origin $RemoteUrl
        Write-Host "  ✓ Added 'origin' remote pointing to $RemoteUrl" -ForegroundColor Green
    }
} else {
    Write-Host "[3/4] GitHub CLI (gh) is not installed or not logged in." -ForegroundColor Red
    Write-Host "`n======================================================================" -ForegroundColor Yellow
    Write-Host " MANUAL FALLBACK INSTRUCTIONS:" -ForegroundColor Yellow
    Write-Host " 1. Open your browser and navigate to: https://github.com/new" -ForegroundColor Yellow
    Write-Host " 2. Set Repository Name: $SanitizedRepoName" -ForegroundColor Yellow
    Write-Host " 3. Select Private (or Public) and DO NOT initialize with README/gitignore." -ForegroundColor Yellow
    Write-Host " 4. Click 'Create repository'." -ForegroundColor Yellow
    Write-Host " 5. Run the following command in your terminal to link origin:" -ForegroundColor Yellow
    Write-Host "    git remote add origin $RemoteUrl" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Yellow

    # Try setting remote anyway if origin doesn't exist
    $existingRemote = git remote get-url origin 2>$null
    if ($LASTEXITCODE -ne 0) {
        git remote add origin $RemoteUrl
        Write-Host "  ✓ Added pre-configured 'origin' remote: $RemoteUrl" -ForegroundColor Green
    }
}

# 4. Summary Status
Write-Host "`n[4/4] Repository Provisioning Summary:" -ForegroundColor Yellow
Write-Host "  Repository Name: $SanitizedRepoName" -ForegroundColor White
Write-Host "  Remote URL:      $RemoteUrl" -ForegroundColor White
Write-Host "  Current Branch:  $(git branch --show-current)" -ForegroundColor White
Write-Host "`nNext Step: Run the initial baseline commit sequence to push Main." -ForegroundColor Green

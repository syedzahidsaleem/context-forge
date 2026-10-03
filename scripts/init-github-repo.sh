#!/usr/bin/env bash
# ==============================================================================
# Automated GitHub Repository Provisioning & Linking Script (Bash)
# ContextForge — Release Engineering Tooling
# ==============================================================================

set -euo pipefail

TARGET_USER="syedzahidsaleem"
TARGET_EMAIL="syedzahidsaleem2@gmail.com"
DEFAULT_REPO_NAME="context-forge"

# Argument processing
REPO_NAME="${1:-$DEFAULT_REPO_NAME}"
VISIBILITY_FLAG="--private"

if [[ "${2:-}" == "--public" ]]; then
    VISIBILITY_FLAG="--public"
fi

# Sanitize repository name to lower-kebab-case
SANITY_NAME=$(echo "$REPO_NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g' | sed -E 's/^-+|-+$//g')
if [[ -z "$SANITY_NAME" ]]; then
    SANITY_NAME="context-forge"
fi

echo "======================================================================"
echo " ContextForge GitHub Repository Setup"
echo " Target Owner: $TARGET_USER ($TARGET_EMAIL)"
echo " Target Repo:  $SANITY_NAME"
echo "======================================================================"

# 1. Local Git Configuration
echo "[1/4] Configuring local Git identity and settings..."
git config user.name "$TARGET_USER"
git config user.email "$TARGET_EMAIL"
git config pull.rebase true
git config push.autoSetupRemote true
git config core.autocrlf false
git config core.eol lf
git branch -M main

echo "  ✓ Local author: $(git config user.name) <$(git config user.email)>"
echo "  ✓ Default branch: main"
echo "  ✓ Settings: pull.rebase=true, core.autocrlf=false, core.eol=lf"

REMOTE_URL="https://github.com/$TARGET_USER/$SANITY_NAME.git"

# 2. GitHub CLI Check & Provisioning
echo -e "\n[2/4] Checking GitHub CLI (gh) authentication..."
if command -v gh &> /dev/null && gh auth status &> /dev/null; then
    echo "[3/4] GitHub CLI authenticated. Provisioning remote repository..."
    if gh repo view "$TARGET_USER/$SANITY_NAME" &> /dev/null; then
        echo "  ℹ Remote repository '$TARGET_USER/$SANITY_NAME' already exists."
    else
        echo "  Creating $VISIBILITY_FLAG remote repo '$TARGET_USER/$SANITY_NAME'..."
        gh repo create "$TARGET_USER/$SANITY_NAME" $VISIBILITY_FLAG --confirm
        echo "  ✓ Remote repository created successfully!"
    fi

    if git remote get-url origin &> /dev/null; then
        git remote set-url origin "$REMOTE_URL"
        echo "  ✓ Updated existing 'origin' remote to $REMOTE_URL"
    else
        git remote add origin "$REMOTE_URL"
        echo "  ✓ Added 'origin' remote pointing to $REMOTE_URL"
    fi
else
    echo "[3/4] GitHub CLI (gh) is not installed or not logged in."
    echo "======================================================================"
    echo " MANUAL FALLBACK INSTRUCTIONS:"
    echo " 1. Open browser: https://github.com/new"
    echo " 2. Set Repository Name: $SANITY_NAME"
    echo " 3. Select Private (or Public) and DO NOT initialize with README/gitignore."
    echo " 4. Click 'Create repository'."
    echo " 5. Run in terminal:"
    echo "    git remote add origin $REMOTE_URL"
    echo "======================================================================"

    if ! git remote get-url origin &> /dev/null; then
        git remote add origin "$REMOTE_URL"
        echo "  ✓ Added pre-configured 'origin' remote: $REMOTE_URL"
    fi
fi

echo -e "\n[4/4] Setup Complete:"
echo "  Repository Name: $SANITY_NAME"
echo "  Remote URL:      $REMOTE_URL"
echo "  Current Branch:  $(git branch --show-current)"

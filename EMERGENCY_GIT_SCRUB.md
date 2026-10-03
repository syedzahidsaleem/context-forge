# Emergency Git Incident Response & Secret Scrub Runbook
**Project:** ContextForge | **Security Level:** CISO Operational Protocol

> [!CAUTION]
> If an API key, GCP service account credential, or forbidden file is exposed, **treat it as an active security breach**. Follow the exact scenario protocol below.

---

## Quick Reference Summary

| Incident Stage | Primary Command | Effect |
|---|---|---|
| Staged locally (not committed) | `git reset HEAD <file>` | Unstages file without destroying changes |
| Committed locally (not pushed) | `git reset --soft HEAD~1` | Reverts commit, preserves work in working directory |
| Pushed to GitHub | `git filter-repo` + key revocation | Scrubs entire Git history and invalidates secret |

---

## Scenario 1: Secret or Forbidden File Staged (NOT Committed)

**Symptom:** You ran `git add .` or `git add .env` and realized sensitive data or temporary test scripts are staged.

### Remediation Protocol
1. **Unstage the specific file immediately:**
   ```bash
   git reset HEAD <path/to/sensitive-file>
   # Or using modern git:
   git restore --staged <path/to/sensitive-file>
   ```

2. **Verify staged index:**
   ```bash
   git status
   ```
   *Confirm the sensitive file is in the "Untracked" or "Changes not staged for commit" section.*

3. **Ensure `.gitignore` covers the pattern:**
   Verify `backend/.env`, `frontend/.env.local`, `*.pem`, `*.log`, etc., are listed in the workspace root `.gitignore`.

---

## Scenario 2: Secret Committed Locally (NOT Pushed to GitHub)

**Symptom:** You committed a sensitive file locally (`git commit -m "..."`), but you have **NOT** run `git push`.

### Remediation Protocol
1. **Soft reset the last commit:**
   ```bash
   git reset --soft HEAD~1
   ```
   *This removes the commit from history while leaving all your modified files intact in your working directory.*

2. **Unstage the sensitive file:**
   ```bash
   git reset HEAD <path/to/sensitive-file>
   ```

3. **Purge or sanitize the secret from the file.**

4. **Re-commit only clean files:**
   ```bash
   git add <clean-file>
   git commit -m "chore: sanitized commit"
   ```

---

## Scenario 3: Secret or Forbidden File Pushed to GitHub

**Symptom:** A commit containing an API key, service account JSON, or `.env` file was pushed to `origin/main` or any remote branch.

> [!CRITICAL]
> **STEP 0 — REVOCATION & ROTATION (MANDATORY)**  
> Once a secret touches GitHub's public/private servers, **it must be assumed compromised**.
> 1. **Gemini API Key:** Revoke immediately in [Google AI Studio](https://aistudio.google.com/). Generate a new key.
> 2. **GCP Service Account Key:** Go to GCP Console → IAM & Admin → Service Accounts → Keys → Delete exposed key. Create a new key.
> 3. **NewsAPI / Crunchbase Key:** Regenerate key in respective provider dashboard.
> 4. **GitHub PAT:** Revoke in GitHub → Settings → Developer Settings → Personal Access Tokens.

### History Scrubbing Protocol (`git-filter-repo`)

1. **Install `git-filter-repo` (Python tool recommended by Git core team):**
   ```bash
   pip install git-filter-repo
   ```

2. **Clone a fresh, isolated mirror of the repository:**
   ```bash
   cd ..
   git clone https://github.com/syedzahidsaleem/context-forge.git context-forge-scrub
   cd context-forge-scrub
   ```

3. **Scrub the forbidden file from ALL commits and branches:**
   ```bash
   # Remove a specific file path completely:
   git filter-repo --path backend/.env --invert-paths

   # Or remove any file matching a pattern:
   git filter-repo --path-match *.pem --invert-paths
   ```

4. **Re-add remote origin (filter-repo strips remotes for safety):**
   ```bash
   git remote add origin https://github.com/syedzahidsaleem/context-forge.git
   ```

5. **Force push scrubbed history to GitHub:**
   ```bash
   git push origin --force --all --tags
   ```

6. **Notify team members to re-clone:**
   Instruct all collaborators to run `git fetch origin` and `git reset --hard origin/main` (or fresh clone).

---

## Prevention & Safeguards Active in ContextForge

1. **Automated Pre-Commit Security Hook (`.githooks/pre-commit`):**
   Scans staged diffs for high-entropy keys (Gemini `AIza...`, OpenAI `sk-...`, Groq `gsk_...`, JWTs, DB URIs) and rejects commits before they occur.
2. **Master `.gitignore`:**
   Excludes all `.env*`, `*.pem`, `*service-account*.json`, and local scratchpads.
3. **Atomic Commit Engine (`scripts/atomic_commit.py`):**
   Stages files strictly one-by-one and checks author identity + secrets before committing.

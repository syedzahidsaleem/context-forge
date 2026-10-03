#!/usr/bin/env python3
"""
Pre-Commit Security & Repository Hygiene Scanner
ContextForge — CISO & Release Engineering
Checks staged files for secret leaks, blacklisted patterns, and large payloads.
"""
import sys
import re
import subprocess
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals if possible
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

BLACKLIST_PATTERNS = [
    r'^\.env.*',
    r'.*\.env$',
    r'.*\.pem$',
    r'.*\.key$',
    r'.*\.cert$',
    r'.*\.p12$',
    r'.*\.pfx$',
    r'.*service-account.*\.json$',
    r'.*credentials.*\.json$',
    r'.*gcp-key.*\.json$',
    r'.*\.sqlite3?$',
    r'.*\.log$',
    r'^scratch_.*',
    r'^test_local_.*',
    r'^temp_.*',
]

SECRET_REGEXES = [
    ("Groq API Key", re.compile(r'gsk_[a-zA-Z0-9]{30,}')),
    ("OpenAI API Key", re.compile(r'sk-[a-zA-Z0-9]{20,}')),
    ("Google / Gemini API Key", re.compile(r'AIza[0-9A-Za-z-_]{35}')),
    ("GitHub PAT (Classic)", re.compile(r'ghp_[a-zA-Z0-9]{36}')),
    ("GitHub PAT (Fine-Grained)", re.compile(r'github_pat_[a-zA-Z0-9_]{82}')),
    ("Generic JWT Token", re.compile(r'eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}')),
    ("PostgreSQL Connection URI", re.compile(r'postgresql://[a-zA-Z0-9_]+:[^@\s]+@[a-zA-Z0-9.-]+')),
    ("MySQL Connection URI", re.compile(r'mysql://[a-zA-Z0-9_]+:[^@\s]+@[a-zA-Z0-9.-]+')),
    ("MongoDB Connection URI", re.compile(r'mongodb\+srv://[a-zA-Z0-9_]+:[^@\s]+@[a-zA-Z0-9.-]+')),
]

def run_git_cmd(args: list[str]) -> str:
    res = subprocess.run(["git"] + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        return ""
    return (res.stdout or "").strip()

def main() -> int:
    staged_files_output = run_git_cmd(["diff", "--cached", "--name-only"])
    if not staged_files_output:
        return 0

    staged_files = [f.strip() for f in staged_files_output.splitlines() if f.strip()]
    errors = []

    print("[PRE-COMMIT SECURITY GATE] Scanning staged files...")

    for file_path_str in staged_files:
        file_path = Path(file_path_str)
        filename = file_path.name

        # 1. Blacklist Interceptor
        for pattern in BLACKLIST_PATTERNS:
            if re.match(pattern, filename, re.IGNORECASE) or re.match(pattern, file_path_str, re.IGNORECASE):
                errors.append(
                    f"[FAIL] BLACKLISTED FILE STAGED: '{file_path_str}' matches forbidden pattern '{pattern}'.\n"
                    f"       UNSTAGE IMMEDIATELY: git reset HEAD \"{file_path_str}\""
                )

        if not file_path.exists():
            continue  # file might be deleted in staged diff

        # 2. Payload Size Sentry
        try:
            file_size = file_path.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                errors.append(
                    f"[FAIL] LARGE PAYLOAD DETECTED: '{file_path_str}' is {file_size / (1024*1024):.2f} MB (Max allowed: 5.00 MB).\n"
                    f"       UNSTAGE IMMEDIATELY: git reset HEAD \"{file_path_str}\""
                )
        except OSError:
            pass

        # 3. High-Entropy Secret Scanner
        try:
            diff_text = run_git_cmd(["diff", "--cached", "-U0", "--", file_path_str])
            if diff_text:
                added_lines = [line[1:] for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++")]
                for line in added_lines:
                    for secret_type, regex in SECRET_REGEXES:
                        if regex.search(line):
                            errors.append(
                                f"[FAIL] HIGH-ENTROPY SECRET LEAK DETECTED in '{file_path_str}':\n"
                                f"       Detected: {secret_type}\n"
                                f"       UNSTAGE & PURGE SECRET: git reset HEAD \"{file_path_str}\""
                            )
        except Exception as ex:
            print(f"[WARN] Could not check diff for {file_path_str}: {ex}")

    if errors:
        print("\n" + "="*70)
        print(" PRE-COMMIT HYGIENE GATE FAILED — COMMIT REJECTED")
        print("="*70)
        for err in errors:
            print(err)
            print("-" * 70)
        return 1

    print("[PASS] PRE-COMMIT SECURITY GATE: All staged files cleared.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

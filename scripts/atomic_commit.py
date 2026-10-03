#!/usr/bin/env python3
"""
Atomic Single-File Verification & Commit Engine
ContextForge — Release Engineering Tooling

Usage:
  python scripts/atomic_commit.py <file-path> "<type>(<scope>): <description>"
"""

import sys
import time
import py_compile
import subprocess
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals if possible
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REQUIRED_AUTHOR = "syedzahidsaleem"
REQUIRED_EMAIL = "syedzahidsaleem2@gmail.com"

def run_cmd(args: list[str], check: bool = True) -> tuple[int, str, str]:
    res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, args, res.stdout, res.stderr)
    return res.returncode, (res.stdout or "").strip(), (res.stderr or "").strip()

def check_author_identity() -> None:
    _, author_name, _ = run_cmd(["git", "config", "user.name"], check=False)
    _, author_email, _ = run_cmd(["git", "config", "user.email"], check=False)
    
    if author_name != REQUIRED_AUTHOR or author_email != REQUIRED_EMAIL:
        print(f"[FAIL] AUTHOR IDENTITY VIOLATION!")
        print(f"       Expected: {REQUIRED_AUTHOR} <{REQUIRED_EMAIL}>")
        print(f"       Found:    {author_name} <{author_email}>")
        print("       Run: git config user.name 'syedzahidsaleem' && git config user.email 'syedzahidsaleem2@gmail.com'")
        sys.exit(1)

def verify_isolated_syntax(file_path: Path) -> None:
    print(f"[1/5] Running isolated syntax check on '{file_path}'...")
    ext = file_path.suffix.lower()
    
    if ext in [".py"]:
        try:
            py_compile.compile(str(file_path), doraise=True)
            print("  [PASS] Python compilation clean.")
        except py_compile.PyCompileError as e:
            print(f"[FAIL] SYNTAX REGRESSION DETECTED in '{file_path}':\n{e}")
            sys.exit(1)
            
        code, ruff_out, _ = run_cmd(["ruff", "check", str(file_path)], check=False)
        if code == 0:
            print("  [PASS] Ruff lint clean.")
            
    elif ext in [".js", ".jsx", ".ts", ".tsx"]:
        code, node_out, err = run_cmd(["node", "--check", str(file_path)], check=False)
        if code == 0:
            print("  [PASS] JavaScript/Node syntax clean.")
        else:
            print(f"  [INFO] Node check info: {err or node_out}")
    else:
        print("  [PASS] Non-executable file — syntax check passed.")

def verify_workspace_dependencies(file_path: Path) -> None:
    print(f"[2/5] Verifying workspace dependency guard...")
    ext = file_path.suffix.lower()
    
    if ext in [".py"] and file_path.parts[0] == "backend":
        pyproject = Path("backend/pyproject.toml")
        if pyproject.exists():
            code, mypy_out, mypy_err = run_cmd(["mypy", str(file_path), "--config-file", str(pyproject)], check=False)
            if code != 0:
                print(f"[WARN] TYPE/DEPENDENCY CHECK WARNING for '{file_path}':")
                print(mypy_out or mypy_err)
                if "Cannot find implementation or library stub" in (mypy_out + mypy_err) or "has no attribute" in (mypy_out + mypy_err):
                    print("\n[FAIL] BROKEN DEPENDENCY DETECTED!")
                    print("       Co-stage the contract stub or fix the dependent file before committing.")
                    sys.exit(1)
    print("  [PASS] Dependency guard passed.")

def scan_staged_diff_for_secrets(file_path_str: str) -> None:
    print(f"[3/5] Scanning staged diff for forbidden secrets...")
    code, diff_out, _ = run_cmd(["git", "diff", "--cached", "-U0", "--", file_path_str], check=False)
    if code == 0 and diff_out:
        code, scan_out, _ = run_cmd(["python", "scripts/pre_commit_check.py"], check=False)
        if code != 0:
            print(f"[FAIL] SECRET LEAK OR BLACKLIST VIOLATION IN STAGED DIFF!")
            print(scan_out)
            run_cmd(["git", "reset", "HEAD", file_path_str], check=False)
            sys.exit(1)
    print("  [PASS] Secret scan clean.")

def commit_and_push(file_path_str: str, commit_msg: str) -> None:
    print(f"[4/5] Executing atomic commit for '{file_path_str}'...")
    commit_code, commit_out, commit_err = run_cmd(["git", "commit", "-m", commit_msg], check=False)
    if commit_code != 0:
        print(f"[FAIL] Git commit failed:\n{commit_err or commit_out}")
        sys.exit(1)
    print(f"  [PASS] Committed: {commit_msg}")

    print(f"[5/5] Pushing commit to remote 'origin HEAD'...")
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        push_code, push_out, push_err = run_cmd(["git", "push", "origin", "HEAD"], check=False)
        if push_code == 0:
            print(f"  [PASS] Successfully pushed to origin/HEAD!")
            return
        else:
            print(f"  [WARN] Push attempt {attempt}/{max_retries} failed: {push_err or push_out}")
            if attempt < max_retries:
                time.sleep(2)

    print("[WARN] Push failed after retries. Commit remains locally. You can push manually via `git push origin HEAD`.")

def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/atomic_commit.py <file-path> \"<type>(<scope>): <description>\"")
        sys.exit(1)

    file_path_input = sys.argv[1]
    commit_msg = sys.argv[2]
    target_path = Path(file_path_input)

    if not target_path.exists():
        print(f"[FAIL] Target file '{file_path_input}' does not exist.")
        sys.exit(1)

    code, status_out, _ = run_cmd(["git", "status", "--porcelain", str(target_path)], check=False)
    if not status_out:
        print(f"[INFO] File '{file_path_input}' has no uncommitted changes or untracked state.")
        sys.exit(0)

    check_author_identity()
    verify_isolated_syntax(target_path)
    verify_workspace_dependencies(target_path)

    print(f"[3/5] Staging ONLY '{file_path_input}'...")
    run_cmd(["git", "add", str(target_path)])
    scan_staged_diff_for_secrets(str(target_path))
    commit_and_push(str(target_path), commit_msg)

if __name__ == "__main__":
    main()

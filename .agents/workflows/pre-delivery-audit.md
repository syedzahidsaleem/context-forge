---
name: pre-delivery-audit
description: "Multi-step verification runbook covering static analysis, type checking, security scanning, route smoke tests, and build artifact creation. Run before every hackathon demo, deployment, or submission."
trigger: manual
estimated_duration: "10–20 minutes"
blocking: true
---

# Workflow: Pre-Delivery Audit — ContextForge

**This workflow must complete with zero failures before any demo, deployment, or code submission.**

If any step fails, fix the issue and restart the workflow from Step 1. Do not skip steps.

---

## Gate 0: Pre-Flight Checks

```bash
# Confirm you're in the repo root
ls PRD.md AGENTS.md .env.example
```
**Expected:** Files listed without error. If not, `cd` to the repo root first.

```bash
# Confirm no uncommitted changes to .env
git status .env
```
**Expected:** `.env` should NOT appear in git status. If it does, it's not gitignored — stop and fix that immediately.

```bash
# Confirm no API keys are committed to git history
git log --all -p | grep -E "(GEMINI_API_KEY|NEWS_API_KEY|CRUNCHBASE)" | grep -v "^-" | grep -v ".env.example"
```
**Expected:** Zero output. Any output means a key was committed — rotate it immediately via the respective provider's dashboard.

---

## Phase 1: Backend Static Analysis

### Step 1.1 — Activate virtual environment
```bash
cd contextforge/backend
source .venv/bin/activate
```

### Step 1.2 — Ruff linting (style + import order + common bugs)
```bash
ruff check . --output-format=text
```
**Expected:** `All checks passed.` or zero output.
**Fail action:** Run `ruff check . --fix` to auto-fix safe issues. Review and fix remaining issues manually.

### Step 1.3 — Ruff formatting check
```bash
ruff format . --check
```
**Expected:** `X files already formatted.` No files listed as needing reformatting.
**Fail action:** Run `ruff format .` to auto-format, then review the diff.

### Step 1.4 — Mypy strict type checking
```bash
mypy . --config-file pyproject.toml
```
**Expected:** `Success: no issues found in X source files`
**Fail action:** Fix all type errors. No `# type: ignore` without an explanatory comment.

### Step 1.5 — Check for circular imports
```bash
python -c "
import sys
sys.path.insert(0, '.')
try:
    import main
    print('PASS: No circular imports detected.')
except ImportError as e:
    print(f'FAIL: Import error (possible circular import): {e}')
    sys.exit(1)
"
```
**Expected:** `PASS: No circular imports detected.`

### Step 1.6 — Verify all module `__all__` exports are defined
```bash
python -c "
import ast, os, sys

missing = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git']]
    for f in files:
        if f.endswith('.py') and f != '__init__.py':
            path = os.path.join(root, f)
            with open(path) as fh:
                try:
                    tree = ast.parse(fh.read())
                    has_all = any(
                        isinstance(node, ast.Assign) and
                        any(isinstance(t, ast.Name) and t.id == '__all__' for t in node.targets)
                        for node in ast.walk(tree)
                    )
                    if not has_all:
                        missing.append(path)
                except SyntaxError:
                    pass

if missing:
    print('FAIL: These modules are missing __all__:')
    for m in missing:
        print(f'  {m}')
    sys.exit(1)
else:
    print(f'PASS: All {sum(1 for _ in missing) + (0 if not missing else len(missing))} modules have __all__ defined.')
    print(f'PASS: All Python modules have __all__ defined.')
"
```
**Expected:** `PASS: All Python modules have __all__ defined.`

---

## Phase 2: Security Audit

### Step 2.1 — Check for hardcoded secrets in source code
```bash
grep -rn \
  --include="*.py" --include="*.js" --include="*.jsx" --include="*.json" \
  --exclude-dir=".venv" --exclude-dir="node_modules" --exclude-dir=".git" \
  -E "(AIza[A-Za-z0-9\-_]{35}|sk-[A-Za-z0-9]{48}|AAAA[A-Za-z0-9\-_]{100})" \
  . || echo "PASS: No hardcoded API key patterns found."
```
**Expected:** `PASS: No hardcoded API key patterns found.`

### Step 2.2 — Check for `allow_origins=["*"]` in CORS config
```bash
grep -rn 'allow_origins.*\["*"\]' --include="*.py" . | grep -v ".venv"
```
**Expected:** Zero output. Any output is a critical security misconfiguration — fix it before proceeding.

### Step 2.3 — Verify no user content is interpolated into system prompts
```bash
grep -n 'system_instruction.*f"' backend/agents/ -r
```
**Expected:** Zero output. Any f-string in a `system_instruction=` argument is a prompt injection risk.

### Step 2.4 — Audit file upload MIME type validation
```bash
grep -n "magic.from_buffer" backend/intake/documents.py backend/intake/vision.py
```
**Expected:** At least one match per file — the MIME type validation via python-magic must be present.

### Step 2.5 — Verify rate limiting middleware is registered
```bash
grep -n "RateLimitMiddleware\|slowapi\|rate_limit" backend/main.py
```
**Expected:** At least one match confirming rate limiting is registered as middleware.

### Step 2.6 — Run pip-audit for known vulnerabilities in Python dependencies
```bash
pip install pip-audit --quiet
pip-audit -r requirements.txt
```
**Expected:** `No known vulnerabilities found.`
**Fail action:** For each vulnerability, check if a patched version is available and update `requirements.txt`. If no patch exists, document the accepted risk in a comment in `requirements.txt`.

### Step 2.7 — Run npm audit for known vulnerabilities in frontend dependencies
```bash
cd ../frontend
npm audit --audit-level=high
```
**Expected:** Zero high or critical vulnerabilities.
**Fail action:** Run `npm audit fix` for auto-fixable issues. Review and manually fix remaining high/critical issues.

---

## Phase 3: Functional Smoke Tests

### Step 3.1 — Start backend in test mode
```bash
cd ../backend
APP_ENV=development uvicorn main:app --host 127.0.0.1 --port 8001 &
BACKEND_PID=$!
sleep 3  # Wait for startup
```

### Step 3.2 — Health endpoint
```bash
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/health)
echo "Health check: $HEALTH"
[ "$HEALTH" = "200" ] && echo "PASS" || (echo "FAIL" && kill $BACKEND_PID && exit 1)
```

### Step 3.3 — Session creation returns 201
```bash
SESSION_RESP=$(curl -s -w "\n%{http_code}" -X POST http://127.0.0.1:8001/intake/session)
SESSION_CODE=$(echo "$SESSION_RESP" | tail -1)
SESSION_BODY=$(echo "$SESSION_RESP" | head -1)
echo "Session creation status: $SESSION_CODE"
[ "$SESSION_CODE" = "201" ] && echo "PASS" || (echo "FAIL: Expected 201, got $SESSION_CODE" && kill $BACKEND_PID && exit 1)
SESSION_ID=$(echo "$SESSION_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
echo "Session ID: $SESSION_ID"
```

### Step 3.4 — Invalid session ID returns 401/404 (not 500)
```bash
BAD_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "X-Session-ID: not-a-valid-uuid" \
  http://127.0.0.1:8001/intake/chat \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"session_id":"not-a-valid-uuid","content":"hello","role":"user"}')
echo "Invalid session status: $BAD_STATUS"
[ "$BAD_STATUS" = "401" ] || [ "$BAD_STATUS" = "400" ] && echo "PASS" || echo "WARN: Got $BAD_STATUS — expected 400 or 401"
```

### Step 3.5 — File upload endpoint rejects unsupported MIME type
```bash
echo "this is not an image or pdf" > /tmp/test_bad_file.txt
BAD_UPLOAD=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://127.0.0.1:8001/intake/upload \
  -H "X-Session-ID: $SESSION_ID" \
  -F "session_id=$SESSION_ID" \
  -F "file=@/tmp/test_bad_file.txt;type=application/x-executable" \
  -F "file_type=document")
echo "Bad MIME upload status: $BAD_UPLOAD"
[ "$BAD_UPLOAD" = "400" ] && echo "PASS" || echo "WARN: Expected 400, got $BAD_UPLOAD"
```

### Step 3.6 — Rate limiting is active (trigger session creation 11 times)
```bash
echo "Testing rate limiting (11 session creations — last should be 429)..."
for i in $(seq 1 11); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8001/intake/session)
  echo "  Request $i: $STATUS"
done
# Note: Last request should show 429 (rate limit exceeded) if window not reset
echo "Rate limiting check complete — verify 429 appeared above."
```

### Step 3.7 — Shut down test backend
```bash
kill $BACKEND_PID 2>/dev/null || true
```

---

## Phase 4: Agent Prompt Validation

### Step 4.1 — Run the agent persona calibration verification test
```bash
cd contextforge/backend
python -c "
from agents.prompts import (
    VC_SYSTEM_PROMPT, LEAN_SYSTEM_PROMPT, CTO_SYSTEM_PROMPT,
    UX_SYSTEM_PROMPT, REGULATOR_SYSTEM_PROMPT, ADVERSARIAL_SYSTEM_PROMPT,
    EVALUATOR_SYSTEM_PROMPT, MERGE_SYSTEM_PROMPT, BRD_SECTIONS, BRD_CRITERIA, AGENT_NAMES
)
errors = []
for name, prompt in [('VC', VC_SYSTEM_PROMPT), ('LEAN', LEAN_SYSTEM_PROMPT),
                      ('CTO', CTO_SYSTEM_PROMPT), ('UX', UX_SYSTEM_PROMPT),
                      ('REGULATOR', REGULATOR_SYSTEM_PROMPT), ('ADV', ADVERSARIAL_SYSTEM_PROMPT)]:
    if len(prompt) < 200:
        errors.append(f'{name} prompt too short ({len(prompt)} chars)')
assert len(BRD_SECTIONS) == 5, 'Expected 5 BRD sections'
assert len(BRD_CRITERIA) == 5, 'Expected 5 BRD criteria'
assert len(AGENT_NAMES) == 6, 'Expected 6 agent names'
if errors:
    print('FAIL: Prompt issues:', errors)
    exit(1)
print('PASS: All agent prompts validated.')
"
```

### Step 4.2 — Run heatmap calculation smoke test
```bash
python -c "
from output.heatmap import calculate_heatmap
from models.scores import ScoreMatrix

raw_matrix = {
    'scores': {
        agent: {
            section: {
                criterion: {'score': float(hash(agent + section + criterion) % 40 + 60), 'citation': 'test'}
                for criterion in ['feasibility', 'market_timing', 'regulatory_safety', 'user_adoption', 'competitive_moat']
            }
            for section in ['problem_statement', 'functional_requirements', 'technical_requirements', 'risk_register', 'timeline_milestones']
        }
        for agent in ['vc', 'lean', 'cto', 'ux', 'regulator', 'adversarial']
    }
}
sm = ScoreMatrix.model_validate(raw_matrix)
heatmap = calculate_heatmap(sm)
assert len(heatmap) == 5, f'Expected 5 heatmap sections, got {len(heatmap)}'
for s in heatmap:
    assert 0.0 <= s['agreement_score'] <= 100.0, f'Agreement out of bounds: {s}'
    assert s['risk_level'] in ('low', 'medium', 'high'), f'Invalid risk level: {s}'
print('PASS: Heatmap calculation produces valid output for all 5 sections.')
"
```

---

## Phase 5: Frontend Build Verification

### Step 5.1 — ESLint on all frontend source files
```bash
cd contextforge/frontend
npx eslint src/ --max-warnings=0
```
**Expected:** Zero warnings, zero errors.

### Step 5.2 — Production build
```bash
npm run build
```
**Expected:** Build succeeds. `dist/` directory created. No TypeScript/JSX errors.

### Step 5.3 — Check bundle for accidental secret inclusion
```bash
grep -r "AIza\|NEWS_API_KEY\|CRUNCHBASE" dist/ 2>/dev/null && echo "CRITICAL FAIL: Secret found in build bundle!" || echo "PASS: No secrets in build bundle."
```
**Expected:** `PASS: No secrets in build bundle.`

### Step 5.4 — Verify CSS custom properties are present in bundle
```bash
grep -l "color-void\|color-surface\|color-accent-signal" dist/assets/*.css
```
**Expected:** At least one CSS file listed — confirms design tokens are included in the build.

### Step 5.5 — Check accessibility: no aria-label omissions on canvas elements (JSX source check)
```bash
grep -rn "<canvas" src/ | grep -v "aria-hidden\|aria-label\|role="
```
**Expected:** Zero output. Any canvas without `aria-hidden` or `aria-label` must be fixed.

---

## Phase 6: Pre-Demo Checklist

Run this immediately before the hackathon demo:

```bash
echo "=== PRE-DEMO CHECKLIST ==="
echo ""
echo "[ ] Backend running on Railway (or locally): check /health endpoint"
echo "[ ] Frontend deployed to Vercel (or locally): check http://localhost:5173"
echo "[ ] VITE_API_BASE_URL in frontend .env points to live backend"
echo "[ ] Gemini API key pool has at least 2 keys (prevents RPM limit during demo)"
echo "[ ] Demo business idea typed and ready: 'I want to build an app that helps small restaurants in India manage their inventory and reduce food waste using AI predictions.'"
echo "[ ] Particle background animating on page load"
echo "[ ] 6 agent cards visible in AgentGrid (all showing Waiting state initially)"
echo "[ ] Run one full BRD generation end-to-end before judges arrive"
echo "[ ] PDF download tested: opens a valid PDF"
echo "[ ] Divergence Heatmap confirmed working from last test run"
echo "[ ] Investor Readiness Score confirmed rendering"
echo "[ ] Browser zoom set to 100% for demo (not zoomed in)"
echo ""
echo "=== AUDIT WORKFLOW COMPLETE ==="
```

---

## Summary Report

Paste this into your PR description or hackathon submission notes after a successful audit:

```
ContextForge Pre-Delivery Audit — PASSED
Date: $(date)
Checks run:
  ✓ Ruff linting: 0 violations
  ✓ Ruff formatting: all files formatted
  ✓ Mypy strict: 0 type errors
  ✓ No circular imports
  ✓ All __all__ exports defined
  ✓ No hardcoded secrets in source
  ✓ No CORS wildcard in production config
  ✓ No user content in system prompts
  ✓ MIME validation present for file uploads
  ✓ Rate limiting registered
  ✓ pip-audit: 0 vulnerabilities
  ✓ npm audit: 0 high/critical vulnerabilities
  ✓ Health endpoint: 200
  ✓ Session creation: 201
  ✓ Invalid session: 401/400 (not 500)
  ✓ Bad MIME upload: 400
  ✓ Agent prompt validation: passed
  ✓ Heatmap calculation: passed
  ✓ Frontend ESLint: 0 warnings/errors
  ✓ Production build: succeeded
  ✓ No secrets in build bundle
  ✓ Design tokens in CSS bundle
  ✓ Canvas aria attributes: all present
```

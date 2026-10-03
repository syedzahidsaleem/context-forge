---
name: setup-and-migrate
description: "Sequential CLI runbook to install dependencies, validate environment, create GCP resources, and verify the full ContextForge stack is ready for development or demo."
trigger: manual
estimated_duration: "15–25 minutes on first run, 3–5 minutes on subsequent runs"
---

# Workflow: Setup & Migrate — ContextForge

Execute every step in order. Do not skip steps. Each step includes a sanity check — if the check fails, fix the issue before proceeding.

---

## Prerequisites (verify before starting)

- [ ] Python 3.12.x installed (`python3 --version`)
- [ ] Node.js 20.x LTS installed (`node --version`)
- [ ] npm installed (`npm --version`)
- [ ] Google Cloud SDK (`gcloud`) installed and authenticated (`gcloud auth list`)
- [ ] A GCP project created with billing enabled
- [ ] At least one Gemini API key obtained from Google AI Studio (https://aistudio.google.com/app/apikey)
- [ ] A NewsAPI key obtained from https://newsapi.org/register (free tier)
- [ ] Git repository cloned locally (`git clone ...`)

---

## Phase 1: Environment Configuration

### Step 1.1 — Copy and fill the environment file
```bash
cd contextforge
cp .env.example .env
```

Open `.env` in your editor and fill in **all `[REQUIRED]` values**:
- `GEMINI_API_KEY_1` — your primary Gemini API key
- `GCP_PROJECT_ID` — your GCP project ID (from GCP Console header)
- `GCS_BUCKET_NAME` — choose a unique name, e.g., `contextforge-outputs-{your-initials}`
- `BIGQUERY_DATASET` — keep default `contextforge_data` unless you have a naming conflict
- `NEWS_API_KEY` — your NewsAPI key

Leave optional keys blank for now if you don't have them (CRUNCHBASE, GOOGLE_DOCS, second Gemini key).

**Sanity check:**
```bash
grep -E "^(GEMINI_API_KEY_1|GCP_PROJECT_ID|GCS_BUCKET_NAME|NEWS_API_KEY)=" .env | grep -v "=$"
```
**Expected:** 4 lines, each showing a variable with a non-empty value. If any line shows `VARIABLE=` with nothing after the `=`, go back and fill it in.

---

### Step 1.2 — Verify the `.env` file is gitignored
```bash
git check-ignore -v .env
```
**Expected output:** `.gitignore:.env`. If `.env` is NOT gitignored, stop immediately, add `.env` to `.gitignore`, and commit the `.gitignore` change before proceeding.

---

## Phase 2: Backend Setup

### Step 2.1 — Create Python virtual environment
```bash
cd contextforge/backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

**Sanity check:**
```bash
which python
```
**Expected:** Path ending in `contextforge/backend/.venv/bin/python`. If it shows the system Python, the virtual environment is not activated.

---

### Step 2.2 — Install Python dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Sanity check:**
```bash
python -c "import fastapi, google.generativeai, google.cloud.storage, google.cloud.bigquery, reportlab, pypdf2, docx, httpx; print('All backend dependencies installed.')"
```
**Expected:** `All backend dependencies installed.`

If any import fails, identify the failing package and check `requirements.txt` for the correct pinned version.

---

### Step 2.3 — Run mypy type check on backend
```bash
cd contextforge/backend
mypy . --config-file pyproject.toml
```
**Expected:** `Success: no issues found in X source files`

If mypy reports errors, fix them before proceeding. Do not add `# type: ignore` without a comment.

---

### Step 2.4 — Run ruff linter
```bash
ruff check .
```
**Expected:** No output (zero violations). If there are violations, run `ruff check . --fix` to auto-fix, then review what was changed.

---

### Step 2.5 — Validate environment variables are loaded correctly
```bash
python -c "
from config import settings
print(f'App env: {settings.APP_ENV}')
print(f'Gemini Flash model: {settings.GEMINI_FLASH_MODEL}')
print(f'GCS bucket: {settings.GCS_BUCKET_NAME}')
print(f'Key pool size: {len([k for k in [settings.GEMINI_API_KEY_1, getattr(settings, \"GEMINI_API_KEY_2\", None)] if k])}')
print('ENV VALIDATION PASSED')
"
```
**Expected:** Variables printed with correct values, ending with `ENV VALIDATION PASSED`.

---

## Phase 3: GCP Resource Provisioning

### Step 3.1 — Authenticate GCP SDK to your project
```bash
gcloud auth application-default login
gcloud config set project $GCP_PROJECT_ID
```
Replace `$GCP_PROJECT_ID` with your actual project ID, or source the .env first:
```bash
export $(grep -v '^#' ../.env | xargs)
gcloud config set project $GCP_PROJECT_ID
```

**Sanity check:**
```bash
gcloud config get-value project
```
**Expected:** Your GCP project ID.

---

### Step 3.2 — Enable required GCP APIs
```bash
gcloud services enable \
  storage.googleapis.com \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  generativelanguage.googleapis.com \
  --project=$GCP_PROJECT_ID
```

**Sanity check:**
```bash
gcloud services list --enabled --project=$GCP_PROJECT_ID | grep -E "storage|bigquery|aiplatform"
```
**Expected:** At least 3 lines showing `ENABLED` for Cloud Storage, BigQuery, and Vertex AI.

---

### Step 3.3 — Create the GCS bucket
```bash
export $(grep -v '^#' ../.env | xargs)
gsutil mb -p $GCP_PROJECT_ID -l US-CENTRAL1 gs://$GCS_BUCKET_NAME
```

Enable Uniform Bucket-Level Access (required by security rule DB-014):
```bash
gsutil uniformbucketlevelaccess set on gs://$GCS_BUCKET_NAME
```

**Sanity check:**
```bash
gsutil ls gs://$GCS_BUCKET_NAME
```
**Expected:** Empty output (no files yet) without any error. An `AccessDeniedException` means the service account doesn't have Storage Admin role.

---

### Step 3.4 — Create BigQuery dataset and tables
```bash
export $(grep -v '^#' ../.env | xargs)
bq mk --dataset --location=US $GCP_PROJECT_ID:$BIGQUERY_DATASET
```

Create the `brd_runs` table:
```bash
bq mk --table \
  --time_partitioning_field created_at \
  --time_partitioning_type DAY \
  --clustering_fields region,industry,status \
  $GCP_PROJECT_ID:$BIGQUERY_DATASET.brd_runs \
  session_id:STRING,created_at:TIMESTAMP,completed_at:TIMESTAMP,user_anonymous_id:STRING,intake_summary:STRING,region:STRING,industry:STRING,stage:STRING,status:STRING,error_message:STRING,gcs_session_prefix:STRING,investor_readiness_score:FLOAT64,schema_version:INT64
```

Create the `context_harvest_logs` table:
```bash
bq mk --table \
  --time_partitioning_field harvested_at \
  --time_partitioning_type DAY \
  --clustering_fields source,region \
  $GCP_PROJECT_ID:$BIGQUERY_DATASET.context_harvest_logs \
  harvest_id:STRING,session_id:STRING,harvested_at:TIMESTAMP,source:STRING,region:STRING,industry:STRING,request_url:STRING,response_status_code:INT64,response_item_count:INT64,latency_ms:INT64,cached:BOOL,error_detail:STRING
```

Create the `evaluator_scores` table:
```bash
bq mk --table \
  --time_partitioning_field evaluated_at \
  --time_partitioning_type DAY \
  --clustering_fields session_id,agent_name \
  $GCP_PROJECT_ID:$BIGQUERY_DATASET.evaluator_scores \
  score_id:STRING,session_id:STRING,agent_name:STRING,section_name:STRING,criterion:STRING,score:FLOAT64,citation:STRING,evaluated_at:TIMESTAMP
```

Create the `divergence_heatmap_data` table:
```bash
bq mk --table \
  $GCP_PROJECT_ID:$BIGQUERY_DATASET.divergence_heatmap_data \
  heatmap_id:STRING,session_id:STRING,section_name:STRING,agreement_score:FLOAT64,std_deviation:FLOAT64,risk_level:STRING,min_score:FLOAT64,max_score:FLOAT64,dominant_agent:STRING,calculated_at:TIMESTAMP
```

**Sanity check:**
```bash
bq ls $GCP_PROJECT_ID:$BIGQUERY_DATASET
```
**Expected:** 4 tables listed: `brd_runs`, `context_harvest_logs`, `evaluator_scores`, `divergence_heatmap_data`.

---

### Step 3.5 — Create and configure GCP Service Account
```bash
gcloud iam service-accounts create contextforge-backend \
  --display-name="ContextForge Backend" \
  --project=$GCP_PROJECT_ID

# Grant required roles
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:contextforge-backend@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:contextforge-backend@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:contextforge-backend@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Generate key and base64-encode it for .env
gcloud iam service-accounts keys create /tmp/contextforge-sa-key.json \
  --iam-account=contextforge-backend@$GCP_PROJECT_ID.iam.gserviceaccount.com

GCP_SA_B64=$(base64 -w 0 /tmp/contextforge-sa-key.json)
echo "GCP_SERVICE_ACCOUNT_JSON_B64=$GCP_SA_B64" >> ../.env
rm /tmp/contextforge-sa-key.json  # Delete the file — the value is now in .env
```

**Sanity check:**
```bash
python -c "
import base64, json, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv('../.env')
b64 = os.environ.get('GCP_SERVICE_ACCOUNT_JSON_B64', '')
if not b64:
    print('FAIL: GCP_SERVICE_ACCOUNT_JSON_B64 not set')
else:
    decoded = json.loads(base64.b64decode(b64))
    print(f'Service account: {decoded[\"client_email\"]}')
    print('PASS: Service account JSON decoded successfully.')
"
```

---

## Phase 4: Frontend Setup

### Step 4.1 — Install frontend dependencies
```bash
cd contextforge/frontend
npm ci
```

**Sanity check:**
```bash
ls node_modules | wc -l
```
**Expected:** A number > 100 (many dependencies installed). If `node_modules` is empty, `npm ci` failed — check for errors above.

---

### Step 4.2 — Run ESLint on frontend
```bash
npx eslint src/
```
**Expected:** No output (zero violations).

---

### Step 4.3 — Verify frontend build compiles
```bash
npm run build
```
**Expected:** Build completes without errors. A `dist/` directory is created.

---

## Phase 5: Integration Smoke Tests

### Step 5.1 — Start the backend server
```bash
cd contextforge/backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```
Leave this running. Open a new terminal for the next steps.

### Step 5.2 — Health check
```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```
**Expected:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "dependencies": {
    "gemini_api": "ok",
    "gcs": "ok",
    "bigquery": "ok"
  }
}
```
If `gemini_api` shows `degraded` or `down`, verify `GEMINI_API_KEY_1` is set and valid.

### Step 5.3 — Session creation smoke test
```bash
SESSION_RESPONSE=$(curl -s -X POST http://localhost:8000/intake/session)
echo $SESSION_RESPONSE | python3 -m json.tool
SESSION_ID=$(echo $SESSION_RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
echo "Session ID: $SESSION_ID"
```
**Expected:** A JSON object with a valid UUID v4 `session_id`.

### Step 5.4 — Start the frontend dev server (in another terminal)
```bash
cd contextforge/frontend
npm run dev
```
**Expected:** Output showing `Local: http://localhost:5173`

Open http://localhost:5173 in a browser. The particle background canvas should be animating. The ChatBox should be visible.

---

## Phase 6: Seed Data (Optional — for testing without live Gemini calls)

### Step 6.1 — Write a test agent output blob to GCS
```bash
python -c "
import json, uuid
from google.cloud import storage
import os; os.chdir('backend')
from dotenv import load_dotenv; load_dotenv('../.env')
from config import settings

client = storage.Client()
bucket = client.bucket(settings.GCS_BUCKET_NAME)
test_session_id = 'test-' + str(uuid.uuid4())[:8]
test_brd = {
  'agent': 'vc',
  'brd': {
    'problem_statement': 'Test problem statement from VC agent.',
    'functional_requirements': 'Test functional requirements.',
    'technical_requirements': 'Test technical requirements.',
    'risk_register': 'Test risk register.',
    'timeline_milestones': 'Test timeline and milestones.'
  }
}
blob = bucket.blob(f'{test_session_id}/agent_vc.json')
blob.upload_from_string(json.dumps(test_brd), content_type='application/json')
print(f'PASS: Test blob written to gs://{settings.GCS_BUCKET_NAME}/{test_session_id}/agent_vc.json')
print(f'Test session ID (save for cleanup): {test_session_id}')
"
```
**Expected:** `PASS: Test blob written to gs://...`

---

## Setup Complete ✓

All phases passed. The ContextForge stack is ready for development.

**Summary of what is now running:**
- Backend: `http://localhost:8000` (FastAPI + uvicorn --reload)
- Frontend: `http://localhost:5173` (Vite dev server)
- GCS bucket: provisioned and accessible
- BigQuery tables: created with correct schemas and partitioning
- GCP Service Account: configured with minimum required roles

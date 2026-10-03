---
trigger: "glob:backend/gcp/**/*,backend/agents/**/*,backend/context/**/*,backend/output/**/*"
description: "GCS blob management, BigQuery query design, and GCP data integrity rules for ContextForge"
priority: 2
applies_to: ["backend/gcp/**/*.py", "backend/agents/**/*.py", "backend/context/**/*.py"]
---

# Database & GCP Data Rules — ContextForge

ContextForge uses Cloud Storage (GCS) as its primary blob store and BigQuery as its analytics/log store. There is no traditional SQL database. These rules govern all interactions with both.

---

## GCS Blob Rules

### Rule DB-001: All GCS blob paths are derived from session_id only
No GCS blob path may be constructed from user-provided input other than the `session_id` (which is a UUID v4 generated server-side). User-submitted filenames, ideas, or any other user content must never appear in a GCS path.

```python
# CORRECT: path derived from server-generated UUID only
blob_name = f"{session_id}/{agent_name}.json"

# FORBIDDEN: user-provided filename in path (path traversal risk)
blob_name = f"{session_id}/{user_uploaded_filename}"  # NEVER
```

### Rule DB-002: All GCS writes must be confirmed before the session status advances
After writing an agent output blob to GCS, verify the write succeeded (check `blob.exists()` or catch the exception) before marking that agent's status as `complete` in the session state. A failed write that appears successful is worse than a visible failure.

```python
async def write_agent_output(session_id: str, agent_name: str, brd_text: str) -> None:
    blob_name = f"{session_id}/agent_{agent_name}.json"
    blob = bucket.blob(blob_name)
    try:
        async with asyncio.timeout(15.0):
            blob.upload_from_string(
                json.dumps({"agent": agent_name, "brd": brd_text}),
                content_type="application/json"
            )
    except Exception as e:
        raise ContextForgeError(
            f"GCS write failed for {agent_name}: {e}",
            "gcs_write_failure",
            status_code=500
        )
```

### Rule DB-003: Agent output blobs are written immediately after each agent completes
Do not batch GCS writes. Each agent output must be written to GCS the moment its Gemini call returns, not after all 6 have completed. This ensures partial results are preserved if the overall swarm fails mid-run.

### Rule DB-004: GCS reads must check blob existence before attempting download
Never call `blob.download_as_text()` without first checking `blob.exists()`. Missing blobs return a 404 from the API, not a 500.

```python
async def read_agent_output(session_id: str, agent_name: str) -> dict:
    blob = bucket.blob(f"{session_id}/agent_{agent_name}.json")
    if not blob.exists():
        raise ContextForgeError(
            f"Agent output not found: {agent_name}",
            "agent_output_missing",
            status_code=404
        )
    return json.loads(blob.download_as_text())
```

### Rule DB-005: All GCS blobs must be written with `content_type="application/json"`
Never write a blob without specifying its content type. This enables correct serving via signed URLs and allows GCS to enforce content policies.

---

## BigQuery Rules

### Rule DB-006: All BigQuery inserts use `insert_rows_json()` with schema validation
Never use string-interpolated BigQuery SQL queries. All writes must go through `insert_rows_json()` with a pre-validated dict that matches the table schema. Row dicts must be validated against Pydantic models before insertion.

```python
# CORRECT
from google.cloud import bigquery

def log_harvest(client: bigquery.Client, dataset: str, row: ContextHarvestLog) -> None:
    table_ref = f"{dataset}.context_harvest_logs"
    errors = client.insert_rows_json(table_ref, [row.model_dump(mode="json")])
    if errors:
        raise ContextForgeError(f"BigQuery insert failed: {errors}", "bq_insert_failure")

# FORBIDDEN: never use string SQL with user data
query = f"INSERT INTO context_harvest_logs VALUES ('{user_data}')"  # SQL injection
```

### Rule DB-007: BigQuery writes are fire-and-forget but errors must be logged
BigQuery logging must not block the main request pipeline. Wrap BigQuery writes in `asyncio.create_task()` after the critical path is complete. Errors from BigQuery writes must be logged at `WARNING` level but must not cause the API response to fail.

```python
# Correct pattern: non-blocking BQ write
async def handle_generate(session_id: str) -> None:
    context = await harvest_context(region, industry)
    # Fire BQ write but do not await it — it must not block the swarm
    asyncio.create_task(_log_harvest_to_bq(context, session_id))
    # Continue with swarm immediately
    results = await run_swarm(package)
```

### Rule DB-008: Never query BigQuery from a hot path
BigQuery is for offline analytics and logging, not for runtime session lookup. All session state during an active BRD run must be held in the FastAPI process (or in-memory dict / Redis). Never perform a BigQuery `SELECT` query as part of serving an HTTP request.

### Rule DB-009: BigQuery table names are always read from `config.py`
Never hardcode BigQuery table or dataset names. All references must use `settings.BIGQUERY_DATASET` from `config.py`.

---

## N+1 Prevention & Query Performance

### Rule DB-010: No per-agent GCS reads in a loop during BRD retrieval
When the merge engine or evaluator needs all 6 agent outputs, fetch them in parallel using `asyncio.gather()`, never one-by-one in a loop.

```python
# CORRECT: parallel fetch
agent_names = ["vc", "lean", "cto", "ux", "regulator", "adversarial"]
outputs = await asyncio.gather(
    *[read_agent_output(session_id, name) for name in agent_names]
)

# FORBIDDEN: serial loop (N+1 equivalent for GCS)
outputs = []
for name in agent_names:
    outputs.append(await read_agent_output(session_id, name))  # serial = slow
```

### Rule DB-011: Context Harvester API calls are always parallel
All 5 context sources (NewsAPI, World Bank, Crunchbase, Govt Open Data, Gemini Grounding) must be called via `asyncio.gather()` with `return_exceptions=True`. A single slow API must not hold up the others.

---

## Data Integrity & Migration Rules

### Rule DB-012: BigQuery schema changes require a migration comment block
Any change to a BigQuery table schema (adding, removing, or renaming a column) must be accompanied by a comment block in the relevant `gcp/bigquery.py` function explaining the change, the date, and the backward-compatibility strategy.

### Rule DB-013: The `schema_version` field must be incremented on any `brd_runs` schema change
When the `brd_runs` table schema changes, increment `CURRENT_SCHEMA_VERSION` in `config.py` and ensure all new writes include the updated version. This enables version-aware queries on historical data.

### Rule DB-014: GCS bucket must be configured with Uniform Bucket-Level Access
Never use ACL-based access control on the GCS bucket. The bucket must use Uniform Bucket-Level Access (set via `gsutil uniformbucketlevelaccess set on gs://{bucket_name}`). IAM policies on the service account govern all access.

### Rule DB-015: Session IDs in GCS paths are always lowercase
UUID v4 session IDs are inherently lowercase hex. If a session ID is ever normalised, lowercase it before using it in a GCS path. Mixed-case paths in GCS are distinct objects, which can cause duplicates.

```python
# Always lowercase the session_id before using in a path
blob_name = f"{session_id.lower()}/agent_{agent_name}.json"
```

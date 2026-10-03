# ContextForge — Product Requirements Document
**Version:** 1.0 | **Prepared by:** Syed Zahid | **Date:** October 2026  
**Hackathon:** Hack Sprint — CDN Commudle Developer Network | **Track:** PS42 — Google Gemini AI + Google Cloud

---

## 1. Executive Summary, Target Audience & Core Value Proposition

### Executive Summary

ContextForge is a multi-modal AI system that transforms raw, unstructured business ideas — expressed as text, voice, images, or documents — into production-grade Business Requirements Documents (BRDs) backed by live market intelligence. It does this by routing a user's input through eight specialised AI agents simultaneously, each operating from a different expert persona (VC investor, lean founder, enterprise CTO, UX researcher, regulator, and adversarial competitor), then evaluating, merging, and presenting the synthesised output with full lineage attribution and confidence scoring.

The system is not a document generator. It is a structured disagreement engine: it forces a business idea through incompatible expert lenses, surfaces where those lenses diverge (the Divergence Heatmap), and constructs the strongest possible BRD from the surviving best sections — all grounded in real-world data pulled from live APIs at the moment of analysis.

### Target Audience

**Primary:** Early-stage founders and solopreneurs preparing for pre-seed or seed fundraising who need investor-grade BRDs but cannot afford a consultant.

**Secondary:** Product managers in mid-stage startups who need rapid, structured requirements documentation when exploring new verticals.

**Tertiary:** Hackathon participants and student entrepreneurs in emerging markets (India, Southeast Asia, Sub-Saharan Africa) where regulatory complexity and local market data are hardest to surface.

### Core Value Proposition

> A single AI call produces a generic, unchallenged BRD. ContextForge produces a *contested* one — where a regulator, a competitor, and a first-principles builder have all stress-tested your idea before you see a word.

Every requirement in the final BRD carries four pieces of metadata: the requirement itself, the agent that produced it, the real-world data point that supports it, and a confidence score. No other tool on the market surfaces the disagreement between expert perspectives as actionable signal.

---

## 2. System Architecture

### 2.1 High-Level Architecture & Component Boundary Map

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  CLIENT LAYER (Vercel — React + Vite)                                                │
│                                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  ChatBox    │  │ FileUpload  │  │  AgentGrid   │  │  BRDViewer + ScoreCard   │  │
│  │ (Text+Voice)│  │(Img + Docs) │  │(Live status) │  │  + DivergenceHeatmap     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘  └────────────┬─────────────┘  │
│         │                │                 │                        │                │
└─────────┼────────────────┼─────────────────┼────────────────────────┼────────────────┘
          │  REST / SSE    │                 │  WebSocket / SSE        │
┌─────────▼────────────────▼─────────────────▼────────────────────────▼────────────────┐
│  API GATEWAY LAYER (FastAPI on Railway)                                               │
│                                                                                      │
│  POST /intake/chat   POST /intake/upload   GET /session/{id}/status   GET /brd/{id}  │
│                                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────┐   │
│  │  ORCHESTRATION LAYER (Vertex AI)                                              │   │
│  │  Job: session_id → tracks agent states, retries, completion signals          │   │
│  └───────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐    │
│  │  INTAKE PROCESSOR                                                            │    │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────────────┐   │    │
│  │  │  Conversational │  │  Gemini Vision   │  │  PyPDF2 / python-docx     │   │    │
│  │  │  Intake (Flash) │  │  (Image Context) │  │  (Document Extraction)    │   │    │
│  │  └─────────────────┘  └──────────────────┘  └───────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐    │
│  │  CONTEXT HARVESTER (Parallel async)                                          │    │
│  │  ┌──────────┐ ┌────────────┐ ┌─────────────┐ ┌────────────┐ ┌───────────┐  │    │
│  │  │ NewsAPI  │ │ World Bank │ │ Crunchbase  │ │ Govt Open  │ │  Gemini   │  │    │
│  │  │          │ │    API     │ │   Basic     │ │    Data    │ │ Grounding │  │    │
│  │  └──────────┘ └────────────┘ └─────────────┘ └────────────┘ └───────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐    │
│  │  SWARM LAYER — asyncio.gather() — 6 parallel Gemini 1.5 Flash calls         │    │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────────┐    │    │
│  │  │ Agent1 │ │ Agent2 │ │ Agent3 │ │ Agent4 │ │ Agent5 │ │   Agent6    │    │    │
│  │  │  VC    │ │  Lean  │ │  CTO   │ │  UX    │ │  Reg.  │ │ Adversarial │    │    │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └─────────────┘    │    │
│  └──────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  ┌──────────────────────┐   ┌────────────────────────────────────────────────┐      │
│  │  EVALUATOR           │   │  MERGE ENGINE                                  │      │
│  │  Gemini 1.5 Pro      │──▶│  Gemini 1.5 Pro                                │      │
│  │  Scores 6 BRDs       │   │  Constructs final BRD from best-scoring        │      │
│  │  across 5 sections   │   │  section per agent                             │      │
│  └──────────────────────┘   └────────────────────────────────────────────────┘      │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐     │
│  │  OUTPUT LAYER                                                               │     │
│  │  ┌──────────────────┐  ┌────────────────────┐  ┌─────────────────────────┐ │     │
│  │  │ Heatmap Calc.    │  │  Investor Score    │  │  PDF (ReportLab) /      │ │     │
│  │  │ (FastAPI)        │  │  (FastAPI)         │  │  Google Docs API        │ │     │
│  │  └──────────────────┘  └────────────────────┘  └─────────────────────────┘ │     │
│  └─────────────────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────────────────┘
          │                              │
┌─────────▼──────────────────────────────▼────────────────────────────────────────────┐
│  GCP PERSISTENCE LAYER                                                               │
│  ┌─────────────────────────┐         ┌─────────────────────────────────────────┐    │
│  │  Cloud Storage (GCS)    │         │  BigQuery                               │    │
│  │  {session_id}/          │         │  contextforge_data.context_harvest      │    │
│  │    {agent_name}.json    │         │  contextforge_data.brd_runs             │    │
│  │    merged_brd.json      │         │  contextforge_data.evaluator_scores     │    │
│  └─────────────────────────┘         └─────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 End-to-End Data Flow Lifecycle

| Step | Layer | Action | Inputs | Outputs |
|------|-------|--------|--------|---------|
| 1 | Client | User enters idea via text or voice (Web Speech API / Gemini Audio fallback). Optional file upload. | Raw text / audio blob / file | Transmitted to FastAPI |
| 2 | FastAPI + Gemini Flash | Conversational intake: extract region, industry, stage, constraints. Run Gemini Vision on images. Extract document text via PyPDF2 / python-docx. | User turns + files | `intake_summary` JSON, `file_context` |
| 3 | FastAPI (async) | Context Harvester fires parallel API calls (NewsAPI, World Bank, Crunchbase, Govt Open Data, Gemini Search Grounding). Logged to BigQuery. | `region`, `industry` | `context_package` JSON |
| 4 | FastAPI | Merge intake summary + file context + context package into unified Intake Package. | All prior outputs | `intake_package` JSON |
| 5 | FastAPI + Gemini Flash ×6 | `asyncio.gather()` fires 6 Flash calls with different system prompts. Each returns a full BRD. Written to GCS. Vertex AI tracks job status. | `intake_package` + 6 system prompts | 6 BRD JSONs in GCS |
| 6 | Gemini 1.5 Pro | Evaluator receives all 6 BRDs + context package. Scores each across 5 sections × 5 criteria. | 6 BRDs + context | `score_matrix` JSON |
| 7 | Gemini 1.5 Pro | Merge Engine receives score matrix + 6 BRDs. Selects best-scoring section from best agent per section. Outputs final BRD with lineage tags. | Score matrix + 6 BRDs | `merged_brd` JSON → GCS |
| 8 | FastAPI (math) | Calculate Divergence Heatmap: std dev of per-section scores across agents. Normalise to 0–100 risk scale. | `score_matrix` | `heatmap_data` JSON |
| 9 | FastAPI (math) | Investor Readiness Score: weighted sum of rubric scores, normalised to 100. Extract gap flags. | `score_matrix` | `readiness_score` + `gaps[]` |
| 10 | FastAPI + ReportLab | PDF generation. Optional Google Docs API call. Push to GCS output prefix. | `merged_brd` | `.pdf` file, Google Doc URL |
| 11 | Client | Render heatmap → BRD viewer with lineage → score card. Offer download. | API responses | Full UI experience |

### 2.3 Concurrency, Latency & Throughput Targets

| Metric | Target | Mechanism |
|--------|--------|-----------|
| End-to-end BRD generation | < 45 seconds P95 | Parallel swarm (steps 5–7 dominate; steps 5+6+7 ≈ 30s) |
| Swarm (6 Flash calls) | < 20 seconds P95 | `asyncio.gather()` with 6 concurrent HTTP calls |
| Context Harvester | < 8 seconds P95 | `asyncio.gather()` on 5 external API calls |
| Evaluator + Merge (2 Pro calls sequential) | < 18 seconds P95 | Sequential by design (merge depends on eval) |
| Heatmap + score calculation | < 200 ms | Pure Python math, no I/O |
| GCS write per agent | < 500 ms | Fire-and-forget async after agent response |
| Concurrent demo sessions | 5 simultaneous | API key rotation pool across 10+ keys |
| Frontend SSE update frequency | 1 event/second per agent | FastAPI SSE endpoint streams agent status |
| PDF generation | < 3 seconds | ReportLab synchronous, called last |

---

## 3. Complete Database Schema Contract

ContextForge uses **BigQuery** as its primary structured data store for context harvesting logs, BRD run metadata, and evaluator scores. **Cloud Storage** (GCS) holds raw JSON blobs. The schemas below define both the BigQuery tables (for querying/analytics) and the GCS blob structures.

### 3.1 BigQuery Dataset: `contextforge_data`

#### Table: `brd_runs`

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| `session_id` | STRING | REQUIRED | UUID v4. Primary key. Partition key. |
| `created_at` | TIMESTAMP | REQUIRED | UTC timestamp of session creation. Default: `CURRENT_TIMESTAMP()` |
| `completed_at` | TIMESTAMP | NULLABLE | UTC timestamp of final merged BRD completion. |
| `user_anonymous_id` | STRING | NULLABLE | Hashed browser fingerprint. No PII. Max 64 chars. |
| `intake_summary` | STRING | REQUIRED | JSON string of extracted intake data. Max 10,000 chars. |
| `region` | STRING | REQUIRED | ISO 3166-1 alpha-2 country code. E.g., `IN`, `US`, `NG`. Max 2 chars. |
| `industry` | STRING | REQUIRED | Free-text industry tag extracted from intake. Max 100 chars. |
| `stage` | STRING | NULLABLE | Business stage. ENUM: `idea`, `prototype`, `mvp`, `growth`. |
| `status` | STRING | REQUIRED | Run status. ENUM: `intake`, `harvesting`, `swarm_running`, `evaluating`, `merging`, `complete`, `failed`. |
| `error_message` | STRING | NULLABLE | Last error message if status = `failed`. Max 2,000 chars. |
| `input_modalities` | STRING | REPEATED | Modalities used. ENUM values: `text`, `voice`, `image`, `document`. |
| `gcs_session_prefix` | STRING | REQUIRED | GCS path prefix. E.g., `gs://contextforge-outputs/{session_id}/`. |
| `investor_readiness_score` | FLOAT64 | NULLABLE | Final score 0–100.0. Populated on completion. |
| `schema_version` | INT64 | REQUIRED | Schema version for migration tracking. Default: `1`. |

**Partitioning:** `created_at` (DATE), daily partitions.  
**Clustering:** `region`, `industry`, `status`.  
**Index justification:** Partitioning by date supports time-range queries on run history. Clustering by region+industry enables aggregation queries (e.g., average investor readiness by country/sector).

#### Table: `context_harvest_logs`

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| `harvest_id` | STRING | REQUIRED | UUID v4. Primary key. |
| `session_id` | STRING | REQUIRED | FK → `brd_runs.session_id`. |
| `harvested_at` | TIMESTAMP | REQUIRED | UTC timestamp. Default: `CURRENT_TIMESTAMP()` |
| `source` | STRING | REQUIRED | API source. ENUM: `newsapi`, `worldbank`, `crunchbase`, `govt_open_data`, `gemini_grounding`. |
| `region` | STRING | REQUIRED | ISO 3166-1 alpha-2. |
| `industry` | STRING | NULLABLE | Industry tag passed to this source. |
| `request_url` | STRING | REQUIRED | Full URL called (with params). Max 2,000 chars. |
| `response_status_code` | INT64 | REQUIRED | HTTP response code from external API. |
| `response_item_count` | INT64 | NULLABLE | Number of items returned (articles, competitors, etc.). |
| `latency_ms` | INT64 | REQUIRED | Round-trip latency in milliseconds. |
| `cached` | BOOL | REQUIRED | Whether result was served from cache. Default: `false`. |
| `error_detail` | STRING | NULLABLE | Error message if response_status_code >= 400. |

**Partitioning:** `harvested_at` (DATE).  
**Clustering:** `source`, `region`.

#### Table: `evaluator_scores`

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| `score_id` | STRING | REQUIRED | UUID v4. Primary key. |
| `session_id` | STRING | REQUIRED | FK → `brd_runs.session_id`. |
| `agent_name` | STRING | REQUIRED | ENUM: `vc`, `lean`, `cto`, `ux`, `regulator`, `adversarial`. |
| `section_name` | STRING | REQUIRED | ENUM: `problem_statement`, `functional_requirements`, `technical_requirements`, `risk_register`, `timeline_milestones`. |
| `criterion` | STRING | REQUIRED | ENUM: `feasibility`, `market_timing`, `regulatory_safety`, `user_adoption`, `competitive_moat`. |
| `score` | FLOAT64 | REQUIRED | Score 0.0–100.0. |
| `citation` | STRING | NULLABLE | One-line data citation supporting the score. Max 500 chars. |
| `evaluated_at` | TIMESTAMP | REQUIRED | UTC timestamp. Default: `CURRENT_TIMESTAMP()` |

**Partitioning:** `evaluated_at` (DATE).  
**Clustering:** `session_id`, `agent_name`.

#### Table: `divergence_heatmap_data`

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| `heatmap_id` | STRING | REQUIRED | UUID v4. Primary key. |
| `session_id` | STRING | REQUIRED | FK → `brd_runs.session_id`. |
| `section_name` | STRING | REQUIRED | ENUM: same as `evaluator_scores.section_name`. |
| `agreement_score` | FLOAT64 | REQUIRED | 0.0–100.0. Higher = more agreement = lower risk. |
| `std_deviation` | FLOAT64 | REQUIRED | Raw std dev of the 6 agent scores for this section. |
| `risk_level` | STRING | REQUIRED | ENUM: `low` (>70), `medium` (40–70), `high` (<40). |
| `min_score` | FLOAT64 | REQUIRED | Lowest agent score for this section. |
| `max_score` | FLOAT64 | REQUIRED | Highest agent score for this section. |
| `dominant_agent` | STRING | REQUIRED | Agent with highest score on this section. |
| `calculated_at` | TIMESTAMP | REQUIRED | UTC timestamp. |

### 3.2 GCS Blob Schema: `contextforge-outputs/{session_id}/`

| Blob Path | Format | Contents |
|-----------|--------|----------|
| `{session_id}/intake_package.json` | JSON | Full intake summary, region, industry, stage, file contexts, context package |
| `{session_id}/agent_vc.json` | JSON | Full BRD output from VC agent, raw text |
| `{session_id}/agent_lean.json` | JSON | Full BRD output from Lean Founder agent |
| `{session_id}/agent_cto.json` | JSON | Full BRD output from CTO agent |
| `{session_id}/agent_ux.json` | JSON | Full BRD output from UX Researcher agent |
| `{session_id}/agent_regulator.json` | JSON | Full BRD output from Regulator agent |
| `{session_id}/agent_adversarial.json` | JSON | Full BRD output from Adversarial agent |
| `{session_id}/score_matrix.json` | JSON | Full evaluator output: all scores + citations per agent × section × criterion |
| `{session_id}/merged_brd.json` | JSON | Final merged BRD with lineage tags, confidence scores, all sections |
| `{session_id}/heatmap.json` | JSON | Heatmap data: agreement scores per section |
| `{session_id}/investor_readiness.json` | JSON | Score (0–100), gaps[], weighted breakdown |
| `{session_id}/output.pdf` | PDF | ReportLab-generated PDF of merged BRD |

#### GCS Blob JSON Schemas

**`intake_package.json`:**
```json
{
  "session_id": "string (uuid4)",
  "created_at": "string (ISO 8601 UTC)",
  "conversation_turns": [
    { "role": "user|assistant", "content": "string" }
  ],
  "extracted": {
    "business_idea": "string",
    "region": "string (ISO 3166-1 alpha-2)",
    "industry": "string",
    "stage": "idea|prototype|mvp|growth",
    "budget_range": "string|null",
    "constraints": ["string"]
  },
  "file_contexts": {
    "image_analyses": ["string (Gemini Vision output per image)"],
    "document_summaries": ["string (extracted text summary per doc)"]
  },
  "context_package": {
    "news": [{ "headline": "string", "date": "string", "source": "string", "url": "string" }],
    "market": { "gdp_usd": "number", "ease_of_business_rank": "number", "inflation_pct": "number", "fdi_inflow_usd": "number" },
    "competitors": [{ "name": "string", "funding": "string", "stage": "string", "founded": "string" }],
    "regulatory": ["string"],
    "cultural": "string"
  }
}
```

**`merged_brd.json`:**
```json
{
  "session_id": "string",
  "generated_at": "string (ISO 8601 UTC)",
  "sections": {
    "problem_statement": {
      "content": "string (full section text)",
      "source_agent": "vc|lean|cto|ux|regulator|adversarial",
      "agent_score": "number (0-100)",
      "data_citations": ["string"],
      "confidence_score": "number (0-100)",
      "dissenting_agents": [{ "agent": "string", "key_disagreement": "string" }]
    },
    "functional_requirements": { "...same shape..." },
    "technical_requirements": { "...same shape..." },
    "risk_register": { "...same shape..." },
    "timeline_milestones": { "...same shape..." }
  },
  "investor_readiness_score": "number",
  "investor_readiness_gaps": ["string"],
  "heatmap_summary": {
    "highest_risk_section": "string",
    "lowest_risk_section": "string"
  }
}
```

---

## 4. Exhaustive API Interface Contract

### Base URL
- **Production:** `https://api.contextforge.app`
- **Local dev:** `http://localhost:8000`

### Authentication
All routes except `/health` and `/intake/session` (POST) require a `session_id` query parameter or `X-Session-ID` header that was previously issued. No user account system — session-scoped access only. Rate limiting is applied per IP.

### 4.1 Session Management

#### `POST /intake/session`
Create a new BRD session.

**Auth:** None required.  
**Rate limit:** 10 requests/15 minutes per IP.

**Request Body:** None.

**Response 201:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-10-01T12:00:00Z",
  "status": "intake",
  "expires_at": "2026-10-01T14:00:00Z"
}
```

**Response 429:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many session creation requests. Please wait before trying again.",
  "retry_after_seconds": 60
}
```

**Response 500:**
```json
{
  "error": "internal_error",
  "message": "Failed to initialise session. Please try again.",
  "request_id": "req_abc123"
}
```

---

#### `GET /intake/session/{session_id}`
Get current session status.

**Auth:** Valid `session_id` path param.  
**Rate limit:** 60 requests/minute per IP.

**Response 200:**
```json
{
  "session_id": "string",
  "status": "intake|harvesting|swarm_running|evaluating|merging|complete|failed",
  "created_at": "string",
  "completed_at": "string|null",
  "input_modalities": ["text", "voice", "image", "document"],
  "agent_statuses": {
    "vc": "pending|running|complete|failed",
    "lean": "pending|running|complete|failed",
    "cto": "pending|running|complete|failed",
    "ux": "pending|running|complete|failed",
    "regulator": "pending|running|complete|failed",
    "adversarial": "pending|running|complete|failed"
  },
  "progress_pct": 0
}
```

**Response 404:**
```json
{
  "error": "session_not_found",
  "message": "No session found with the provided ID.",
  "session_id": "string"
}
```

---

### 4.2 Intake & File Upload

#### `POST /intake/chat`
Submit a conversational turn. Returns the AI's next question or confirmation that intake is complete.

**Auth:** Valid `X-Session-ID` header.  
**Rate limit:** 30 requests/minute per session.  
**Content-Type:** `application/json`

**Request Body:**
```typescript
{
  role: "user";                  // required
  content: string;               // required. Min 1 char, max 5,000 chars.
  session_id: string;            // required. UUID v4.
}
```

**Response 200:**
```json
{
  "session_id": "string",
  "response": {
    "role": "assistant",
    "content": "string (AI follow-up question or intake complete confirmation)",
    "intake_complete": false,
    "extracted_so_far": {
      "business_idea": "string|null",
      "region": "string|null",
      "industry": "string|null",
      "stage": "string|null",
      "budget_range": "string|null"
    },
    "context_harvesting_started": false
  }
}
```

**Response 400:**
```json
{
  "error": "validation_error",
  "message": "Request body validation failed.",
  "details": [
    { "field": "content", "issue": "Field is required and must be non-empty." }
  ]
}
```

**Response 401:**
```json
{
  "error": "invalid_session",
  "message": "Session ID is missing, invalid, or expired.",
  "session_id": "string|null"
}
```

**Response 403:**
```json
{
  "error": "session_state_error",
  "message": "Intake is already complete for this session. Cannot accept new chat turns.",
  "current_status": "string"
}
```

---

#### `POST /intake/upload`
Upload an image or document for multimodal processing.

**Auth:** Valid `X-Session-ID` header.  
**Rate limit:** 10 uploads/session.  
**Content-Type:** `multipart/form-data`  
**Max file size:** 20 MB per file. Max 5 files per session.

**Request Form Fields:**
```typescript
{
  session_id: string;            // required
  file: File;                    // required. Accepted MIME types below.
  file_type: "image" | "document"; // required
}
```

**Accepted MIME types:**
- Images: `image/jpeg`, `image/png`, `image/webp`, `image/gif`
- Documents: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (DOCX), `text/plain`

**Response 200:**
```json
{
  "session_id": "string",
  "upload_id": "string (uuid4)",
  "file_type": "image|document",
  "original_filename": "string",
  "processing_status": "queued|processing|complete|failed",
  "extracted_context_preview": "string|null (first 500 chars of extracted content)"
}
```

**Response 400:**
```json
{
  "error": "validation_error",
  "message": "File type not supported or file exceeds size limit.",
  "details": [
    { "field": "file", "issue": "Accepted types: JPEG, PNG, WEBP, GIF, PDF, DOCX, TXT. Max size: 20MB." }
  ]
}
```

**Response 413:**
```json
{
  "error": "file_too_large",
  "message": "File size exceeds the 20MB limit.",
  "max_size_mb": 20,
  "submitted_size_mb": 25.4
}
```

---

### 4.3 BRD Generation

#### `POST /generate`
Trigger the full BRD generation pipeline. Requires intake to be complete.

**Auth:** Valid `X-Session-ID` header.  
**Rate limit:** 5 generation requests/hour per IP.  
**Content-Type:** `application/json`

**Request Body:**
```typescript
{
  session_id: string;            // required
}
```

**Response 202:**
```json
{
  "session_id": "string",
  "status": "swarm_running",
  "message": "BRD generation started. Poll /intake/session/{session_id} or subscribe to /generate/stream/{session_id} for progress.",
  "estimated_seconds": 45
}
```

**Response 409:**
```json
{
  "error": "generation_already_running",
  "message": "A BRD generation job is already active for this session.",
  "current_status": "swarm_running"
}
```

---

#### `GET /generate/stream/{session_id}`
Server-Sent Events stream for real-time agent status updates.

**Auth:** Valid `session_id` path param.  
**Content-Type:** `text/event-stream`

**Event Types:**
```
event: agent_started
data: {"agent": "vc", "timestamp": "2026-10-01T12:00:05Z"}

event: agent_complete
data: {"agent": "vc", "timestamp": "2026-10-01T12:00:18Z", "word_count": 1247}

event: agent_failed
data: {"agent": "cto", "timestamp": "2026-10-01T12:00:20Z", "error": "API rate limit hit. Retrying with backup key."}

event: swarm_complete
data: {"timestamp": "2026-10-01T12:00:25Z", "agents_succeeded": 6, "agents_failed": 0}

event: evaluator_complete
data: {"timestamp": "2026-10-01T12:00:35Z"}

event: merge_complete
data: {"timestamp": "2026-10-01T12:00:42Z"}

event: generation_complete
data: {"session_id": "string", "brd_url": "/brd/{session_id}", "timestamp": "2026-10-01T12:00:44Z"}

event: generation_failed
data: {"error": "string", "recoverable": true|false, "timestamp": "string"}
```

---

### 4.4 BRD Retrieval & Output

#### `GET /brd/{session_id}`
Retrieve the complete merged BRD with lineage and scores.

**Auth:** Valid `session_id` path param.  
**Rate limit:** 60 requests/minute per IP.

**Response 200:** Full `merged_brd.json` schema (see §3.2).

**Response 404:**
```json
{
  "error": "brd_not_found",
  "message": "No completed BRD found for this session. Check generation status.",
  "session_id": "string",
  "current_status": "string"
}
```

---

#### `GET /brd/{session_id}/heatmap`
Retrieve Divergence Heatmap data.

**Response 200:**
```json
{
  "session_id": "string",
  "sections": [
    {
      "section_name": "problem_statement",
      "label": "Problem Statement",
      "agreement_score": 82.0,
      "risk_level": "low",
      "std_deviation": 9.0,
      "min_score": 71.0,
      "max_score": 94.0,
      "dominant_agent": "ux",
      "per_agent_scores": {
        "vc": 88.0, "lean": 71.0, "cto": 82.0,
        "ux": 94.0, "regulator": 79.0, "adversarial": 76.0
      }
    }
  ]
}
```

---

#### `GET /brd/{session_id}/score`
Retrieve the Investor Readiness Score.

**Response 200:**
```json
{
  "session_id": "string",
  "investor_readiness_score": 73.0,
  "breakdown": {
    "feasibility": { "score": 80.0, "weight": 0.25, "weighted_contribution": 20.0 },
    "market_timing": { "score": 78.0, "weight": 0.20, "weighted_contribution": 15.6 },
    "regulatory_safety": { "score": 48.0, "weight": 0.20, "weighted_contribution": 9.6 },
    "user_adoption": { "score": 82.0, "weight": 0.20, "weighted_contribution": 16.4 },
    "competitive_moat": { "score": 55.0, "weight": 0.15, "weighted_contribution": 8.25 }
  },
  "gaps": [
    { "criterion": "regulatory_safety", "score": 48.0, "threshold": 60.0, "action": "FSSAI licensing requirements for food tech in India need addressing before Series A pitch." },
    { "criterion": "competitive_moat", "score": 55.0, "threshold": 60.0, "action": "No defensible advantage over existing players documented. Strengthen moat narrative." }
  ]
}
```

---

#### `GET /brd/{session_id}/download`
Download BRD as PDF.

**Response 200:** Binary PDF file.  
**Content-Type:** `application/pdf`  
**Content-Disposition:** `attachment; filename="contextforge-brd-{session_id[:8]}.pdf"`

**Response 425:**
```json
{
  "error": "pdf_not_ready",
  "message": "PDF generation is still in progress.",
  "retry_after_seconds": 5
}
```

---

#### `GET /health`
Health check endpoint.

**Auth:** None.  
**Response 200:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-10-01T12:00:00Z",
  "dependencies": {
    "gemini_api": "ok|degraded|down",
    "gcs": "ok|degraded|down",
    "bigquery": "ok|degraded|down"
  }
}
```

---

## 5. UI/UX Design System Specification

### 5.1 Design Philosophy
ContextForge's visual language is that of a **mission control room**: dark, precise, high-information density. The UI should feel like you are watching six expert analysts work simultaneously and their outputs are being synthesised in real time. It is not a word processor. It is a command centre.

### 5.2 Color Palette Tokens

| Token Name | Hex | Usage |
|------------|-----|-------|
| `--color-void` | `#050A14` | Page background — deep space navy, not pure black |
| `--color-surface` | `#0C1524` | Card/panel backgrounds |
| `--color-elevated` | `#132035` | Elevated panels, modals, dropdowns |
| `--color-border` | `#1E3050` | Borders, dividers, hairlines |
| `--color-border-subtle` | `#0F1F38` | Subtle dividers within cards |
| `--color-text-primary` | `#E8F0FE` | Primary readable text |
| `--color-text-secondary` | `#7B9CC7` | Supporting text, labels, metadata |
| `--color-text-muted` | `#3D5A80` | Placeholder, disabled text |
| `--color-accent-signal` | `#00C2FF` | Primary accent — electric blue. SSE events, active states, links |
| `--color-accent-pulse` | `#0070E0` | Agent running indicator, progress rings |
| `--color-success` | `#00D68F` | Agent complete status, confidence high |
| `--color-warning` | `#FFB020` | Medium risk heatmap cells, medium confidence |
| `--color-error` | `#FF4D4F` | High risk heatmap cells, agent failed, errors |
| `--color-risk-high` | `#FF4D4F` | Heatmap: agreement < 40% |
| `--color-risk-medium` | `#FFB020` | Heatmap: agreement 40–70% |
| `--color-risk-low` | `#00D68F` | Heatmap: agreement > 70% |
| `--color-agent-vc` | `#C084FC` | VC agent accent — venture purple |
| `--color-agent-lean` | `#34D399` | Lean founder accent — go-fast green |
| `--color-agent-cto` | `#60A5FA` | CTO agent accent — architecture blue |
| `--color-agent-ux` | `#F472B6` | UX researcher accent — empathy pink |
| `--color-agent-regulator` | `#FBBF24` | Regulator accent — caution amber |
| `--color-agent-adversarial` | `#F87171` | Adversarial accent — threat red |
| `--color-overlay` | `rgba(5,10,20,0.85)` | Modal overlays, loading screens |
| `--color-gradient-start` | `#050A14` | Background radial gradient centre |
| `--color-gradient-particle` | `rgba(0,194,255,0.06)` | Particle canvas dots |

### 5.3 Typography System

**Display font:** `Space Grotesk` (Google Fonts) — bold, geometric, technical. Used for headings, agent names, score readouts.  
**Body font:** `Inter` (Google Fonts) — neutral, highly legible for BRD content at any size.  
**Monospace font:** `JetBrains Mono` (Google Fonts) — code blocks, session IDs, citation metadata, lineage tags.

| Scale Name | Size | Weight | Line Height | Usage |
|------------|------|--------|-------------|-------|
| `--text-display` | `3.5rem / 56px` | 700 | 1.1 | Hero readouts (Investor Score number) |
| `--text-h1` | `2rem / 32px` | 700 | 1.2 | Page section headers |
| `--text-h2` | `1.5rem / 24px` | 600 | 1.3 | BRD section headers, card titles |
| `--text-h3` | `1.125rem / 18px` | 600 | 1.4 | Agent names, subsection headers |
| `--text-body` | `0.9375rem / 15px` | 400 | 1.6 | BRD body content |
| `--text-body-sm` | `0.8125rem / 13px` | 400 | 1.5 | Metadata, citations, secondary labels |
| `--text-caption` | `0.6875rem / 11px` | 500 | 1.4 | Tags, chips, status labels |
| `--text-mono` | `0.8125rem / 13px` | 400 | 1.6 | Session IDs, lineage tags, confidence scores |
| `--text-score` | `4.5rem / 72px` | 700 | 1.0 | Investor Readiness Score number |

### 5.4 Component Hierarchy & View States

#### ChatBox Component
- **Default:** Single borderless textarea on void background. Cursor blinks. Placeholder: "Describe your business idea — as a sentence, a voice note, or a document."
- **Focused:** `--color-border` outline appears (1px, 4px border-radius). Character count appears bottom-right.
- **Voice active:** Microphone icon pulses (CSS `animation: pulse 1.5s ease-in-out infinite`). Waveform visualisation renders in the input area (canvas element with `--color-accent-signal` bars).
- **Sending:** Submit button replaces with a spinner. Input becomes `readonly`.
- **Error:** Red border, error message below: "Something went wrong. Your message was not sent."

#### AgentGrid Component (6 cards in 2×3 or 3×2 grid)
Each card shows: Agent name, agent persona subtitle, current status chip, word count (on completion), a micro-animation.

- **Pending:** Card at 40% opacity. Agent icon silhouette visible. Status chip: grey "Waiting".
- **Running:** Card fades to full opacity. Status chip: `--color-accent-pulse` pulsing "Thinking...". A **canvas-rendered neural net animation** runs behind the card: 12–20 nodes connected by edges that fire in sequence, simulating neural activity. Edge colour matches the agent's accent colour (`--color-agent-{name}`).
- **Complete:** Neural net animation freezes into a static glowing state. Status chip: `--color-success` "Done". Word count appears. Card border glows with agent accent colour for 2 seconds then fades to subtle.
- **Failed:** Card dims to 20% opacity. Status chip: `--color-error` "Failed". Retry button appears. Neural net animation plays a "shutdown" sequence (nodes dim one by one).
- **Skeleton (loading initial state):** All 6 cards show shimmer skeleton animation before session is created.

#### DivergenceHeatmap Component
- **Default (loading):** Grid of 5 cells showing pulse skeleton animation.
- **Populated:** 5 rows (one per BRD section), each row showing:
  - Section label (left, `--text-h3`)
  - Agreement bar (centre) — horizontal bar, width = agreement %, colour mapped from `--color-risk-high` → `--color-risk-medium` → `--color-risk-low` via gradient. Animated fill: CSS `transition: width 800ms cubic-bezier(0.34, 1.56, 0.64, 1)` (slight overshoot spring for drama).
  - Agreement % (right, `--text-body-sm`, colour-coded)
  - Risk chip (far right) — "HIGH RISK" / "MEDIUM RISK" / "LOW RISK"
- **Row hover:** Expands to show per-agent mini-scores as dots (6 dots, colour = agent accent colour). Tooltip shows agent name + score.

#### BRDViewer Component
- **Loading:** Skeleton shimmer on 5 section blocks.
- **Populated:** Each section renders:
  - Section header with dominant agent badge (coloured with `--color-agent-{name}`)
  - Body text in `--text-body` / `Inter`
  - "Data Citations" collapsible block below each section
  - Confidence score badge: circular progress ring, fill colour matches risk level
  - "Dissenting views" collapsible: lists agents that disagreed and their key point
- **Error:** Isolated section error state: "This section could not be generated. [Retry section]"

#### ScoreCard Component
- **Default:** Full-width card at bottom of BRD. Large score number (`--text-score`), circular gauge animation on load (0 → final score, 1.2 seconds).
- **Populated:** 5 criterion rows with bar charts (weighted contribution). Gaps section below with red warning cards per gap item.

### 5.5 Micro-interactions & Animation Specifications

| Interaction | Duration | Easing | Notes |
|-------------|----------|--------|-------|
| Agent card fade-in (on session create) | 400ms staggered, 60ms between each | `ease-out` | Cards appear left-to-right, top-to-bottom |
| Agent status chip colour change | 300ms | `ease-in-out` | Colour and text change simultaneously |
| Heatmap bar fill | 800ms per bar, staggered 100ms | `cubic-bezier(0.34,1.56,0.64,1)` | Overshoot spring — lands at final width |
| Score gauge animation | 1200ms | `ease-out` | SVG stroke-dashoffset from 0 → final |
| Section reveal in BRDViewer | 500ms per section, staggered 80ms | `ease-out` | Sections slide up from 20px offset + fade in |
| Confidence score ring | 600ms | `ease-in-out` | SVG stroke-dashoffset |
| Agent neural net canvas | Continuous while running | — | requestAnimationFrame at 60fps |
| ChatBox input voice waveform | Continuous while recording | — | Canvas bars at 60fps from AudioContext AnalyserNode |
| Page background particle field | Continuous | — | 120 particles on canvas, slow drift, connections drawn between nearby particles using `--color-gradient-particle` |

### 5.6 Background Canvas Rendering Specification

**Particle field (global background):**
```
Canvas: full viewport, fixed position, z-index -1, pointer-events none
Particles: 120 circles, radius 1–3px, colour rgba(0,194,255,0.4)
Motion: each particle drifts at 0.2–0.5 px/frame in a random direction, wraps at viewport edges
Connections: draw a line between any two particles within 120px. Line opacity = (1 - distance/120) * 0.15. Colour: rgba(0,194,255,{opacity})
On swarm running: particle speed increases by 3×, connection opacity increases by 2×. Reverts after swarm completes.
```

**Agent neural net (per-card canvas):**
```
Canvas: fills agent card background, z-index 0, pointer-events none
Nodes: 16 circles, radius 3px, positioned in 4 concentric rings
Edges: fully connected graph between nodes in adjacent rings
Animation: a "signal" travels along each edge in sequence (CSS-like: a bright dot moves along the line at 60fps)
Signal colour: agent accent colour (--color-agent-{name})
On agent complete: all nodes glow white simultaneously, then fade to static low-opacity state
On agent failed: nodes dim one by one over 800ms
```

---

## 6. Threat Model & Security Specification

### 6.1 Authentication Lifecycle
ContextForge uses **session-scoped, anonymous access** (no user accounts). Sessions are identified by a UUID v4 session token that is:
- **Issued** server-side by `POST /intake/session`
- **Stored client-side** in `sessionStorage` only (not `localStorage`, not cookies) — does not persist across browser restarts. This is appropriate because BRD sessions are ephemeral by design.
- **Transmitted** in `X-Session-ID` header on all subsequent requests
- **Validated** on every request: server checks UUID format, session existence in an in-memory Redis/dict cache, and expiration (2-hour TTL from last activity)
- **Revoked** automatically on TTL expiry. Manual revocation available via `DELETE /intake/session/{session_id}` (no auth required — sessions are anonymous; knowing the ID is sufficient to revoke)

### 6.2 Rate Limiting Configuration

| Endpoint Group | Window | Limit | Action on Exceed |
|----------------|--------|-------|------------------|
| `POST /intake/session` | 15 minutes | 10 per IP | 429, `retry_after_seconds` |
| `POST /intake/chat` | 1 minute | 30 per session | 429 |
| `POST /intake/upload` | 1 session lifetime | 10 files | 429 |
| `POST /generate` | 1 hour | 5 per IP | 429 |
| All GET endpoints | 1 minute | 60 per IP | 429 |
| Global | 1 minute | 200 per IP | 429 + IP logged |

### 6.3 OWASP Top 10 Mitigations

| Threat | Mitigation |
|--------|------------|
| **A01 Broken Access Control** | All routes validate session_id. GCS blobs are keyed by UUID — no sequential IDs. No user can enumerate sessions. |
| **A02 Cryptographic Failures** | All data in transit via TLS 1.3. GCS bucket has uniform bucket-level access (no ACLs). No user PII stored. |
| **A03 Injection** | All user inputs are passed to Gemini as content strings, never interpolated into SQL, system commands, or file paths. File paths generated exclusively from UUIDs. |
| **A04 Insecure Design** | Context Harvester URLs are constructed from a whitelist of allowed API base URLs. User-provided region/industry values are normalised and validated against allowlists before being interpolated into API calls. |
| **A05 Security Misconfiguration** | CORS restricted to `CONTEXTFORGE_ALLOWED_ORIGINS`. No debug endpoints in production. FastAPI docs disabled in production (`docs_url=None`). |
| **A06 Vulnerable & Outdated Components** | `pip-audit` and `npm audit` run in pre-delivery audit workflow. Dependabot enabled on repo. |
| **A07 Auth & Session Management Failures** | Session IDs are UUID v4 (cryptographically random). TTL enforced server-side, not client-side. Sessions cannot be extended by the client. |
| **A08 Software & Data Integrity** | All GCS writes include SHA-256 checksum via `x-goog-hash` header. Dependency lockfile (`requirements.txt` pinned versions) committed to repo. |
| **A09 Security Logging & Monitoring** | All rate limit triggers, invalid session attempts, and upload rejections logged to Cloud Logging with `severity: WARNING`. Context harvester errors logged with full request URL redacted of API keys. |
| **A10 SSRF** | Context Harvester uses an explicit whitelist of allowed outbound domains. No user-controlled URLs are fetched. Any URL constructed from user input (e.g., `?region=IN`) uses only the path-safe extracted value, not the raw string. |

### 6.4 Input Sanitization Boundaries

| Input Source | Sanitization Applied |
|--------------|---------------------|
| Chat messages (`/intake/chat`) | Max length 5,000 chars. Strip null bytes. No HTML parsing (sent as text to Gemini). Validate UTF-8 encoding. |
| File uploads | MIME type verified against Python `magic` library (not trusting Content-Type header). File scanned for malicious content via filename extension allowlist + file header magic bytes check. Files never executed. |
| Region (extracted by Gemini) | Validated against ISO 3166-1 alpha-2 country code regex `^[A-Z]{2}$` before use in any API call. |
| Industry (extracted by Gemini) | Stripped to `[a-zA-Z0-9 \-]`, max 100 chars, before use in NewsAPI/Crunchbase calls. |
| Session IDs (all routes) | Validated against UUID v4 regex `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` before any lookup. |

### 6.5 Secret Sanitization in Logs

All log entries are filtered through a regex sanitizer that replaces any string matching:
- `[A-Za-z0-9]{32,}` appearing as a URL query parameter value named `key`, `api_key`, `token`, or `secret`
- The literal value of any environment variable listed in `.env.example` under `# AI/LLM Provider Keys` or `# Third-Party APIs`

With `[REDACTED]` before the log entry is written to Cloud Logging or stdout.

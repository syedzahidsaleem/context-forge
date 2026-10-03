# AGENTS.md — ContextForge Workspace Governance
**Immutable rules for all AI coding agents, Antigravity sessions, and human contributors.**  
These rules are not guidelines. Violations block merges.

---

## 1. System Invariants

### 1.1 Runtime & Framework Choices

| Layer | Technology | Version Pin | Notes |
|-------|-----------|------------|-------|
| Frontend runtime | Node.js | `>=20.11.0` LTS | Never use Node <18 |
| Frontend framework | React | `^18.3.0` | Functional components only. No class components. |
| Frontend build | Vite | `^5.4.0` | Do not use Create React App or Next.js |
| Frontend deploy | Vercel | Latest | Static output. No Vercel serverless functions — all API calls go to Railway backend |
| Backend runtime | Python | `3.12.x` | Must be pinned in `Dockerfile` and `.python-version` |
| Backend framework | FastAPI | `^0.115.0` | Async-first. Pydantic v2 for all models. |
| Backend deploy | Railway | Latest | Dockerfile-based deployment |
| Package manager (JS) | `npm` | Lockfile: `package-lock.json` | `npm ci` only in CI. Never `npm install` in CI. |
| Package manager (Python) | `pip` | Lockfile: `requirements.txt` (pinned) | All versions pinned with `==`. No `>=` in requirements.txt |
| Python type checking | `mypy` | `^1.10.0` | `strict = true` mode. No `# type: ignore` without a comment explaining why. |
| Python linting | `ruff` | `^0.5.0` | Replaces flake8 + isort + black. Config in `pyproject.toml`. |
| JavaScript linting | ESLint | `^9.0.0` | Flat config (`eslint.config.js`). Airbnb rules base. |
| JavaScript formatting | Prettier | `^3.3.0` | Config in `.prettierrc`. Single quotes, 2-space indent. |

### 1.2 TypeScript / JavaScript Compiler Flags

The frontend uses JSX with strict runtime checks via ESLint, not TypeScript compilation. However, JSDoc type annotations are required on all exported functions.

**ESLint enforced rules:**
```json
{
  "no-unused-vars": "error",
  "no-implicit-globals": "error",
  "no-var": "error",
  "prefer-const": "error",
  "eqeqeq": ["error", "always"],
  "no-console": ["warn", { "allow": ["error", "warn"] }],
  "react-hooks/rules-of-hooks": "error",
  "react-hooks/exhaustive-deps": "error"
}
```

### 1.3 Python Strict Mypy Configuration (`pyproject.toml`)
```toml
[tool.mypy]
strict = true
python_version = "3.12"
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_any_generics = true
no_implicit_optional = true
check_untyped_defs = true
```

### 1.4 Approved Dependency Lists

**Backend (Python) — required, no substitutions without PR discussion:**
```
fastapi==0.115.2
uvicorn[standard]==0.30.6
pydantic==2.9.2
google-generativeai==0.8.3
google-cloud-storage==2.18.2
google-cloud-bigquery==3.25.0
google-cloud-aiplatform==1.68.0
reportlab==4.2.5
pypdf2==3.0.1
python-docx==1.1.2
httpx==0.27.2
python-multipart==0.0.12
python-magic==0.4.27
ruff==0.5.7
mypy==1.11.2
pytest==8.3.3
pytest-asyncio==0.24.0
```

**Frontend (JS) — required:**
```
react@18.3.1
react-dom@18.3.1
vite@5.4.8
@vitejs/plugin-react@4.3.1
eslint@9.11.1
prettier@3.3.3
```

---

## 2. Architectural Boundaries

### 2.1 Strict Separation of Concerns

**Frontend (React) is allowed to:**
- Render UI from props and state
- Make HTTP/SSE calls to the FastAPI backend at `VITE_API_BASE_URL`
- Use the Web Speech API and `AudioContext` for voice/waveform
- Store session_id in `sessionStorage` only
- Animate via CSS transitions and Canvas 2D API

**Frontend is FORBIDDEN from:**
- Calling Gemini, GCS, BigQuery, or any GCP API directly
- Holding any API key (Gemini, NewsAPI, Crunchbase, etc.) in client-side code or environment variables prefixed with `VITE_` — with the sole exception of `VITE_API_BASE_URL`
- Performing any PDF generation, text extraction, or AI inference
- Storing user content (chat messages, uploaded files) in `localStorage` or `IndexedDB`

**Backend (FastAPI) is the exclusive home for:**
- All Gemini API calls (swarm, evaluator, merge, vision, audio, grounding)
- All GCP calls (GCS, BigQuery, Vertex AI)
- All third-party API calls (NewsAPI, World Bank, Crunchbase, Govt Open Data)
- File processing (image analysis, PDF/DOCX text extraction)
- Session management and TTL enforcement
- Rate limiting logic (via `slowapi` or in-memory dict)
- Investor Readiness Score and Heatmap calculation

### 2.2 Backend Module Separation

| Module | Responsibility | May Import From | May NOT Import From |
|--------|---------------|----------------|---------------------|
| `agents/swarm.py` | Fire 6 parallel Gemini Flash calls | `agents/prompts.py`, `gcp/storage.py` | `intake/`, `context/`, `output/` |
| `agents/evaluator.py` | Score 6 BRDs | `agents/prompts.py`, `gcp/storage.py` | `agents/swarm.py` |
| `agents/merge.py` | Build merged BRD | `agents/prompts.py`, `gcp/storage.py` | `agents/swarm.py`, `agents/evaluator.py` |
| `agents/prompts.py` | System prompt constants | Nothing (pure constants) | Everything else |
| `intake/conversation.py` | Conversational intake flow | `agents/` (Flash only) | `context/`, `output/` |
| `intake/vision.py` | Gemini Vision for images | Nothing (pure Gemini call) | `agents/`, `context/`, `output/` |
| `intake/documents.py` | PyPDF2 / python-docx extraction | Nothing (pure extraction) | `agents/`, `context/`, `output/` |
| `context/harvester.py` | Orchestrate all context API calls | `context/newsapi.py`, `context/worldbank.py`, `context/grounding.py` | `agents/`, `output/` |
| `output/heatmap.py` | Heatmap calculation (pure math) | Nothing | Everything |
| `output/scoring.py` | Investor Readiness Score (pure math) | Nothing | Everything |
| `output/pdf_gen.py` | ReportLab PDF generation | Nothing (takes dict input) | Everything except data models |
| `gcp/storage.py` | GCS read/write | Nothing | `agents/`, `intake/`, `context/` |
| `gcp/bigquery.py` | BigQuery write | Nothing | `agents/`, `intake/`, `context/` |
| `gcp/vertex.py` | Vertex AI job tracking | Nothing | `agents/`, `intake/`, `context/` |
| `main.py` | FastAPI app, route definitions, orchestration | All of the above | No business logic lives here |

**Critical rule:** `main.py` contains ONLY route definitions and orchestration calls. No business logic, no Gemini calls, no calculations. If logic is more than 10 lines, it belongs in a module.

### 2.3 Server-Only Secrets Boundary

The following environment variables are **strictly forbidden from appearing in any client-side code**, Vite config with `VITE_` prefix, API response body, log output, or error message returned to the client:

```
GEMINI_API_KEY_1 through GEMINI_API_KEY_N
NEWS_API_KEY
CRUNCHBASE_API_KEY
GCP_PROJECT_ID        (sensitive in combination with other GCP vars)
GCS_BUCKET_NAME       (prevents enumeration)
BIGQUERY_DATASET      (prevents enumeration)
VERTEX_AI_LOCATION
GCP_SERVICE_ACCOUNT_JSON
```

**The only variable permitted in client-side scope:**
```
VITE_API_BASE_URL     (the Railway backend URL, not a secret)
```

---

## 3. Code Quality & Failure Semantics

### 3.1 Error Handling Patterns

**Python — Standard Application Error Classes:**
All application errors inherit from `ContextForgeError` defined in `backend/errors.py`:
```python
class ContextForgeError(Exception):
    def __init__(self, message: str, code: str, status_code: int = 500) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)

class SessionNotFoundError(ContextForgeError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session not found: {session_id}", "session_not_found", 404)

class IntakeIncompleteError(ContextForgeError):
    def __init__(self) -> None:
        super().__init__("Intake not complete. Cannot trigger generation.", "intake_incomplete", 409)

class AgentFailureError(ContextForgeError):
    def __init__(self, agent_name: str, reason: str) -> None:
        super().__init__(f"Agent {agent_name} failed: {reason}", "agent_failure", 500)

class ContextHarvestError(ContextForgeError):
    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"Context harvest failed for {source}: {reason}", "harvest_failure", 500)

class FileProcessingError(ContextForgeError):
    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(f"File processing failed for {filename}: {reason}", "file_processing_failure", 422)
```

All FastAPI routes must catch `ContextForgeError` and return a standardised error response:
```python
@app.exception_handler(ContextForgeError)
async def contextforge_error_handler(request: Request, exc: ContextForgeError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "request_id": request.state.request_id}
    )
```

**No bare `except Exception` clauses.** Every `except` clause must catch a specific exception type or `ContextForgeError` subclass.

### 3.2 Async Invariants

- **No floating promises / unawaited coroutines.** Every `async` call must be awaited or wrapped in `asyncio.create_task()` with a reference held.
- **All external network calls must have a timeout wrapper.** No Gemini call, GCS call, or third-party API call may be made without an explicit timeout:
  ```python
  # Correct
  async with asyncio.timeout(30.0):
      response = await gemini_client.generate_content_async(...)
  
  # Forbidden
  response = await gemini_client.generate_content_async(...)  # No timeout
  ```
- **Standard timeouts:**
  | Call Type | Timeout |
  |-----------|---------|
  | Gemini Flash (swarm) | 30 seconds |
  | Gemini Pro (evaluator/merge) | 60 seconds |
  | Gemini Vision | 20 seconds |
  | NewsAPI | 10 seconds |
  | World Bank API | 10 seconds |
  | Crunchbase | 10 seconds |
  | GCS write | 15 seconds |
  | BigQuery insert | 15 seconds |

- **`asyncio.gather()` always uses `return_exceptions=True`** for the swarm call so one failing agent does not crash the others:
  ```python
  results = await asyncio.gather(
      *[run_agent(name, prompt, package) for name, prompt in agents.items()],
      return_exceptions=True
  )
  # Then inspect each result: if isinstance(result, Exception): handle gracefully
  ```

### 3.3 Structured Logging

All log entries must use structured JSON via Python's `logging` module with a JSON formatter (not print statements):

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
            "session_id": getattr(record, "session_id", None),
        }
        return json.dumps(log_entry)
```

**Forbidden in logs:**
- Any value from the `SERVER_ONLY_SECRETS` list (enforced by the sanitizer middleware)
- Full file upload content
- Full Gemini API responses (log word count and status only)

---

## 4. Directory Layout Conventions

```
contextforge/
├── frontend/                        # React + Vite client
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── components/              # UI components (one file per component)
│   │   │   ├── ChatBox.jsx          # Conversational intake + voice
│   │   │   ├── FileUpload.jsx       # Image + document upload
│   │   │   ├── AgentGrid.jsx        # 6-agent status grid with canvas animations
│   │   │   ├── AgentCard.jsx        # Individual agent card (used by AgentGrid)
│   │   │   ├── NeuralNetCanvas.jsx  # Per-agent neural net animation canvas
│   │   │   ├── ParticleBackground.jsx # Global particle field canvas
│   │   │   ├── Heatmap.jsx          # Divergence heatmap visualisation
│   │   │   ├── BRDViewer.jsx        # Merged BRD renderer with lineage
│   │   │   ├── BRDSection.jsx       # Individual BRD section block
│   │   │   ├── ScoreCard.jsx        # Investor Readiness Score display
│   │   │   ├── ContextPanel.jsx     # Live context harvest display
│   │   │   └── DownloadBar.jsx      # PDF download + Google Docs link
│   │   ├── hooks/                   # Custom React hooks
│   │   │   ├── useSession.js        # Session creation and status polling
│   │   │   ├── useSSE.js            # Server-Sent Events subscription
│   │   │   ├── useVoiceInput.js     # Web Speech API + Gemini Audio fallback
│   │   │   ├── useFileUpload.js     # File upload with progress
│   │   │   └── useParticleCanvas.js # Particle animation loop
│   │   ├── lib/                     # Pure utility functions (no React)
│   │   │   ├── api.js               # All fetch() calls to backend (typed wrappers)
│   │   │   ├── constants.js         # AGENT_NAMES, SECTION_NAMES, RISK_THRESHOLDS
│   │   │   └── colours.js           # Design token exports for canvas use
│   │   ├── App.jsx                  # Root component, state orchestration
│   │   └── main.jsx                 # ReactDOM.createRoot entry
│   ├── .eslintrc.js
│   ├── .prettierrc
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
│
├── backend/                         # FastAPI Python backend
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── swarm.py                 # asyncio.gather() for 6 Flash calls
│   │   ├── evaluator.py             # Gemini Pro evaluator call
│   │   ├── merge.py                 # Gemini Pro merge engine call
│   │   └── prompts.py               # All 8 system prompt constants (SCREAMING_SNAKE_CASE)
│   ├── intake/
│   │   ├── __init__.py
│   │   ├── conversation.py          # Conversational intake state machine
│   │   ├── vision.py                # Gemini Vision processing
│   │   └── documents.py             # PyPDF2 + python-docx extraction
│   ├── context/
│   │   ├── __init__.py
│   │   ├── harvester.py             # Orchestrates all context API calls
│   │   ├── newsapi.py               # NewsAPI client
│   │   ├── worldbank.py             # World Bank API client
│   │   ├── crunchbase.py            # Crunchbase API client
│   │   └── grounding.py             # Gemini Search Grounding call
│   ├── output/
│   │   ├── __init__.py
│   │   ├── heatmap.py               # Agreement calculation (pure functions)
│   │   ├── scoring.py               # Investor Readiness Score (pure functions)
│   │   └── pdf_gen.py               # ReportLab PDF generation
│   ├── gcp/
│   │   ├── __init__.py
│   │   ├── storage.py               # GCS read/write helpers
│   │   ├── bigquery.py              # BigQuery insert helpers
│   │   └── vertex.py                # Vertex AI job status helpers
│   ├── models/                      # Pydantic v2 data models
│   │   ├── __init__.py
│   │   ├── session.py               # Session, SessionStatus models
│   │   ├── intake.py                # IntakePackage, ConversationTurn models
│   │   ├── brd.py                   # BRDSection, MergedBRD, LineageTag models
│   │   ├── scores.py                # ScoreMatrix, InvestorReadinessScore models
│   │   └── heatmap.py               # HeatmapData, HeatmapSection models
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── rate_limit.py            # Rate limiting middleware
│   │   ├── request_id.py            # X-Request-ID injection
│   │   └── log_sanitizer.py         # Secret-stripping log filter
│   ├── errors.py                    # All ContextForgeError subclasses
│   ├── config.py                    # Settings via pydantic-settings, reads .env
│   ├── key_pool.py                  # Gemini API key rotation pool
│   ├── main.py                      # FastAPI app, route definitions, CORS, startup
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
│
├── .agents/                         # AI agent governance (this repo)
│   ├── rules/
│   │   ├── architecture.md
│   │   ├── database.md
│   │   ├── security.md
│   │   └── ui-ux.md
│   ├── skills/
│   │   ├── brd-section-merge/SKILL.md
│   │   ├── agent-persona-calibration/SKILL.md
│   │   └── context-harvester-assembly/SKILL.md
│   ├── workflows/
│   │   ├── setup-and-migrate.md
│   │   └── pre-delivery-audit.md
│   └── mcp_config.json
│
├── .env.example
├── PRD.md
├── AGENTS.md
├── README.md
└── .gitignore
```

### 4.1 File Size Limits

| File Type | Max Lines | Enforcement |
|-----------|-----------|-------------|
| Any Python module | 350 lines | Ruff rule `E501` + manual review |
| Any React component | 250 lines | ESLint custom rule |
| `main.py` (FastAPI) | 150 lines | Manual review in PR |
| `agents/prompts.py` | Unlimited | It is a data file, not logic |
| Any test file | 400 lines | No limit per test, but split by module |

### 4.2 Export Patterns

**Python:** All public symbols in a module must be listed in `__all__`. Anything not in `__all__` is private.  
**JavaScript:** Named exports only. No default exports except for React components (which use `export default`). No re-exporting from barrel `index.js` files (causes circular dependency risk and hurts tree-shaking).

### 4.3 Anti-Patterns — Explicitly Forbidden

| Anti-pattern | Why | Alternative |
|-------------|-----|-------------|
| Circular imports between Python modules | Breaks mypy and runtime import order | Use the module boundary table in §2.2 |
| Business logic in `main.py` FastAPI routes | Routes become untestable blobs | Extract to service functions in the appropriate module |
| Gemini API calls in `intake/` or `context/` modules — except for `intake/conversation.py`, `intake/vision.py`, and `context/grounding.py` | Violates module boundary | Route all Gemini calls through the appropriate module |
| `asyncio.gather()` without `return_exceptions=True` on the swarm call | One agent failure crashes all | Always use `return_exceptions=True` |
| Hardcoded API keys in source code | Security violation | Always read from `config.py` / environment |
| `time.sleep()` in async code | Blocks the event loop | Use `await asyncio.sleep()` |
| `requests` library in async code | Blocking I/O | Use `httpx.AsyncClient` |
| `console.log()` in production React code | Log pollution | Remove before build; use `console.error()` for actual errors only |
| CSS `!important` in component stylesheets | Overrides become unpredictable | Fix specificity instead |
| Canvas `context.clearRect()` outside the animation loop | Causes flickering | Clear at the top of every frame in requestAnimationFrame |

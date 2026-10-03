---
trigger: always_on
description: "Security safeguards, input validation, secret sanitization, and auth rules for ContextForge"
priority: 1
applies_to: ["backend/**/*.py", "frontend/src/**/*.js", "frontend/src/**/*.jsx"]
---

# Security Rules — ContextForge

These rules apply to every file in the repository. Security rules take precedence over all other rules including architecture and UI/UX rules.

---

## Input Validation — Pydantic Schemas

### Rule SEC-001: All HTTP request bodies must have a Pydantic v2 schema
No FastAPI route may accept raw `dict`, `Any`, or untyped `body` parameters. All request bodies must be validated through a `BaseModel` subclass defined in `backend/models/`.

```python
# CORRECT
class ChatRequest(BaseModel):
    session_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
    content: str = Field(..., min_length=1, max_length=5000)
    role: Literal["user"]

@app.post("/intake/chat")
async def chat(body: ChatRequest) -> ChatResponse:
    ...

# FORBIDDEN
@app.post("/intake/chat")
async def chat(body: dict) -> dict:  # untyped — never
    ...
```

### Rule SEC-002: Session ID must be validated as UUID v4 on every endpoint
Before any lookup, every session ID must be validated against the UUID v4 regex pattern. An invalid format must return 401 immediately, not a database lookup attempt.

```python
SESSION_ID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
)

def validate_session_id(session_id: str) -> None:
    if not SESSION_ID_PATTERN.match(session_id):
        raise SessionNotFoundError(session_id)
```

### Rule SEC-003: Region codes extracted from Gemini must be validated before use in API calls
The extracted region string from the conversational intake is LLM output and must be treated as untrusted. Before using it in any outbound API call (NewsAPI, World Bank, Crunchbase), validate it against the ISO 3166-1 alpha-2 allowlist:

```python
import re

REGION_PATTERN = re.compile(r'^[A-Z]{2}$')

def validate_region(region: str) -> str:
    normalised = region.strip().upper()
    if not REGION_PATTERN.match(normalised):
        raise ValueError(f"Invalid region code extracted: {region!r}")
    return normalised
```

### Rule SEC-004: Industry strings extracted from Gemini must be sanitized before use in API calls
```python
import re

def sanitize_industry(industry: str) -> str:
    sanitised = re.sub(r'[^a-zA-Z0-9 \-]', '', industry).strip()[:100]
    if not sanitised:
        raise ValueError("Industry string is empty after sanitization")
    return sanitised
```

### Rule SEC-005: File uploads must be validated by MIME type via magic bytes, not extension
The file extension provided by the client must never be trusted. Use Python's `python-magic` library to read the file's actual magic bytes:

```python
import magic

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain"
}

def validate_file_type(file_bytes: bytes) -> str:
    mime_type = magic.from_buffer(file_bytes[:1024], mime=True)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise FileProcessingError("uploaded_file", f"Unsupported MIME type: {mime_type}")
    return mime_type
```

---

## Secret Handling

### Rule SEC-006: No API keys may appear in any log entry
All log entries must pass through the `LogSanitizer` defined in `backend/middleware/log_sanitizer.py`. This middleware applies a regex filter that replaces any detected API key pattern with `[REDACTED]`. This applies to: stdout, Cloud Logging, error messages returned to the client, and SSE event data.

The sanitizer regex targets:
- Any value of URL query parameter named `key`, `api_key`, `apikey`, `token`, `secret`, `auth`
- The literal values of `GEMINI_API_KEY_*`, `NEWS_API_KEY`, `CRUNCHBASE_API_KEY`

### Rule SEC-007: Client error responses must never expose internal paths, stack traces, or config values
The FastAPI exception handler must catch all unhandled exceptions and return only the standardised error shape. The `detail` field from FastAPI's default 422 handler must be overridden to prevent Pydantic validation field paths from leaking internal model structure.

```python
# FORBIDDEN — leaks internal structure
raise HTTPException(status_code=500, detail=f"Error in backend/gcp/storage.py line 42: {e}")

# CORRECT — safe error response
raise ContextForgeError("Storage operation failed. Please try again.", "storage_error", 500)
```

### Rule SEC-008: `GCP_SERVICE_ACCOUNT_JSON_B64` must be decoded at startup only
The base64-encoded service account JSON must be decoded once at application startup (in `config.py` or `main.py` lifespan event) and stored in a `tempfile.NamedTemporaryFile` that is deleted when the process exits. It must not be decoded on every request.

### Rule SEC-009: API key rotation pool must never log which key was used
The `key_pool.py` rotation logic must log only the key index used (e.g., `"Using key index 2"`) and never the key value itself, even in DEBUG mode.

---

## Cookie & Session Security

### Rule SEC-010: Session IDs are stored in `sessionStorage` only, never `localStorage` or cookies
The frontend `useSession.js` hook must store the session ID exclusively in `window.sessionStorage`. The rationale: sessions are ephemeral (2-hour TTL), BRD content is sensitive business information, and `localStorage` persists across restarts enabling session hijacking via XSS over a longer window.

```javascript
// Correct
sessionStorage.setItem('contextforge_session_id', sessionId);
const sessionId = sessionStorage.getItem('contextforge_session_id');

// FORBIDDEN
localStorage.setItem('contextforge_session_id', sessionId);  // persists too long
document.cookie = `session_id=${sessionId}`;  // not needed, adds CSRF surface
```

### Rule SEC-011: CORS must be configured with explicit origin allowlist
The FastAPI `CORSMiddleware` must use `allow_origins=settings.CORS_ALLOWED_ORIGINS.split(",")`. The wildcard `allow_origins=["*"]` is forbidden in production. In development, the allowed origins list must include only `http://localhost:5173`.

---

## Rate Limiting

### Rule SEC-012: Rate limit exceeded responses must not reveal the limit configuration
The 429 response body must include `retry_after_seconds` but must not expose the specific rate limit thresholds (e.g., "You have hit the 10 requests/15min limit"). This prevents adversaries from precisely timing requests to stay under the limit.

```python
# CORRECT
return JSONResponse(status_code=429, content={
    "error": "rate_limit_exceeded",
    "message": "Too many requests. Please wait before trying again.",
    "retry_after_seconds": 60
})

# FORBIDDEN — reveals limit config
return JSONResponse(status_code=429, content={
    "error": "rate_limit_exceeded",
    "message": "You have exceeded the limit of 10 session creations per 15 minutes."
})
```

---

## SSRF Prevention

### Rule SEC-013: Context Harvester must only call whitelisted domains
All outbound HTTP calls in `context/` modules must use the `ALLOWED_OUTBOUND_DOMAINS` allowlist defined in `config.py`. Before making any HTTP call, verify the target URL's hostname is in the allowlist. User-provided URLs may never be fetched.

```python
ALLOWED_OUTBOUND_DOMAINS = frozenset({
    "newsapi.org",
    "api.worldbank.org",
    "api.crunchbase.com",
    "generativelanguage.googleapis.com",
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
})

def validate_outbound_url(url: str) -> None:
    from urllib.parse import urlparse
    hostname = urlparse(url).hostname
    if hostname not in ALLOWED_OUTBOUND_DOMAINS:
        raise ContextForgeError(
            f"Outbound call to non-whitelisted domain blocked: {hostname}",
            "ssrf_blocked",
            status_code=403
        )
```

### Rule SEC-014: No user-controlled string may be interpolated directly into an outbound URL
User-extracted values (region, industry, business idea text) may only be used as URL query parameter values via `httpx`'s `params=` argument, never via f-string URL construction.

```python
# CORRECT: httpx handles URL encoding of params
response = await client.get(
    "https://newsapi.org/v2/everything",
    params={"q": sanitized_industry, "country": validated_region, "apiKey": "[REDACTED]"}
)

# FORBIDDEN: direct string interpolation into URL
url = f"https://newsapi.org/v2/everything?q={user_industry}&apiKey={key}"  # injection risk
```

---

## Gemini Prompt Injection Prevention

### Rule SEC-015: User input must be isolated as the `user` role, never injected into system prompts
Agent system prompts are fixed constants defined in `agents/prompts.py`. User-provided content (business idea, extracted intake) must only appear in the `user` role of the Gemini API call. It must never be string-interpolated into the `system_instruction` parameter.

```python
# CORRECT: user content stays in user role
response = await model.generate_content_async([
    Content(role="user", parts=[Part(text=f"Business Idea: {intake_summary}\nContext: {context_json}")])
])

# FORBIDDEN: user content injected into system prompt
model = genai.GenerativeModel(
    model_name=settings.GEMINI_FLASH_MODEL,
    system_instruction=f"{VC_SYSTEM_PROMPT}\n\nUser's idea: {user_input}"  # injection risk
)
```

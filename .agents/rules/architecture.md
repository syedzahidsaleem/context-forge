---
trigger: always_on
description: "System architecture and clean-code boundaries for ContextForge"
priority: 1
applies_to: ["backend/**/*.py", "frontend/src/**/*.js", "frontend/src/**/*.jsx"]
---

# Architecture Rules — ContextForge

These rules are enforced on every file in the repository. They cannot be overridden by inline comments or PR descriptions. If a rule conflicts with a feature request, the rule wins — escalate to human review instead.

---

## Module Boundary Rules

### Rule ARCH-001: Module ownership is absolute
Each Python module in `backend/` owns a specific domain. No module may reach across its boundary to perform work owned by another module. The complete boundary map is defined in `AGENTS.md §2.2`. Before adding any import, verify that the importing module is permitted to import from the target module per that table.

**Violation example:**
```python
# In backend/context/harvester.py — FORBIDDEN
from agents.swarm import run_agent  # harvester cannot call agents
```

**Correct pattern:**
```python
# In backend/main.py — CORRECT
# main.py orchestrates: call harvester, then call swarm separately
context = await harvest_context(region, industry)
brd_outputs = await run_swarm(intake_package)
```

### Rule ARCH-002: `main.py` is a thin orchestrator only
`main.py` may contain only: FastAPI app initialisation, middleware registration, route function definitions, and calls to service functions. The body of each route function must not exceed 30 lines. All logic exceeding 5 lines must be extracted to the appropriate module.

**Violation example:**
```python
# In backend/main.py — FORBIDDEN
@app.post("/generate")
async def generate(session_id: str):
    # 80 lines of Gemini calls and GCS writes inline here
    ...
```

**Correct pattern:**
```python
# In backend/main.py — CORRECT
@app.post("/generate")
async def generate(body: GenerateRequest, request: Request) -> GenerateResponse:
    session = await get_session(body.session_id)
    await trigger_generation_pipeline(session)  # all logic in agents/, gcp/ modules
    return GenerateResponse(session_id=body.session_id, status="swarm_running")
```

### Rule ARCH-003: No circular imports
No module may form a circular import chain. The dependency direction is:
`main.py` → `agents/` / `intake/` / `context/` / `output/` → `gcp/` → `models/` → `errors.py` → `config.py`

Arrows point toward dependencies. No module may import from a module that is higher in this chain. `mypy` will catch most circular import issues but you must also verify with `python -c "import backend.main"` at the shell.

### Rule ARCH-004: All public symbols must be in `__all__`
Every Python module must define `__all__` listing all symbols intended for external use. Anything not in `__all__` is considered private and must be prefixed with `_`.

```python
# Correct
__all__ = ["run_swarm", "AgentResult"]

async def run_swarm(package: IntakePackage) -> list[AgentResult]:
    ...

def _build_agent_prompt(agent_name: str) -> str:  # private helper
    ...
```

---

## Export Patterns

### Rule ARCH-005: React components use default exports; all other JS uses named exports
```javascript
// Component file (correct)
export default function AgentCard({ agent, status }) { ... }

// Utility file (correct)
export function buildApiUrl(path) { ... }
export const AGENT_NAMES = ['vc', 'lean', 'cto', 'ux', 'regulator', 'adversarial'];

// FORBIDDEN: default export of non-component
export default { buildApiUrl };  // do not do this
```

### Rule ARCH-006: No barrel index files
Do not create `src/components/index.js` or any file that re-exports from multiple modules. Each file is imported by its explicit path. This prevents circular dependencies and improves tree-shaking.

```javascript
// FORBIDDEN
// src/components/index.js
export { default as AgentCard } from './AgentCard';
export { default as ChatBox } from './ChatBox';

// Correct: import directly
import AgentCard from './components/AgentCard';
import ChatBox from './components/ChatBox';
```

---

## File Size Limits

### Rule ARCH-007: File size hard limits
| File type | Maximum lines | Action if exceeded |
|-----------|-------------|-------------------|
| Python service module | 350 lines | Split by extracting a helper module |
| React component | 250 lines | Extract child components or custom hooks |
| `main.py` | 150 lines | Extract route handlers to `routers/` directory |
| `agents/prompts.py` | Unlimited | It is a data file — all constants |
| Test files | 400 lines | Split by test class or describe block |

---

## Anti-Pattern Prohibitions

### Rule ARCH-008: No logic in controllers / route handlers
Route functions define the HTTP contract. They validate input (via Pydantic), call one service function, and return the response. Nothing else.

### Rule ARCH-009: No string-typed configuration in code
All configuration values (model names, timeouts, bucket names, rate limits) must be read from `config.py`, which reads from environment variables. No hardcoded strings for infrastructure values anywhere in the codebase.

```python
# FORBIDDEN
response = await gemini_client.generate_content("gemini-1.5-flash", ...)

# Correct
from config import settings
response = await gemini_client.generate_content(settings.GEMINI_FLASH_MODEL, ...)
```

### Rule ARCH-010: No synchronous blocking calls in async functions
`requests`, `time.sleep()`, `open()` on large files, and any CPU-bound loop > 10ms must not appear inside `async def` functions. Use `httpx.AsyncClient` for HTTP, `await asyncio.sleep()` for delays, and `asyncio.to_thread()` for CPU-bound work.

### Rule ARCH-011: Canvas animation must use requestAnimationFrame exclusively
All canvas-based animations (particle field, neural net) must use `requestAnimationFrame` for their animation loop. `setInterval` and `setTimeout` are forbidden for animation rendering. The animation loop must check `isRunning` state and exit cleanly when the component unmounts:

```javascript
useEffect(() => {
  let animFrameId;
  let isRunning = true;

  function draw() {
    if (!isRunning) return;
    // ... render frame
    animFrameId = requestAnimationFrame(draw);
  }

  animFrameId = requestAnimationFrame(draw);

  return () => {
    isRunning = false;
    cancelAnimationFrame(animFrameId);
  };
}, []);
```

### Rule ARCH-012: SSE connections must be cleaned up on component unmount
All `EventSource` connections opened in React components or hooks must be closed in the cleanup function of `useEffect`. Dangling SSE connections will silently exhaust Railway's connection limit.

```javascript
useEffect(() => {
  const source = new EventSource(`${API_BASE}/generate/stream/${sessionId}`);
  source.onmessage = handleEvent;
  return () => source.close();  // REQUIRED
}, [sessionId]);
```

### Rule ARCH-013: Pydantic models for all API request and response shapes
Every FastAPI endpoint must declare explicit Pydantic v2 `BaseModel` request and response types. No raw `dict` in route signatures. No `Response(content=json.dumps(...))` — use the Pydantic model as the return type.

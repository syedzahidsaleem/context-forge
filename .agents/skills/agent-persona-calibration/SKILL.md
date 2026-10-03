---
name: agent-persona-calibration
description: "Writing, calibrating, and testing the 6 swarm agent system prompts to ensure differentiated, non-generic BRD output. Use this skill when modifying backend/agents/prompts.py or when agent outputs feel too similar to each other."
version: 1.0
applies_to: ["backend/agents/prompts.py", "backend/agents/swarm.py"]
---

# Skill: Agent Persona Calibration

This skill defines the exact system prompts for all 6 swarm agents and provides the verification procedure to confirm that agents produce genuinely differentiated outputs. The single most common failure mode in multi-agent BRD systems is agent homogenisation — all agents produce nearly identical text despite different system prompts.

---

## Prerequisites & Dependencies

- `backend/agents/prompts.py` exists and is importable.
- A working Gemini Flash API key is configured in `.env`.
- `backend/agents/swarm.py` has the `run_agent()` function implemented.

---

## Step 1: Implement all 6 System Prompts in `agents/prompts.py`

Each prompt has four mandatory components:
1. **Role declaration** — who the agent is
2. **Lens instruction** — what lens they apply to the problem
3. **Output contract** — exact JSON structure they must produce
4. **Differentiation anchor** — one explicit thing that makes this agent unique and likely to disagree with others

```python
# backend/agents/prompts.py

"""
All system prompt constants for ContextForge agents.
These are immutable. Modifying a prompt changes the agent's output characteristics.
Run the calibration test (Step 4 of SKILL.md) after any change.
"""

from typing import Final

__all__ = [
    "VC_SYSTEM_PROMPT",
    "LEAN_SYSTEM_PROMPT",
    "CTO_SYSTEM_PROMPT",
    "UX_SYSTEM_PROMPT",
    "REGULATOR_SYSTEM_PROMPT",
    "ADVERSARIAL_SYSTEM_PROMPT",
    "EVALUATOR_SYSTEM_PROMPT",
    "MERGE_SYSTEM_PROMPT",
    "BRD_SECTIONS",
    "BRD_CRITERIA",
    "AGENT_NAMES",
]

BRD_SECTIONS: Final[list[str]] = [
    "problem_statement",
    "functional_requirements",
    "technical_requirements",
    "risk_register",
    "timeline_milestones",
]

BRD_CRITERIA: Final[list[str]] = [
    "feasibility",
    "market_timing",
    "regulatory_safety",
    "user_adoption",
    "competitive_moat",
]

AGENT_NAMES: Final[list[str]] = ["vc", "lean", "cto", "ux", "regulator", "adversarial"]

_OUTPUT_CONTRACT: Final[str] = """
Output ONLY a valid JSON object with exactly these keys. No markdown. No prose outside JSON.
{
  "problem_statement": "<your full section content as a string>",
  "functional_requirements": "<your full section content as a string>",
  "technical_requirements": "<your full section content as a string>",
  "risk_register": "<your full section content as a string>",
  "timeline_milestones": "<your full section content as a string>"
}
Each section must be a complete, standalone piece of text. Minimum 150 words per section.
"""

VC_SYSTEM_PROMPT: Final[str] = f"""
You are a Silicon Valley venture capitalist who has reviewed 2,000+ pitch decks. Your BRDs are written to maximise fundability.

YOUR LENS: Every requirement must serve the investor narrative. TAM comes first. Unit economics in every section. Network effects, defensible moats, and land-and-expand potential are your obsessions. If a feature doesn't help the business raise a Series A, question whether it belongs in the MVP.

YOUR DIFFERENTIATION ANCHOR: You will consistently push for larger market framing than any other agent. You will overweight growth metrics and underweight regulatory risk. Your timeline will be aggressive because investors reward speed.

When you see the real-world context data, use competitor funding rounds and market size figures directly in your BRD. Cite them.

{_OUTPUT_CONTRACT}
"""

LEAN_SYSTEM_PROMPT: Final[str] = f"""
You are a repeat founder who has built 3 startups on minimal budgets. Your BRDs are written to ship the fastest possible MVP with the least resources.

YOUR LENS: Ruthlessly cut scope. If something doesn't validate the core hypothesis in 4 weeks, it doesn't belong in this BRD. One user problem, one solution, one metric. You are allergic to premature scalability. A single Python script on a free tier is a valid architecture if it works.

YOUR DIFFERENTIATION ANCHOR: You will consistently push for a much smaller MVP scope than any other agent. You will cut features that the VC agent adds. Your technical requirements will be radically simpler than the CTO agent's. Your timeline will be the shortest of all 6 agents.

When you see context data, use it to validate that the problem is real — then propose the minimum viable solution to that specific problem.

{_OUTPUT_CONTRACT}
"""

CTO_SYSTEM_PROMPT: Final[str] = f"""
You are an enterprise CTO who has scaled systems to 50 million users. Your BRDs are written for production-grade, enterprise-ready systems.

YOUR LENS: Security, scalability, compliance, and architecture soundness are non-negotiable. You think in SLAs (99.9% uptime), data residency requirements, disaster recovery RPO/RTO targets, and API versioning strategies. You do not cut corners on infrastructure.

YOUR DIFFERENTIATION ANCHOR: You will consistently require a more robust technical foundation than any other agent. Where the lean founder says 'SQLite', you say 'PostgreSQL with read replicas'. Where the lean founder says 'deploy on a free tier', you say 'auto-scaling Kubernetes cluster'. Your timeline will be the longest of all 6 agents because you account for security review and load testing.

When you see context data, focus on regulatory compliance (data localisation, GDPR equivalents in the target region) and any technical precedents set by competitors.

{_OUTPUT_CONTRACT}
"""

UX_SYSTEM_PROMPT: Final[str] = f"""
You are a UX researcher with 12 years of user interviews across emerging markets. Your BRDs are written from the end user's perspective.

YOUR LENS: Every single requirement must trace back to a documented user pain point. If you cannot map a requirement to a real human behaviour you've observed or that the context data supports, you flag it as an assumption and recommend a validation experiment before building it.

YOUR DIFFERENTIATION ANCHOR: You will consistently question whether users actually have the problem the founder thinks they have. You will flag adoption risks that other agents ignore. You will identify cultural and linguistic barriers (language support, literacy levels, connectivity constraints) that no other agent mentions. You will recommend user research milestones before key development phases.

When you see context data, use World Bank literacy/connectivity data and cultural nuance summaries to identify adoption barriers. Use news data to understand how users in this region currently solve this problem.

{_OUTPUT_CONTRACT}
"""

REGULATOR_SYSTEM_PROMPT: Final[str] = f"""
You are a regulatory lawyer specialising in technology, data privacy, and fintech/healthtech in emerging markets. Your BRDs are written to survive legal and ethical scrutiny.

YOUR LENS: Every feature is a potential liability. Data collected = data regulated. You look for: applicable data protection laws (DPDP Act, GDPR equivalents, CCPA), sector-specific licensing requirements (FSSAI for food, RBI for fintech, CDSCO for health), cross-border data transfer restrictions, and consumer protection obligations.

YOUR DIFFERENTIATION ANCHOR: You are the only agent who will actively identify requirements that could make the product illegal in its target market. You flag mandatory features that the VC and lean founder will omit (consent management, data deletion flows, audit trails). Your risk register will be the longest and most specific of all 6 agents.

When you see context data, treat the regulatory flags list as your primary input. Cross-reference with news data for recent enforcement actions in this region and industry.

{_OUTPUT_CONTRACT}
"""

ADVERSARIAL_SYSTEM_PROMPT: Final[str] = f"""
You are the founder's most dangerous competitor — well-funded, technically superior, and already operating in this market. Your BRDs are written to expose every weakness an adversary could exploit.

YOUR LENS: Actively try to kill this idea. Your job is to write a BRD that documents every assumption that could be wrong, every market condition that could invalidate the thesis, and every technical weakness a competitor could use to undercut this product. You are not rooting for this idea to succeed.

YOUR DIFFERENTIATION ANCHOR: You will consistently identify fatal flaws that no other agent mentions. You will use competitor data from the context package to show where established players already own this space. You will identify the single biggest existential risk to the product and put it in the problem statement section, not buried in the risk register.

When you see context data, use Crunchbase competitor funding data aggressively. If a well-funded competitor exists in this space, name them, estimate their runway, and explain exactly how they will respond to this product entering the market.

{_OUTPUT_CONTRACT}
"""

EVALUATOR_SYSTEM_PROMPT: Final[str] = """
You are an objective BRD evaluator. You receive 6 BRDs written by different expert agents and real-world market context data.

Score each agent's BRD on each of these 5 sections:
- problem_statement, functional_requirements, technical_requirements, risk_register, timeline_milestones

For each section of each agent, score all 5 criteria (0–100):
- feasibility: Can this be built with stated resources/timeline?
- market_timing: Is the market ready? Does the context data support this?
- regulatory_safety: Does this survive legal/regulatory scrutiny in the stated region?
- user_adoption: Does this match real user behaviour evidenced in the context?
- competitive_moat: Is there a defensible advantage over existing players?

For every single score, provide one citation from the provided context package that justifies it.
High score = strong evidence from context. Low score = contradicted by context or missing evidence.

Output ONLY valid JSON with no prose outside the JSON object:
{
  "scores": {
    "<agent_name>": {
      "<section_name>": {
        "<criterion>": {
          "score": <number 0.0–100.0>,
          "citation": "<one sentence citing specific data>"
        }
      }
    }
  }
}
"""

MERGE_SYSTEM_PROMPT: Final[str] = """
You are a senior technical writer synthesising competing expert BRD sections into a single coherent document.

You receive pre-selected best sections — one per BRD section, from the highest-scoring agent for that section.
Your task:
1. Unify terminology across sections (the VC calls it "TAM", the regulator calls it "target population" — pick one and use it throughout).
2. Ensure section transitions are coherent (the functional requirements must reference the problem statement).
3. Preserve ALL factual content, requirements, and risk flags from each section. Do not add new requirements. Do not remove existing ones.
4. Improve sentence flow within each section without changing meaning.

Output ONLY valid JSON:
{
  "problem_statement": "<polished unified section text>",
  "functional_requirements": "<polished unified section text>",
  "technical_requirements": "<polished unified section text>",
  "risk_register": "<polished unified section text>",
  "timeline_milestones": "<polished unified section text>"
}
"""
```

---

## Step 2: Implement `run_swarm()` in `agents/swarm.py`

```python
import asyncio
import json
from typing import Any

import google.generativeai as genai

from config import settings
from key_pool import get_next_key
from agents.prompts import (
    VC_SYSTEM_PROMPT, LEAN_SYSTEM_PROMPT, CTO_SYSTEM_PROMPT,
    UX_SYSTEM_PROMPT, REGULATOR_SYSTEM_PROMPT, ADVERSARIAL_SYSTEM_PROMPT,
    AGENT_NAMES,
)
from gcp.storage import write_agent_output
from errors import AgentFailureError

__all__ = ["run_swarm", "AgentResult"]

from dataclasses import dataclass

@dataclass
class AgentResult:
    agent_name: str
    brd: dict[str, str]
    success: bool
    error: str | None = None

_AGENT_PROMPTS: dict[str, str] = {
    "vc": VC_SYSTEM_PROMPT,
    "lean": LEAN_SYSTEM_PROMPT,
    "cto": CTO_SYSTEM_PROMPT,
    "ux": UX_SYSTEM_PROMPT,
    "regulator": REGULATOR_SYSTEM_PROMPT,
    "adversarial": ADVERSARIAL_SYSTEM_PROMPT,
}

async def _run_single_agent(
    agent_name: str,
    system_prompt: str,
    intake_package: dict[str, Any],
) -> AgentResult:
    api_key = get_next_key()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=settings.GEMINI_FLASH_MODEL,
        system_instruction=system_prompt,
    )
    user_message = (
        f"Business Idea & Intake Summary:\n{json.dumps(intake_package['extracted'], indent=2)}\n\n"
        f"Real-World Context Package:\n{json.dumps(intake_package['context_package'], indent=2)}\n\n"
        f"Write the complete BRD for this business idea."
    )
    try:
        async with asyncio.timeout(settings.GEMINI_FLASH_TIMEOUT_SECONDS):
            response = await model.generate_content_async(user_message)
        brd_dict: dict[str, str] = json.loads(response.text)
        await write_agent_output(intake_package["session_id"], agent_name, brd_dict)
        return AgentResult(agent_name=agent_name, brd=brd_dict, success=True)
    except asyncio.TimeoutError:
        return AgentResult(agent_name=agent_name, brd={}, success=False, error="Timeout")
    except Exception as e:
        return AgentResult(agent_name=agent_name, brd={}, success=False, error=str(e))

async def run_swarm(intake_package: dict[str, Any]) -> list[AgentResult]:
    tasks = [
        _run_single_agent(name, prompt, intake_package)
        for name, prompt in _AGENT_PROMPTS.items()
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    results: list[AgentResult] = []
    for i, result in enumerate(raw_results):
        if isinstance(result, Exception):
            results.append(AgentResult(
                agent_name=AGENT_NAMES[i], brd={}, success=False, error=str(result)
            ))
        else:
            results.append(result)
    return results
```

---

## Step 3: Differentiation Quality Check

After implementing, run a single BRD generation with this demo idea and visually confirm agents disagree:

**Demo idea:** *"I want to build an app that helps small restaurants in India manage their inventory and reduce food waste using AI predictions."*

Check these divergence markers:
| Metric | What to look for |
|--------|-----------------|
| Tech stack choice | CTO says Kubernetes/PostgreSQL; Lean says FastAPI + SQLite |
| MVP scope | Lean cuts features; VC adds investor-facing analytics |
| Regulatory flags | Regulator mentions FSSAI; others may not |
| Market verdict | Adversarial names a funded competitor; VC expands TAM |
| Timeline | Lean: 4 weeks; CTO: 6 months |

---

## Step 4: Verification Test

```bash
cd backend
python -c "
import asyncio, os
os.environ.setdefault('APP_ENV', 'development')

async def test_prompt_diversity():
    from agents.prompts import (
        VC_SYSTEM_PROMPT, LEAN_SYSTEM_PROMPT, CTO_SYSTEM_PROMPT,
        UX_SYSTEM_PROMPT, REGULATOR_SYSTEM_PROMPT, ADVERSARIAL_SYSTEM_PROMPT,
        EVALUATOR_SYSTEM_PROMPT, MERGE_SYSTEM_PROMPT, BRD_SECTIONS, BRD_CRITERIA, AGENT_NAMES
    )
    # All prompts must be non-empty
    for name, prompt in [('VC', VC_SYSTEM_PROMPT), ('LEAN', LEAN_SYSTEM_PROMPT),
                          ('CTO', CTO_SYSTEM_PROMPT), ('UX', UX_SYSTEM_PROMPT),
                          ('REGULATOR', REGULATOR_SYSTEM_PROMPT), ('ADV', ADVERSARIAL_SYSTEM_PROMPT),
                          ('EVAL', EVALUATOR_SYSTEM_PROMPT), ('MERGE', MERGE_SYSTEM_PROMPT)]:
        assert len(prompt) > 200, f'{name} prompt too short — likely truncated'
        assert 'problem_statement' in prompt or name in ('EVAL', 'MERGE'), f'{name} missing section contract'
    # All BRD sections defined
    assert len(BRD_SECTIONS) == 5, f'Expected 5 sections, got {len(BRD_SECTIONS)}'
    assert len(BRD_CRITERIA) == 5, f'Expected 5 criteria, got {len(BRD_CRITERIA)}'
    assert len(AGENT_NAMES) == 6, f'Expected 6 agents, got {len(AGENT_NAMES)}'
    # Prompts are meaningfully different (no two should share > 60% of their tokens)
    prompts = [VC_SYSTEM_PROMPT, LEAN_SYSTEM_PROMPT, CTO_SYSTEM_PROMPT, UX_SYSTEM_PROMPT, REGULATOR_SYSTEM_PROMPT, ADVERSARIAL_SYSTEM_PROMPT]
    for i, p1 in enumerate(prompts):
        for j, p2 in enumerate(prompts):
            if i >= j: continue
            shared = len(set(p1.split()) & set(p2.split()))
            total = max(len(set(p1.split())), len(set(p2.split())))
            similarity = shared / total
            assert similarity < 0.6, f'Agents {AGENT_NAMES[i]} and {AGENT_NAMES[j]} prompts too similar ({similarity:.0%})'
    print('PASS: All prompt validation checks passed.')

asyncio.run(test_prompt_diversity())
"
```

**Expected:** `PASS: All prompt validation checks passed.`

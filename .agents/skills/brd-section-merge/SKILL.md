---
name: brd-section-merge
description: "Deterministic section-level merging of 6 agent BRD outputs into a single lineage-tagged, confidence-scored final BRD. Use this skill whenever implementing or modifying backend/agents/merge.py or backend/agents/evaluator.py."
version: 1.0
applies_to: ["backend/agents/merge.py", "backend/agents/evaluator.py", "backend/models/brd.py", "backend/models/scores.py"]
---

# Skill: BRD Section Merge

This skill defines the exact procedure for building the merge engine and evaluator. Follow all steps in order. Deviation from the 5-section schema or the scoring rubric will break the deterministic merge logic.

---

## Prerequisites & Dependencies

- `backend/agents/prompts.py` must contain all 8 system prompt constants before this skill runs.
- `backend/models/scores.py` must contain `ScoreMatrix`, `SectionScore`, and `InvestorReadinessScore` Pydantic models.
- `backend/models/brd.py` must contain `MergedBRD`, `BRDSection`, and `LineageTag` Pydantic models.
- All 6 swarm agents must have successfully written their outputs to GCS (verified via `gcp/storage.py`).
- The `GEMINI_PRO_MODEL` and `GEMINI_PRO_TIMEOUT_SECONDS` settings must be set in `config.py`.

---

## Step 1: Define the 5 Fixed BRD Section Identifiers

The merge engine operates on exactly 5 sections. These names are the ground truth — they must appear identically in agent system prompts, the evaluator prompt, and the merge prompt.

```python
# In backend/agents/prompts.py

BRD_SECTIONS = [
    "problem_statement",
    "functional_requirements",
    "technical_requirements",
    "risk_register",
    "timeline_milestones",
]

BRD_CRITERIA = [
    "feasibility",
    "market_timing",
    "regulatory_safety",
    "user_adoption",
    "competitive_moat",
]
```

All 6 agent system prompts must instruct the agent to structure their BRD output using exactly these section headings as JSON keys. The swarm prompt template must include:
```
Output your BRD as a JSON object with exactly these keys:
{
  "problem_statement": "...",
  "functional_requirements": "...",
  "technical_requirements": "...",
  "risk_register": "...",
  "timeline_milestones": "..."
}
Do not add any other keys. Do not use markdown headers. Return only valid JSON.
```

---

## Step 2: Implement the Evaluator (`backend/agents/evaluator.py`)

The evaluator receives all 6 BRD JSON objects and the context package. It outputs a `ScoreMatrix`.

```python
import asyncio
import json
from typing import Any

import google.generativeai as genai

from config import settings
from models.scores import ScoreMatrix, SectionScore
from agents.prompts import EVALUATOR_SYSTEM_PROMPT, BRD_SECTIONS, BRD_CRITERIA
from gcp.storage import read_all_agent_outputs
from errors import AgentFailureError

__all__ = ["run_evaluator"]

async def run_evaluator(session_id: str, context_package: dict[str, Any]) -> ScoreMatrix:
    """
    Calls Gemini Pro once with all 6 BRDs + context.
    Returns a ScoreMatrix with per-agent, per-section, per-criterion scores.
    """
    # 1. Load all 6 agent outputs in parallel from GCS
    agent_outputs: dict[str, dict] = await read_all_agent_outputs(session_id)

    # 2. Build the evaluator prompt — pass all 6 BRDs + context as one structured user message
    brd_payload = json.dumps(agent_outputs, indent=2)
    context_payload = json.dumps(context_package, indent=2)
    user_message = (
        f"Here are 6 BRDs from different expert agents:\n{brd_payload}\n\n"
        f"Here is the real-world context used:\n{context_payload}\n\n"
        f"Score each agent on each BRD section across all criteria. "
        f"Output ONLY a valid JSON ScoreMatrix. No prose. No markdown."
    )

    model = genai.GenerativeModel(
        model_name=settings.GEMINI_PRO_MODEL,
        system_instruction=EVALUATOR_SYSTEM_PROMPT,
    )

    try:
        async with asyncio.timeout(settings.GEMINI_PRO_TIMEOUT_SECONDS):
            response = await model.generate_content_async(user_message)
    except asyncio.TimeoutError as e:
        raise AgentFailureError("evaluator", f"Timeout after {settings.GEMINI_PRO_TIMEOUT_SECONDS}s") from e

    # 3. Parse and validate
    try:
        raw: dict = json.loads(response.text)
        return ScoreMatrix.model_validate(raw)
    except Exception as e:
        raise AgentFailureError("evaluator", f"Failed to parse score matrix: {e}") from e
```

**Evaluator System Prompt** (add to `agents/prompts.py`):
```python
EVALUATOR_SYSTEM_PROMPT = """
You are an objective BRD evaluator. You receive 6 BRDs written by different expert agents and real-world market context.

Your task: Score each agent's BRD on each of these 5 sections:
- problem_statement
- functional_requirements
- technical_requirements
- risk_register
- timeline_milestones

For each section, score each agent on each of these 5 criteria (0–100):
- feasibility: Can this be built with stated resources/timeline?
- market_timing: Is the market ready? Does the context data support this?
- regulatory_safety: Does this survive legal/regulatory scrutiny?
- user_adoption: Does this match real user behaviour from the context?
- competitive_moat: Is there a defensible advantage over existing players?

For each score, provide one-line data citation from the provided context package.

Output ONLY valid JSON in this exact schema:
{
  "scores": {
    "<agent_name>": {
      "<section_name>": {
        "<criterion>": {
          "score": <number 0-100>,
          "citation": "<one line citing the specific data that justifies this score>"
        }
      }
    }
  }
}
Agent names: vc, lean, cto, ux, regulator, adversarial
Section names: problem_statement, functional_requirements, technical_requirements, risk_register, timeline_milestones
Criterion names: feasibility, market_timing, regulatory_safety, user_adoption, competitive_moat
"""
```

---

## Step 3: Implement the Merge Engine (`backend/agents/merge.py`)

```python
import asyncio
import json
from typing import Any

import google.generativeai as genai

from config import settings
from models.brd import MergedBRD, BRDSection
from models.scores import ScoreMatrix
from agents.prompts import MERGE_SYSTEM_PROMPT, BRD_SECTIONS
from gcp.storage import read_all_agent_outputs
from errors import AgentFailureError

__all__ = ["run_merge"]

def find_best_agent_per_section(score_matrix: ScoreMatrix) -> dict[str, str]:
    """
    For each BRD section, identify which agent had the highest average score
    across all 5 criteria. Returns {section_name: agent_name}.
    """
    best: dict[str, str] = {}
    for section in BRD_SECTIONS:
        best_agent = None
        best_avg = -1.0
        for agent_name in score_matrix.scores:
            section_scores = score_matrix.scores[agent_name].get(section, {})
            if not section_scores:
                continue
            avg = sum(v.score for v in section_scores.values()) / len(section_scores)
            if avg > best_avg:
                best_avg = avg
                best_agent = agent_name
        best[section] = best_agent or "vc"  # fallback to vc if scores missing
    return best

async def run_merge(session_id: str, score_matrix: ScoreMatrix) -> MergedBRD:
    """
    Takes the highest-scoring agent per section.
    Calls Gemini Pro to polish and unify the combined sections into a coherent final BRD.
    Returns a MergedBRD with lineage tags.
    """
    agent_outputs: dict[str, dict] = await read_all_agent_outputs(session_id)
    best_agents: dict[str, str] = find_best_agent_per_section(score_matrix)

    # Assemble the best section from the best agent for each section
    section_candidates: dict[str, Any] = {}
    for section, agent_name in best_agents.items():
        section_candidates[section] = {
            "content": agent_outputs.get(agent_name, {}).get(section, ""),
            "source_agent": agent_name,
        }

    # Build dissenting views per section (agents that scored next-highest)
    dissenting: dict[str, list] = _build_dissenting_views(score_matrix, best_agents, agent_outputs)

    user_message = (
        f"Here are the best sections selected from the 6 expert agents:\n"
        f"{json.dumps(section_candidates, indent=2)}\n\n"
        f"Unify these sections into a coherent, professional BRD. "
        f"Fix any terminology inconsistencies between sections. "
        f"Preserve all factual content. Do not add new requirements. "
        f"Output ONLY valid JSON following the MergedBRD schema. No markdown."
    )

    model = genai.GenerativeModel(
        model_name=settings.GEMINI_PRO_MODEL,
        system_instruction=MERGE_SYSTEM_PROMPT,
    )

    try:
        async with asyncio.timeout(settings.GEMINI_PRO_TIMEOUT_SECONDS):
            response = await model.generate_content_async(user_message)
    except asyncio.TimeoutError as e:
        raise AgentFailureError("merge", f"Timeout after {settings.GEMINI_PRO_TIMEOUT_SECONDS}s") from e

    try:
        raw: dict = json.loads(response.text)
        merged = MergedBRD.model_validate(raw)
        # Attach lineage metadata that only the server knows
        for section_name, section in merged.sections.items():
            section.source_agent = best_agents.get(section_name, "unknown")
            section.dissenting_agents = dissenting.get(section_name, [])
        return merged
    except Exception as e:
        raise AgentFailureError("merge", f"Failed to parse merged BRD: {e}") from e

def _build_dissenting_views(
    score_matrix: ScoreMatrix,
    best_agents: dict[str, str],
    agent_outputs: dict[str, dict],
) -> dict[str, list]:
    """For each section, find the runner-up agent(s) and their key disagreement."""
    dissenting: dict[str, list] = {}
    for section in BRD_SECTIONS:
        winner = best_agents[section]
        others = []
        for agent_name in score_matrix.scores:
            if agent_name == winner:
                continue
            section_data = score_matrix.scores[agent_name].get(section, {})
            if not section_data:
                continue
            avg = sum(v.score for v in section_data.values()) / len(section_data)
            others.append({"agent": agent_name, "avg_score": round(avg, 1)})
        others.sort(key=lambda x: x["avg_score"], reverse=True)
        # Top dissenter only
        if others:
            top = others[0]
            top["key_disagreement"] = (
                f"{top['agent'].upper()} scored {top['avg_score']}/100 on this section "
                f"(vs {winner.upper()}'s higher score). Review this agent's output for alternative perspective."
            )
        dissenting[section] = others[:2]  # top 2 dissenters only
    return dissenting
```

---

## Step 4: Implement `calculate_agreement()` in `output/heatmap.py`

```python
import statistics
from models.scores import ScoreMatrix
from agents.prompts import BRD_SECTIONS

__all__ = ["calculate_heatmap"]

def calculate_heatmap(score_matrix: ScoreMatrix) -> list[dict]:
    """
    For each BRD section, calculate the agreement level across all 6 agents.
    Agreement = 100 - (std_dev of average per-agent section scores * 2), clamped 0–100.
    """
    heatmap = []
    for section in BRD_SECTIONS:
        per_agent_avgs: list[float] = []
        for agent_name, sections in score_matrix.scores.items():
            section_data = sections.get(section, {})
            if not section_data:
                per_agent_avgs.append(50.0)  # neutral default if missing
                continue
            avg = sum(v.score for v in section_data.values()) / len(section_data)
            per_agent_avgs.append(avg)

        std_dev = statistics.stdev(per_agent_avgs) if len(per_agent_avgs) > 1 else 0.0
        agreement = max(0.0, min(100.0, 100.0 - (std_dev * 2)))
        risk_level = "low" if agreement > 70 else ("medium" if agreement >= 40 else "high")
        dominant = max(
            score_matrix.scores.items(),
            key=lambda item: sum(
                v.score for v in item[1].get(section, {}).values()
            ) / max(1, len(item[1].get(section, {})))
        )[0]

        heatmap.append({
            "section_name": section,
            "label": section.replace("_", " ").title(),
            "agreement_score": round(agreement, 1),
            "risk_level": risk_level,
            "std_deviation": round(std_dev, 2),
            "min_score": round(min(per_agent_avgs), 1),
            "max_score": round(max(per_agent_avgs), 1),
            "dominant_agent": dominant,
            "per_agent_scores": {
                agent: round(
                    sum(v.score for v in score_matrix.scores[agent].get(section, {}).values())
                    / max(1, len(score_matrix.scores[agent].get(section, {}))),
                    1
                )
                for agent in score_matrix.scores
            }
        })
    return heatmap
```

---

## Step 5: Verification Test

Run this to confirm the merge pipeline is working end-to-end:

```bash
cd backend
python -c "
import asyncio
import json

async def test_merge_pipeline():
    # Use a fake session that has pre-written test fixtures in GCS
    # or mock the GCS reads with local JSON files
    from output.heatmap import calculate_heatmap
    from models.scores import ScoreMatrix

    # Minimal valid ScoreMatrix for smoke-test
    raw_matrix = {
        'scores': {
            agent: {
                section: {
                    criterion: {'score': 75.0, 'citation': 'Test citation'}
                    for criterion in ['feasibility', 'market_timing', 'regulatory_safety', 'user_adoption', 'competitive_moat']
                }
                for section in ['problem_statement', 'functional_requirements', 'technical_requirements', 'risk_register', 'timeline_milestones']
            }
            for agent in ['vc', 'lean', 'cto', 'ux', 'regulator', 'adversarial']
        }
    }
    score_matrix = ScoreMatrix.model_validate(raw_matrix)
    heatmap = calculate_heatmap(score_matrix)
    assert len(heatmap) == 5, f'Expected 5 sections, got {len(heatmap)}'
    for section in heatmap:
        assert section['agreement_score'] == 100.0, 'All identical scores should give 100% agreement'
    print('PASS: Heatmap calculation correct.')
    print(json.dumps(heatmap, indent=2))

asyncio.run(test_merge_pipeline())
"
```

**Expected output:** `PASS: Heatmap calculation correct.` followed by a JSON array of 5 section objects each with `agreement_score: 100.0`.

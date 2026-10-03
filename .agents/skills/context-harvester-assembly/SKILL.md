---
name: context-harvester-assembly
description: "Implementing and wiring the Context Harvester: the parallel async pipeline that pulls live market data the moment region and industry are detected in the conversational intake. Use when implementing or debugging backend/context/harvester.py or any of its sub-modules."
version: 1.0
applies_to: ["backend/context/harvester.py", "backend/context/newsapi.py", "backend/context/worldbank.py", "backend/context/grounding.py", "backend/intake/conversation.py"]
---

# Skill: Context Harvester Assembly

The Context Harvester is ContextForge's primary differentiator. This skill walks through building all 5 context sources and wiring them into a single parallel async pipeline that fires the moment region detection is confirmed.

---

## Prerequisites & Dependencies

- `NEWS_API_KEY` and `WORLDBANK_API_BASE_URL` set in `.env`.
- `CONTEXT_HARVESTER_TIMEOUT_SECONDS` set in `.env` (default: 10).
- `httpx` installed and available (`import httpx`).
- `config.py` exports `settings.NEWS_API_KEY`, `settings.WORLDBANK_API_BASE_URL`, `settings.CONTEXT_HARVESTER_TIMEOUT_SECONDS`.
- Security rule SEC-013 (SSRF whitelist) enforced before calling this skill.

---

## Step 1: Implement NewsAPI Client (`context/newsapi.py`)

```python
import httpx
from config import settings
from errors import ContextHarvestError

__all__ = ["fetch_news"]

async def fetch_news(region: str, industry: str) -> list[dict]:
    """
    Fetch last 30 days of news for the given region + industry.
    Returns list of {headline, date, source, url} dicts.
    Max 5 articles returned to keep context package concise.
    """
    params = {
        "q": industry,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": 5,
        "apiKey": settings.NEWS_API_KEY,
    }
    # Add country only if it's a supported NewsAPI country code
    # NewsAPI uses ISO 3166-1 alpha-2 but not all countries are supported
    NEWSAPI_SUPPORTED_COUNTRIES = frozenset({
        "ae", "ar", "at", "au", "be", "bg", "br", "ca", "ch", "cn",
        "co", "cu", "cz", "de", "eg", "fr", "gb", "gr", "hk", "hu",
        "id", "ie", "il", "in", "it", "jp", "kr", "lt", "lv", "ma",
        "mx", "my", "ng", "nl", "no", "nz", "ph", "pl", "pt", "ro",
        "rs", "ru", "sa", "se", "sg", "si", "sk", "th", "tr", "tw",
        "ua", "us", "ve", "za",
    })
    if region.lower() in NEWSAPI_SUPPORTED_COUNTRIES:
        params["country"] = region.lower()

    try:
        async with httpx.AsyncClient(timeout=settings.CONTEXT_HARVESTER_TIMEOUT_SECONDS) as client:
            response = await client.get("https://newsapi.org/v2/top-headlines", params=params)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            return [
                {
                    "headline": a.get("title", ""),
                    "date": a.get("publishedAt", "")[:10],
                    "source": a.get("source", {}).get("name", ""),
                    "url": a.get("url", ""),
                }
                for a in articles[:5]
            ]
    except httpx.TimeoutException as e:
        raise ContextHarvestError("newsapi", f"Timeout after {settings.CONTEXT_HARVESTER_TIMEOUT_SECONDS}s") from e
    except httpx.HTTPStatusError as e:
        raise ContextHarvestError("newsapi", f"HTTP {e.response.status_code}") from e
```

---

## Step 2: Implement World Bank API Client (`context/worldbank.py`)

```python
import httpx
from config import settings
from errors import ContextHarvestError

__all__ = ["fetch_market_data"]

# World Bank indicator codes used by ContextForge
_WB_INDICATORS = {
    "gdp_usd": "NY.GDP.MKTP.CD",           # GDP (current USD)
    "ease_of_business_rank": "IC.BUS.EASE.XQ", # Ease of doing business rank
    "inflation_pct": "FP.CPI.TOTL.ZG",     # Inflation (consumer prices %)
    "fdi_inflow_usd": "BX.KLT.DINV.CD.WD", # FDI net inflows (USD)
    "internet_users_pct": "IT.NET.USER.ZS", # Internet users (% of population)
}

async def fetch_market_data(region: str) -> dict:
    """
    Fetch key economic indicators for the given country from World Bank API.
    Returns dict with indicator names as keys and latest available values.
    World Bank API is completely free and requires no API key.
    """
    results: dict = {}
    base_url = settings.WORLDBANK_API_BASE_URL  # https://api.worldbank.org/v2

    async with httpx.AsyncClient(timeout=settings.CONTEXT_HARVESTER_TIMEOUT_SECONDS) as client:
        for key, indicator_code in _WB_INDICATORS.items():
            url = f"{base_url}/country/{region.upper()}/indicator/{indicator_code}"
            params = {"format": "json", "mrv": 1, "per_page": 1}  # mrv=1: most recent value
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                # World Bank response is [metadata, [data_points]]
                if len(data) >= 2 and data[1] and data[1][0].get("value") is not None:
                    results[key] = round(float(data[1][0]["value"]), 2)
                else:
                    results[key] = None  # Indicator not available for this country
            except (httpx.TimeoutException, httpx.HTTPStatusError, IndexError, KeyError, ValueError):
                results[key] = None  # Non-fatal: missing indicator is acceptable

    return results
```

---

## Step 3: Implement Gemini Search Grounding (`context/grounding.py`)

```python
import google.generativeai as genai
from config import settings
from key_pool import get_next_key
from errors import ContextHarvestError
import asyncio

__all__ = ["fetch_grounding_context"]

async def fetch_grounding_context(region: str, industry: str, business_idea: str) -> str:
    """
    Uses Gemini with Google Search Grounding to gather cultural, seasonal,
    and social context for the target market.
    Returns a free-text summary string.
    """
    api_key = get_next_key()
    genai.configure(api_key=api_key)

    # Enable Google Search Grounding via tools
    search_tool = genai.protos.Tool(
        google_search_retrieval=genai.protos.GoogleSearchRetrieval()
    )

    model = genai.GenerativeModel(
        model_name=settings.GEMINI_FLASH_MODEL,
        tools=[search_tool],
    )

    prompt = (
        f"For the country '{region}' and industry '{industry}', provide a brief summary of:\n"
        f"1. Cultural nuances relevant to this business idea: {business_idea}\n"
        f"2. Religious or seasonal considerations affecting this market\n"
        f"3. Social sensitivities or viral trends in this region\n"
        f"4. Consumer trust signals in this country for this industry\n"
        f"Be specific, cite current facts, and keep the response under 300 words."
    )

    try:
        async with asyncio.timeout(settings.CONTEXT_HARVESTER_TIMEOUT_SECONDS):
            response = await model.generate_content_async(prompt)
            return response.text
    except asyncio.TimeoutError as e:
        raise ContextHarvestError("gemini_grounding", "Timeout") from e
    except Exception as e:
        raise ContextHarvestError("gemini_grounding", str(e)) from e
```

---

## Step 4: Implement the Harvester Orchestrator (`context/harvester.py`)

```python
import asyncio
import logging
from typing import Any

from context.newsapi import fetch_news
from context.worldbank import fetch_market_data
from context.grounding import fetch_grounding_context
from errors import ContextHarvestError

logger = logging.getLogger(__name__)

__all__ = ["harvest_context"]

async def harvest_context(
    region: str,
    industry: str,
    business_idea: str,
    session_id: str,
) -> dict[str, Any]:
    """
    Fire all context sources in parallel.
    Returns the complete context_package dict.
    Individual source failures are handled gracefully — a failed source
    returns an empty/null value rather than crashing the whole harvest.
    """
    results = await asyncio.gather(
        _safe_harvest("newsapi", fetch_news(region, industry)),
        _safe_harvest("worldbank", fetch_market_data(region)),
        _safe_harvest("grounding", fetch_grounding_context(region, industry, business_idea)),
        return_exceptions=False,  # _safe_harvest never raises; exceptions become None
    )

    news, market, cultural = results

    context_package: dict[str, Any] = {
        "news": news or [],
        "market": market or {},
        "competitors": [],        # Crunchbase: populated if API key present (see crunchbase.py)
        "regulatory": [],         # Govt Open Data: populated per-country (extension point)
        "cultural": cultural or "Cultural context data unavailable.",
        "image_analyses": [],     # Populated by intake/vision.py after file processing
        "document_summaries": [], # Populated by intake/documents.py after file processing
    }

    logger.info(
        "Context harvest complete",
        extra={
            "session_id": session_id,
            "news_count": len(context_package["news"]),
            "market_keys": list(context_package["market"].keys()),
            "cultural_length": len(context_package["cultural"]),
        }
    )
    return context_package

async def _safe_harvest(source_name: str, coro) -> Any:
    """
    Wraps a context harvest coroutine to catch all exceptions.
    Returns None on failure and logs a warning.
    """
    try:
        return await coro
    except ContextHarvestError as e:
        logger.warning(f"Context harvest partial failure: {source_name} — {e.message}")
        return None
    except Exception as e:
        logger.warning(f"Context harvest unexpected error: {source_name} — {e}")
        return None
```

---

## Step 5: Wire into Conversational Intake

In `intake/conversation.py`, detect when `region` is extracted and trigger harvesting:

```python
# In intake/conversation.py — add to the region-detection handler

async def on_region_detected(session: Session, region: str, industry: str, business_idea: str) -> None:
    """Called the moment region is confirmed in the conversation. Fires harvest in background."""
    import asyncio
    from context.harvester import harvest_context
    from gcp.bigquery import log_harvest_start

    # Fire harvest as a background task — does NOT block the conversation
    asyncio.create_task(
        _harvest_and_store(session.session_id, region, industry, business_idea)
    )

async def _harvest_and_store(session_id: str, region: str, industry: str, business_idea: str) -> None:
    """Background task: harvest context, store in session state for swarm."""
    from context.harvester import harvest_context
    from session_store import update_session_context

    context_package = await harvest_context(region, industry, business_idea, session_id)
    await update_session_context(session_id, context_package)
```

---

## Step 6: Verification Test

```bash
cd backend
python -c "
import asyncio, os
os.environ.setdefault('WORLDBANK_API_BASE_URL', 'https://api.worldbank.org/v2')
os.environ.setdefault('CONTEXT_HARVESTER_TIMEOUT_SECONDS', '15')
os.environ.setdefault('NEWS_API_KEY', 'test_placeholder')  # World Bank test does not need this

async def test_worldbank():
    from context.worldbank import fetch_market_data
    data = await fetch_market_data('IN')  # India
    print('World Bank data for India:', data)
    assert isinstance(data, dict), 'Expected dict'
    assert 'gdp_usd' in data, 'Expected gdp_usd key'
    print('PASS: World Bank API reachable and returning data.')

asyncio.run(test_worldbank())
"
```

**Expected:** GDP data for India printed, followed by `PASS: World Bank API reachable and returning data.`

Also verify the parallel timing:
```bash
python -c "
import asyncio, time

async def test_harvest_parallelism():
    # Simulate 3 tasks that each take 2 seconds
    async def slow_task(n):
        await asyncio.sleep(2)
        return n

    start = time.time()
    results = await asyncio.gather(slow_task(1), slow_task(2), slow_task(3))
    elapsed = time.time() - start
    assert elapsed < 3.0, f'Tasks ran serially! Took {elapsed:.1f}s instead of ~2s'
    print(f'PASS: 3x 2s tasks completed in {elapsed:.1f}s (parallel as expected).')

asyncio.run(test_harvest_parallelism())
"
```

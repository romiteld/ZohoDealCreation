import os
import logging
from typing import Dict, List, Tuple, Any
from openai import AsyncOpenAI
import asyncio

logger = logging.getLogger(__name__)

# Read from environment (Azure Container Apps runtime)
VOIT_BUDGET = float(os.getenv("VOIT_BUDGET", "5.0"))
TARGET_QUALITY = float(os.getenv("TARGET_QUALITY", "0.9"))
VOIT_LAM = float(os.getenv("VOIT_LAM", "0.3"))
VOIT_MU = float(os.getenv("VOIT_MU", "0.2"))

# Model cost mapping (relative units)
MODEL_COSTS = {
    "gpt-5-nano": 0.5,
    "gpt-5-mini": 1.0,
    "gpt-5": 3.5
}

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _voi(qgain: float, cost: float, latency: float, lam: float = VOIT_LAM, mu: float = VOIT_MU) -> float:
    """Calculate Value of Insight."""
    return qgain - lam*cost - mu*latency

async def call_llm(model: str, span: dict) -> Tuple[str, float]:
    """Call LLM for span processing."""
    try:
        # Map model tier
        model_name = {"mini": "gpt-5-mini", "large": "gpt-5"}.get(model, "gpt-5-nano")
        
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Process this span with high quality."},
                {"role": "user", "content": span.get("cached_text", "")}
            ],
            temperature=1.0,
            max_tokens=500
        )
        
        return response.choices[0].message.content, MODEL_COSTS.get(model_name, 1.0)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return span.get("cached_text", ""), 0.0

async def call_tool(span: dict) -> Tuple[str, float]:
    """Call external tool for span enrichment."""
    # Placeholder for Firecrawl or other tool integration
    await asyncio.sleep(0.1)  # Simulate tool call
    return span.get("cached_text", "") + " [tool-enriched]", 1.8

def assemble(spans: List[dict]) -> dict:
    """Assemble processed spans into final artifact."""
    return {
        "assembled": True,
        "spans": [{"id": s["id"], "text": s.get("text", ""), "quality": s.get("quality", 0)}
                 for s in spans],
        "total_quality": sum(s.get("quality", 0) for s in spans) / max(len(spans), 1)
    }

def voit_controller(artifact_ctx: dict, target_quality: float = TARGET_QUALITY, 
                   total_budget: float = VOIT_BUDGET, lam: float = VOIT_LAM, mu: float = VOIT_MU) -> dict:
    """
    VoIT controller for span-level reasoning depth allocation.
    artifact_ctx = { spans:[{id, quality, cached_text, ctx:{retrieval_dispersion, rule_conflicts, c3_margin, needs_fact_check}}] }
    """
    if not os.getenv("FEATURE_VOIT", "false").lower() == "true":
        logger.info("VoIT disabled - returning assembled spans")
        return assemble(artifact_ctx.get("spans", []))
    
    spans = artifact_ctx.get("spans", [])
    
    # Sort spans by priority (highest uncertainty first)
    spans.sort(key=lambda s: (
        s.get("ctx", {}).get("retrieval_dispersion", 0) + 
        s.get("ctx", {}).get("rule_conflicts", 0) + 
        s.get("ctx", {}).get("c3_margin", 0)
    ), reverse=True)
    
    # Process each span with budget constraint
    for s in spans:
        if total_budget <= 0 or s.get("quality", 0) >= target_quality:
            continue
        
        # Evaluate action candidates
        candidates = [
            ("reuse", s.get("cached_text", ""), 0.01, 0.0, 0.0),
            ("small", asyncio.run(call_llm("mini", s))[0], 0.15, 1.0, 1.0),
            ("tool",  asyncio.run(call_tool(s))[0], 0.22, 1.8, 1.2),
            ("deep",  asyncio.run(call_llm("large", s))[0], 0.30, 3.5, 2.0),
        ]
        
        # Select action with highest VOI
        name, text, qgain, cost, lat = max(candidates, key=lambda c: _voi(c[2], c[3], c[4], lam, mu))
        
        if cost <= total_budget:
            logger.info(f"VoIT: Applying {name} to span {s.get('id')} (cost={cost:.2f})")
            total_budget -= cost
            s["text"] = text
            s["quality"] = min(1.0, s.get("quality", 0) + qgain)
            s["action_taken"] = name
    
    return assemble(spans)
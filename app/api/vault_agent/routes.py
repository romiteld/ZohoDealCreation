from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import hashlib
import json
import time
import uuid
import os
import logging
from app.cache.c3 import C3Entry, DependencyCertificate, c3_reuse_or_rebuild, update_calibration, generate_cache_key
from app.cache.redis_io import load_c3_entry, save_c3_entry
from app.orchestrator.voit import voit_controller
from app.redis_cache_manager import get_cache_manager
from app.models import ExtractedData
import numpy as np

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vault-agent", tags=["vault-agent"])

# Import API key verification
from app.auth import verify_api_key

class IngestRequest(BaseModel):
    source: str                      # "email" | "resume" | "transcript" | "web"
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = {}

class PublishRequest(BaseModel):
    locator: str
    channels: List[str]              # ["zoho","email","jd_alignment","portal_card"]

async def generate_embedding(text: str) -> List[float]:
    """Generate text embedding (placeholder - implement with OpenAI/sentence-transformers)."""
    # Simple hash-based pseudo-embedding for now
    hash_val = hashlib.sha256(text.encode()).hexdigest()
    return [float(int(hash_val[i:i+2], 16))/255 for i in range(0, min(64, len(hash_val)), 2)]

async def normalize_payload(source: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize payload into canonical record format."""
    canonical = {
        "source": source,
        "timestamp": time.time(),
        "fields": {}
    }
    
    if source == "email":
        canonical["fields"] = {
            "candidate_name": payload.get("candidate_name"),
            "job_title": payload.get("job_title"),
            "location": payload.get("location"),
            "company_name": payload.get("company_name"),
            "referrer_name": payload.get("referrer_name"),
            "email": payload.get("email"),
            "template_version": payload.get("template_version", "v1"),
            "role_family": payload.get("role_family", "unknown"),
            "geo": payload.get("location", "").split(",")[0] if payload.get("location") else "unknown",
            "comp_policy": payload.get("comp_policy", "standard")
        }
        text = f"{payload.get('subject', '')} {payload.get('body', '')}"
    else:
        canonical["fields"] = payload
        text = json.dumps(payload)
    
    # Add embedding
    canonical["embed"] = await generate_embedding(text)
    canonical["text"] = text[:1000]  # Store sample text
    
    return canonical

@router.post("/ingest", dependencies=[Depends(verify_api_key)])
async def ingest_record(request: IngestRequest) -> Dict[str, str]:
    """
    Ingest data from various sources and create canonical record.
    normalize → canonical record + embeddings → store in Redis → return locator
    """
    try:
        # Normalize to canonical format
        canonical = await normalize_payload(request.source, request.payload)
        canonical["metadata"] = request.metadata
        
        # Generate unique locator
        locator = f"VAULT-{uuid.uuid4()}"
        
        # Get Redis client
        cache_mgr = get_cache_manager()
        if cache_mgr and cache_mgr.redis_client:
            # Store canonical record
            key = f"vault:record:{locator}"
            await cache_mgr.redis_client.hset(
                key,
                mapping={
                    "canonical": json.dumps(canonical),
                    "source": request.source,
                    "created_at": str(time.time())
                }
            )
            await cache_mgr.redis_client.expire(key, 86400 * 7)  # 7 day TTL
            
            logger.info(f"Ingested record: {locator} from source: {request.source}")
        
        return {"locator": locator, "status": "ingested"}
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/publish", dependencies=[Depends(verify_api_key)])
async def publish_record(request: PublishRequest) -> Dict[str, Any]:
    """
    Publish canonical record to specified channels.
    fetch → C³ reuse-or-rebuild → VoIT allocate → return output summaries
    """
    try:
        cache_mgr = get_cache_manager()
        if not cache_mgr or not cache_mgr.redis_client:
            raise HTTPException(status_code=503, detail="Cache service unavailable")
        
        # Fetch canonical record
        key = f"vault:record:{request.locator}"
        record_data = await cache_mgr.redis_client.hgetall(key)
        
        if not record_data:
            raise HTTPException(status_code=404, detail=f"Record not found: {request.locator}")
        
        canonical = json.loads(record_data.get(b"canonical", b"{}").decode())
        
        # Generate cache key for C³
        cache_key = generate_cache_key(
            canonical,
            client="default",
            channel=request.channels[0] if request.channels else "email"
        )
        
        # Try C³ cache if enabled
        artifact = None
        if os.getenv("FEATURE_C3", "false").lower() == "true":
            entry = await load_c3_entry(cache_mgr.redis_client, cache_key)
            
            if entry:
                # C³ gate decision
                req_context = {
                    "embed": canonical.get("embed", []),
                    "fields": canonical.get("fields", {}),
                    "touched_selectors": []  # Could be populated from UI interactions
                }
                
                delta = float(os.getenv("C3_DELTA", "0.01"))
                eps = int(os.getenv("C3_EPS", "3"))
                
                mode, payload = c3_reuse_or_rebuild(req_context, entry, delta, eps)
                
                if mode == "reuse":
                    artifact = json.loads(entry.artifact.decode())
                    logger.info(f"C³ cache hit for {request.locator}")
                else:
                    # Selective rebuild needed
                    logger.info(f"C³ selective rebuild for {request.locator}: {len(payload)} spans")
        
        # If no cache hit or C³ disabled, generate new
        if not artifact:
            # Prepare artifact context for VoIT
            artifact_ctx = {
                "spans": [
                    {
                        "id": f"span_{i}",
                        "quality": 0.5,
                        "cached_text": canonical.get("text", ""),
                        "ctx": {
                            "retrieval_dispersion": 0.2,
                            "rule_conflicts": 0.1,
                            "c3_margin": 0.3,
                            "needs_fact_check": i % 2 == 0
                        }
                    }
                    for i in range(min(3, len(request.channels)))
                ]
            }
            
            # Apply VoIT if enabled
            if os.getenv("FEATURE_VOIT", "false").lower() == "true":
                artifact = voit_controller(artifact_ctx)
            else:
                artifact = {"assembled": True, "spans": artifact_ctx["spans"]}
            
            # Save to C³ cache for future
            if os.getenv("FEATURE_C3", "false").lower() == "true":
                new_entry = C3Entry(
                    artifact=json.dumps(artifact).encode(),
                    dc=DependencyCertificate(spans={}, invariants={}),
                    probes={},
                    calib_scores=[],
                    tau_delta=1e9,
                    meta={
                        "embed": canonical.get("embed", []),
                        "fields": canonical.get("fields", {}),
                        "created_at": time.time(),
                        "template_version": "v1"
                    }
                )
                await save_c3_entry(cache_mgr.redis_client, cache_key, new_entry)
        
        # Generate channel-specific summaries
        summaries = {}
        for channel in request.channels:
            if channel == "email":
                summaries[channel] = f"<html><body><h2>Deal Summary</h2><pre>{json.dumps(canonical.get('fields', {}), indent=2)}</pre></body></html>"
            elif channel == "zoho":
                summaries[channel] = {"deal": canonical.get("fields", {})}
            elif channel == "jd_alignment":
                summaries[channel] = {"alignment_score": 0.85, "matched_skills": ["Python", "FastAPI"]}
            else:
                summaries[channel] = canonical.get("fields", {})
        
        return {
            "published": request.channels,
            "summaries": summaries,
            "cache_status": "hit" if artifact and os.getenv("FEATURE_C3") == "true" else "miss",
            "voit_applied": os.getenv("FEATURE_VOIT") == "true"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publishing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", dependencies=[Depends(verify_api_key)])
async def vault_status() -> Dict[str, Any]:
    """Get Vault Agent status and configuration."""
    return {
        "status": "operational",
        "features": {
            "c3_enabled": os.getenv("FEATURE_C3", "false").lower() == "true",
            "voit_enabled": os.getenv("FEATURE_VOIT", "false").lower() == "true",
            "c3_delta": float(os.getenv("C3_DELTA", "0.01")),
            "c3_eps": int(os.getenv("C3_EPS", "3")),
            "voit_budget": float(os.getenv("VOIT_BUDGET", "5.0")),
            "target_quality": float(os.getenv("TARGET_QUALITY", "0.9"))
        }
    }
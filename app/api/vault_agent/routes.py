from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, List, Optional
import hashlib
import json
import time
import uuid
import os
import logging
from well_shared.cache.c3 import C3Entry, DependencyCertificate, c3_reuse_or_rebuild, update_calibration, generate_cache_key
from app.cache.redis_io import load_c3_entry, save_c3_entry
from app.orchestrator.voit import voit_controller
from well_shared.cache.redis_manager import get_cache_manager
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

class EmailSpec(BaseModel):
    to: List[EmailStr]
    subject: Optional[str] = "TalentWell – Candidate Alert"

class PublishRequest(BaseModel):
    locator: str
    channels: List[str]              # ["zoho_crm","email_campaign","jd_alignment","portal_card"]
    email: Optional[EmailSpec] = None

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
        cache_mgr = await get_cache_manager()
        if cache_mgr and cache_mgr.client:
            # Store canonical record
            key = f"vault:record:{locator}"
            await cache_mgr.client.hset(
                key,
                mapping={
                    "canonical": json.dumps(canonical),
                    "source": request.source,
                    "created_at": str(time.time())
                }
            )
            await cache_mgr.client.expire(key, 86400 * 7)  # 7 day TTL
            
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
        cache_mgr = await get_cache_manager()
        if not cache_mgr or not cache_mgr.client:
            raise HTTPException(status_code=503, detail="Cache service unavailable")

        # Fetch canonical record
        key = f"vault:record:{request.locator}"
        record_data = await cache_mgr.client.hgetall(key)
        
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
            entry = await load_c3_entry(cache_mgr.client, cache_key)
            
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
                await save_c3_entry(cache_mgr.client, cache_key, new_entry)
        
        # Generate channel-specific results
        results = {}
        for channel in request.channels:
            if channel == "email_campaign":
                # Handle email campaign channel
                if not request.email or not request.email.to:
                    raise HTTPException(
                        status_code=422, 
                        detail="email.to is required when channels include email_campaign"
                    )
                
                # Import helpers
                from app.jobs.talentwell_curator import TalentWellCurator
                from app.validation.talentwell_validator import validate_candidate_card
                from app.mail.send_helper import send_html_email
                
                # Generate candidate card HTML using Brandon's format
                candidate_fields = canonical.get("fields", {})
                
                # Build mobility line
                curator = TalentWellCurator()
                mobility_line = curator._build_mobility_line(
                    candidate_fields.get('is_mobile', False),
                    candidate_fields.get('remote_preference', False),
                    candidate_fields.get('hybrid_preference', False)
                )
                
                # Generate hard-skill bullets
                bullets = []
                if candidate_fields.get('professional_designations'):
                    bullets.append(f"<li>Licenses/Designations: {candidate_fields['professional_designations']}</li>")
                if candidate_fields.get('book_size_aum'):
                    bullets.append(f"<li>Book Size: {candidate_fields['book_size_aum']}</li>")
                if candidate_fields.get('production_12mo'):
                    bullets.append(f"<li>12-Month Production: {candidate_fields['production_12mo']}</li>")
                if candidate_fields.get('when_available'):
                    bullets.append(f"<li>Available: {candidate_fields['when_available']}</li>")
                if candidate_fields.get('desired_comp'):
                    bullets.append(f"<li>Desired Compensation: {candidate_fields['desired_comp']}</li>")
                
                # Ensure 2-5 bullets
                if len(bullets) < 2:
                    bullets.append(f"<li>Current Role: {candidate_fields.get('job_title', 'Financial Advisor')}</li>")
                if len(bullets) < 2:
                    bullets.append(f"<li>Current Firm: {candidate_fields.get('company_name', 'Unknown')}</li>")
                bullets = bullets[:5]  # Max 5
                
                bullets_html = '\n'.join(bullets)
                
                # Generate ref code
                ref_code = f"TWAV-{request.locator[-8:]}"
                
                # Build card HTML with Brandon's format
                card_html = f"""
                <div class="candidate-card">
                    <h3><strong>{candidate_fields.get('candidate_name', 'Unknown')}</strong></h3>
                    <div class="candidate-location">
                        <strong>Location:</strong> {candidate_fields.get('location', 'Unknown')} {mobility_line}
                    </div>
                    <div class="candidate-details">
                        <div class="skill-list">
                            <ul>
                                {bullets_html}
                            </ul>
                        </div>
                        <div class="availability-comp">
                            {f'<div>Available: {candidate_fields.get("when_available")}</div>' if candidate_fields.get("when_available") else ''}
                            {f'<div>Desired Comp: {candidate_fields.get("desired_comp")}</div>' if candidate_fields.get("desired_comp") else ''}
                        </div>
                    </div>
                    <div class="ref-code">Ref code: {ref_code}</div>
                </div>
                """
                
                # Load and inject into weekly_digest_v1.html template
                try:
                    with open("app/templates/email/weekly_digest_v1.html", "r") as f:
                        template_html = f.read()
                    
                    # Replace placeholder with card HTML
                    email_html = template_html.replace("<!-- CANDIDATE_CARDS -->", card_html)
                    
                    # Update subject if in template
                    email_html = email_html.replace(
                        "<title data-ast=\"subject\">TalentWell Weekly Digest</title>",
                        f"<title>{request.email.subject}</title>"
                    )
                except:
                    # Fallback to basic HTML
                    email_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head><title>{request.email.subject}</title></head>
                    <body>
                        <h1>{request.email.subject}</h1>
                        {card_html}
                    </body>
                    </html>
                    """
                
                # Validate HTML structure
                is_valid, errors = validate_candidate_card(card_html)
                if not is_valid:
                    logger.warning(f"Card validation warnings: {errors}")
                
                # Send email
                send_result = await send_html_email(
                    subject=request.email.subject,
                    html=email_html,
                    to=request.email.to
                )
                
                results["email_campaign"] = {
                    "success": send_result.get("success", False),
                    "provider": send_result.get("provider", "unknown"),
                    "message_id": send_result.get("message_id"),
                    "recipients": request.email.to
                }
                
            elif channel == "zoho_crm":
                results[channel] = {"status": "would_sync", "fields": canonical.get("fields", {})}
            elif channel == "portal_card":
                results[channel] = {"status": "would_update", "card_id": request.locator}
            elif channel == "jd_alignment":
                results[channel] = {"alignment_score": 0.85, "matched_skills": ["Python", "FastAPI"]}
            else:
                results[channel] = canonical.get("fields", {})
        
        return {
            "published": request.channels,
            "results": results,
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
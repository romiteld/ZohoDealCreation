from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional
import time
import numpy as np
import hashlib
import json
import os
import logging
import asyncio
from scipy import stats

logger = logging.getLogger(__name__)

@dataclass
class DependencyCertificate:
    spans: Dict[str, List[Tuple[int, int]]]    # selector -> [(start,end)]
    invariants: Dict[str, str]                 # name -> rule/regex
    selector_tau: Dict[str, float]             # selector -> tau_delta

@dataclass
class C3Entry:
    artifact: bytes
    dc: DependencyCertificate
    probes: Dict[str, List[dict]]              # selector -> [{edit, span_delta}]
    calib_scores: List[Tuple[float,int]]       # [(score, span_err)]
    tau_delta: float
    meta: Dict[str, Any]                       # {embed:list[float], fields:dict, created_at:float, template_version:str}
    selector_ttl: Dict[str, Dict[str, float]]  # selector -> {alpha, beta, last_sampled_ttl}
    selector_calib: Dict[str, List[Tuple[float,int]]]  # selector -> [(score, span_err)]

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine distance between two vectors."""
    num = float(np.dot(a,b))
    den = float(np.linalg.norm(a)*np.linalg.norm(b) + 1e-9)
    return 1 - (num/den)

def _feature_drift(req_fields: dict, cache_fields: dict) -> float:
    """Calculate feature drift between request and cached fields."""
    keys = ["role_family","geo","comp_policy","template_version"]
    return sum(req_fields.get(k) != cache_fields.get(k) for k in keys) / max(len(keys),1)

def score(req: dict, meta: dict) -> float:
    """Calculate overall cache match score."""
    α, β, γ, η = 0.6, 0.3, 0.08, 0.02
    s  = α * _cosine(np.array(req.get("embed", [])), np.array(meta.get("embed", [])))
    s += β * _feature_drift(req.get("fields", {}), meta.get("fields", {}))
    s += γ * min(72, (time.time() - meta.get("created_at", time.time())) / 3600.0) / 72
    s += η * (0 if req.get("fields", {}).get("template_version")==meta.get("fields", {}).get("template_version") else 1)
    return float(s)

def _worst_probe_delta(probes: List[dict]) -> int:
    """Find maximum span delta from probes."""
    return max([p.get("span_delta",0) for p in probes], default=0)

def _conformal_tau(calib_scores: List[Tuple[float,int]], eps:int, delta:float) -> float:
    """Calculate conformal threshold tau."""
    over = sorted([s for s,e in calib_scores if e > eps])
    if not over: return 1e9
    idx = int(max(0,(1-delta)*(len(over)-1)))
    return float(over[idx])

def c3_reuse_or_rebuild(req: dict, entry: C3Entry, delta: float, eps: int) -> Tuple[str, Any]:
    """Enhanced selector-aware C³ decision with per-selector tau."""
    s = score(req, entry.meta)
    dirty = []
    
    for sel in req.get("touched_selectors", []):
        # Get selector-specific tau or use global
        selector_tau = entry.dc.selector_tau.get(sel, entry.tau_delta)
        
        # Check if this selector needs rebuild
        if _worst_probe_delta(entry.probes.get(sel,[])) > eps or s > selector_tau:
            dirty.extend(entry.dc.spans.get(sel, []))
            logger.debug(f"Selector {sel} dirty: score={s:.3f}, tau={selector_tau:.3f}")
    
    if not dirty:
        logger.info(f"C³ cache hit - score={s:.3f}")
        return ("reuse", entry.artifact)
    else:
        logger.info(f"C³ cache miss - rebuilding {len(dirty)} spans from {len(req.get('touched_selectors', []))} selectors")
        return ("rebuild", dirty)

def update_calibration(entry: C3Entry, req_score: float, realized_span_error: int,
                       eps: int, delta: float, maxlen:int=1000):
    """Update calibration scores and recalculate tau."""
    entry.calib_scores.append((req_score, realized_span_error))
    entry.calib_scores[:] = entry.calib_scores[-maxlen:]
    entry.tau_delta = _conformal_tau(entry.calib_scores, eps, delta)

def generate_cache_key(canonical_record: dict, client: str = "default", 
                      channel: str = "email", template_version: str = "v1",
                      model_id: str = "gpt-5-mini") -> str:
    """Generate cache key for C³ entry."""
    K_base = hashlib.sha256(json.dumps(canonical_record, sort_keys=True).encode()).hexdigest()
    K_art = hashlib.sha256(f"{K_base}|{client}|{channel}|{template_version}|{model_id}".encode()).hexdigest()
    return f"c3:{K_art}"


def sample_bdat_ttl(alpha: float, beta: float, min_ttl: int = 3600, 
                    max_ttl: int = 86400 * 7) -> int:
    """Sample TTL from Beta distribution (BDAT)."""
    # Sample from Beta distribution
    sample = np.random.beta(alpha, beta)
    
    # Map [0,1] to [min_ttl, max_ttl]
    ttl = int(min_ttl + sample * (max_ttl - min_ttl))
    
    return ttl


def update_selector_ttl_params(entry: C3Entry, selector: str, 
                              was_stale: bool, actual_ttl: float):
    """Update BDAT parameters based on staleness observation."""
    if selector not in entry.selector_ttl:
        entry.selector_ttl[selector] = {'alpha': 3, 'beta': 7, 'last_sampled_ttl': 86400}
    
    params = entry.selector_ttl[selector]
    
    if was_stale:
        # Entry expired too early - increase TTL
        params['beta'] = max(1, params['beta'] - 0.5)
        params['alpha'] = min(10, params['alpha'] + 0.5)
    else:
        # Entry was still fresh - could potentially decrease TTL
        if actual_ttl > params['last_sampled_ttl'] * 1.5:
            params['alpha'] = max(1, params['alpha'] - 0.2)
            params['beta'] = min(10, params['beta'] + 0.2)
    
    logger.debug(f"Updated BDAT for {selector}: α={params['alpha']:.2f}, β={params['beta']:.2f}")


async def get_selector_tau_from_redis(redis_client, selector: str) -> float:
    """Get selector-specific tau from Redis."""
    if not redis_client:
        return 0.01  # Default
    
    key = f"c3:tau:{selector}"
    value = await redis_client.get(key)
    return float(value.decode()) if value else 0.01


async def get_selector_ttl_params_from_redis(redis_client, selector: str) -> Dict[str, float]:
    """Get selector-specific BDAT parameters from Redis."""
    if not redis_client:
        return {'alpha': 3, 'beta': 7}
    
    key = f"ttl:{selector}"
    value = await redis_client.get(key)
    if value:
        return json.loads(value.decode())
    return {'alpha': 3, 'beta': 7}


def update_selector_calibration(entry: C3Entry, selector: str, 
                               req_score: float, realized_span_error: int,
                               eps: int, delta: float, maxlen: int = 100):
    """Update per-selector calibration scores."""
    if selector not in entry.selector_calib:
        entry.selector_calib[selector] = []
    
    entry.selector_calib[selector].append((req_score, realized_span_error))
    entry.selector_calib[selector] = entry.selector_calib[selector][-maxlen:]
    
    # Update selector-specific tau
    selector_tau = _conformal_tau(entry.selector_calib[selector], eps, delta)
    entry.dc.selector_tau[selector] = selector_tau
    
    logger.debug(f"Updated tau for {selector}: {selector_tau:.4f}")
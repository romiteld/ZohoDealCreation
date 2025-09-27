import json
import logging
from typing import Optional
from app.cache.c3 import C3Entry, DependencyCertificate
import redis.asyncio as redis

logger = logging.getLogger(__name__)

def decode_c3entry(raw: dict) -> Optional[C3Entry]:
    """Decode C3Entry from Redis storage format."""
    if not raw: return None
    try:
        dc_data = json.loads(raw.get("dc","{}"))
        dc = DependencyCertificate(
            spans=dc_data.get("spans",{}),
            invariants=dc_data.get("invariants",{})
        )
        return C3Entry(
            artifact=raw.get("artifact", b""),
            dc=dc,
            probes=json.loads(raw.get("probes","{}")),
            calib_scores=json.loads(raw.get("calib","[]")),
            tau_delta=float(raw.get("tau_delta","1e9")),
            meta=json.loads(raw.get("meta","{}")),
        )
    except Exception as e:
        logger.error(f"Failed to decode C3Entry: {e}")
        return None

def encode_c3entry(e: C3Entry) -> dict:
    """Encode C3Entry for Redis storage."""
    return {
        "artifact": e.artifact,
        "dc": json.dumps({"spans": e.dc.spans, "invariants": e.dc.invariants}),
        "probes": json.dumps(e.probes),
        "calib": json.dumps(e.calib_scores),
        "tau_delta": str(e.tau_delta),
        "meta": json.dumps(e.meta),
    }

async def load_c3_entry(redis_client: redis.Redis, key: str) -> Optional[C3Entry]:
    """Load C3Entry from Redis."""
    try:
        raw = await redis_client.hgetall(key)
        if not raw:
            return None
        # Convert bytes to strings for JSON parsing
        decoded = {k.decode() if isinstance(k, bytes) else k: 
                  v if k == b"artifact" else v.decode() if isinstance(v, bytes) else v
                  for k, v in raw.items()}
        return decode_c3entry(decoded)
    except Exception as e:
        logger.error(f"Failed to load C3Entry from Redis: {e}")
        return None

async def save_c3_entry(redis_client: redis.Redis, key: str, entry: C3Entry, ttl: int = 86400):
    """Save C3Entry to Redis with TTL."""
    try:
        encoded = encode_c3entry(entry)
        await redis_client.hset(key, mapping=encoded)
        await redis_client.expire(key, ttl)
        logger.info(f"Saved C3Entry to Redis: {key}")
    except Exception as e:
        logger.error(f"Failed to save C3Entry to Redis: {e}")
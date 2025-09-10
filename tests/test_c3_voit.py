import pytest
import numpy as np
import time
import json
from app.cache.c3 import (
    score, c3_reuse_or_rebuild, C3Entry, DependencyCertificate,
    update_calibration, generate_cache_key, _conformal_tau, _voi
)
from app.orchestrator.voit import voit_controller, _voi

def test_c3_score_calculation():
    """Test C³ scoring function."""
    req = {
        "embed": [0.1] * 32,
        "fields": {"template_version": "v1", "geo": "US"}
    }
    meta = {
        "embed": [0.1] * 32,
        "fields": {"template_version": "v1", "geo": "US"},
        "created_at": time.time()
    }
    s = score(req, meta)
    assert 0 <= s <= 2  # Score can be slightly above 1 due to time component

def test_c3_score_with_drift():
    """Test C³ scoring with field drift."""
    req = {
        "embed": [0.1] * 32,
        "fields": {"template_version": "v2", "geo": "EU", "role_family": "eng"}
    }
    meta = {
        "embed": [0.2] * 32,  # Different embedding
        "fields": {"template_version": "v1", "geo": "US", "role_family": "sales"},
        "created_at": time.time() - 3600  # 1 hour old
    }
    s = score(req, meta)
    assert s > 0.5  # Should have higher score due to differences

def test_voit_value_calculation():
    """Test VoIT value of insight calculation."""
    voi = _voi(qgain=0.3, cost=1.5, latency=2.0, lam=0.3, mu=0.2)
    expected = 0.3 - 0.3*1.5 - 0.2*2.0
    assert abs(voi - expected) < 0.001

def test_c3_reuse_decision():
    """Test C³ reuse vs rebuild decision."""
    entry = C3Entry(
        artifact=b"cached",
        dc=DependencyCertificate(spans={"s1": [(0,10)]}, invariants={}),
        probes={"s1": [{"edit": "minor", "span_delta": 2}]},
        calib_scores=[(0.5, 1), (0.6, 2)],
        tau_delta=0.7,
        meta={"embed": [0.1]*32, "fields": {}, "created_at": time.time()}
    )
    
    req = {"embed": [0.1]*32, "fields": {}, "touched_selectors": []}
    mode, payload = c3_reuse_or_rebuild(req, entry, delta=0.01, eps=3)
    assert mode == "reuse"

def test_c3_rebuild_decision():
    """Test C³ rebuild decision when edit exceeds threshold."""
    entry = C3Entry(
        artifact=b"cached",
        dc=DependencyCertificate(spans={"s1": [(0,10)], "s2": [(10,20)]}, invariants={}),
        probes={"s1": [{"edit": "major", "span_delta": 5}]},  # Exceeds eps=3
        calib_scores=[(0.5, 1), (0.6, 2)],
        tau_delta=0.7,
        meta={"embed": [0.1]*32, "fields": {}, "created_at": time.time()}
    )
    
    req = {"embed": [0.1]*32, "fields": {}, "touched_selectors": ["s1"]}
    mode, payload = c3_reuse_or_rebuild(req, entry, delta=0.01, eps=3)
    assert mode == "rebuild"
    assert payload == [(0, 10)]  # Should rebuild span s1

def test_conformal_tau_calculation():
    """Test conformal threshold calculation."""
    calib_scores = [
        (0.1, 1), (0.2, 2), (0.3, 4), (0.4, 5),
        (0.5, 1), (0.6, 6), (0.7, 2), (0.8, 7)
    ]
    tau = _conformal_tau(calib_scores, eps=3, delta=0.1)
    # Should select 90th percentile of scores where error > 3
    assert tau > 0

def test_update_calibration():
    """Test calibration update mechanism."""
    entry = C3Entry(
        artifact=b"test",
        dc=DependencyCertificate(spans={}, invariants={}),
        probes={},
        calib_scores=[],
        tau_delta=1e9,
        meta={}
    )
    
    # Add calibration scores
    update_calibration(entry, 0.5, 2, eps=3, delta=0.01)
    assert len(entry.calib_scores) == 1
    
    update_calibration(entry, 0.6, 4, eps=3, delta=0.01)
    assert len(entry.calib_scores) == 2
    
    # Tau should be updated
    assert entry.tau_delta != 1e9

def test_generate_cache_key():
    """Test cache key generation."""
    record = {"field1": "value1", "field2": "value2"}
    key1 = generate_cache_key(record)
    key2 = generate_cache_key(record)
    assert key1 == key2  # Same input should produce same key
    
    key3 = generate_cache_key(record, channel="zoho")
    assert key1 != key3  # Different channel should produce different key

def test_voit_controller_disabled():
    """Test VoIT controller when feature is disabled."""
    import os
    os.environ["FEATURE_VOIT"] = "false"
    
    artifact_ctx = {
        "spans": [
            {"id": "s1", "quality": 0.5, "cached_text": "test"}
        ]
    }
    
    result = voit_controller(artifact_ctx)
    assert result["assembled"] == True
    assert len(result["spans"]) == 1

def test_voit_controller_budget_constraint():
    """Test VoIT controller respects budget constraint."""
    import os
    os.environ["FEATURE_VOIT"] = "true"
    
    artifact_ctx = {
        "spans": [
            {
                "id": "s1",
                "quality": 0.3,
                "cached_text": "test1",
                "ctx": {
                    "retrieval_dispersion": 0.8,
                    "rule_conflicts": 0.5,
                    "c3_margin": 0.2,
                    "needs_fact_check": True
                }
            },
            {
                "id": "s2",
                "quality": 0.9,  # Already high quality
                "cached_text": "test2",
                "ctx": {
                    "retrieval_dispersion": 0.1,
                    "rule_conflicts": 0.1,
                    "c3_margin": 0.1,
                    "needs_fact_check": False
                }
            }
        ]
    }
    
    result = voit_controller(artifact_ctx, target_quality=0.9, total_budget=0.1)
    assert result["assembled"] == True
    # With small budget, should mostly reuse
    assert any(s.get("action_taken") == "reuse" for s in artifact_ctx["spans"])

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
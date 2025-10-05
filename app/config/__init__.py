"""
Configuration modules for Well Intake API.
Centralized configuration for VoIT, C³, and other system components.
"""
from .voit_config import VoITConfig, voit_config, FEATURE_C3, FEATURE_VOIT, C3_DELTA
from .feature_flags import (
    PRIVACY_MODE,
    FEATURE_ASYNC_ZOHO,
    FEATURE_LLM_SENTIMENT,
    FEATURE_GROWTH_EXTRACTION,
    FEATURE_AUDIENCE_FILTERING,
    FEATURE_CANDIDATE_SCORING
)

__all__ = [
    'VoITConfig', 'voit_config', 'FEATURE_C3', 'FEATURE_VOIT', 'C3_DELTA',
    'PRIVACY_MODE', 'FEATURE_ASYNC_ZOHO', 'FEATURE_LLM_SENTIMENT',
    'FEATURE_GROWTH_EXTRACTION', 'FEATURE_AUDIENCE_FILTERING', 'FEATURE_CANDIDATE_SCORING'
]

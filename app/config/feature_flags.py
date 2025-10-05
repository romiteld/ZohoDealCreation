"""
Feature flags for gradual rollout of new functionality.
Set in .env.local or environment variables.

Approved by stakeholder on 2025-10-05:
- PRIVACY_MODE: Company anonymization and strict compensation formatting
- FEATURE_ASYNC_ZOHO: Async Zoho API calls for performance
"""
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

# Privacy features (APPROVED - 2025-10-05)
PRIVACY_MODE = os.getenv('PRIVACY_MODE', 'true').lower() == 'true'

# Performance features (DISABLED - awaiting proper async implementation)
FEATURE_ASYNC_ZOHO = os.getenv('FEATURE_ASYNC_ZOHO', 'false').lower() == 'true'

# AI features
FEATURE_LLM_SENTIMENT = os.getenv('FEATURE_LLM_SENTIMENT', 'false').lower() == 'true'
FEATURE_GROWTH_EXTRACTION = os.getenv('FEATURE_GROWTH_EXTRACTION', 'true').lower() == 'true'

# UX features (Phase 3 - not implemented yet)
FEATURE_AUDIENCE_FILTERING = os.getenv('FEATURE_AUDIENCE_FILTERING', 'false').lower() == 'true'
FEATURE_CANDIDATE_SCORING = os.getenv('FEATURE_CANDIDATE_SCORING', 'false').lower() == 'true'

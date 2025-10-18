"""
Feature flags for gradual rollout of new functionality.
Set in .env.local or environment variables.

Approved by stakeholder on 2025-10-05:
- PRIVACY_MODE: Company anonymization and strict compensation formatting
- FEATURE_ASYNC_ZOHO: Async Zoho API calls for performance

Feature Flags:
==============
Privacy & Security:
- PRIVACY_MODE: Enables company anonymization and strict compensation format
  Default: true (approved 2025-10-05)

Performance:
- FEATURE_ASYNC_ZOHO: Enables async Zoho API calls for better performance
  Default: false (awaiting proper async implementation)
- USE_ASYNC_DIGEST: Use Service Bus for async digest generation
  Default: true (enabled 2025-10-15)

AI & Machine Learning:
- FEATURE_LLM_SENTIMENT: GPT-5 sentiment scoring with ±15% boost/penalty
  Default: true
- FEATURE_GROWTH_EXTRACTION: Extract growth metrics from transcripts
  Default: true
- ENABLE_NLP_CARDS: Control adaptive card generation for natural language queries
  Default: false (cards can be verbose in Teams chat)
- ENABLE_AZURE_AI_SEARCH: Route complex queries to Azure AI Search
  Default: false (experimental feature)

Data Sources:
- USE_ZOHO_API: Toggle for vault alert email generation (deprecated for queries)
  Default: false (Phase 4 - dual data source support)

User Experience:
- FEATURE_AUDIENCE_FILTERING: Enable audience-based content filtering
  Default: false (Phase 3 - not implemented)
- FEATURE_CANDIDATE_SCORING: Enable marketability scoring for vault candidates
  Default: false (Phase 3 - not implemented)
"""
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

# Privacy features (APPROVED - 2025-10-05)
PRIVACY_MODE = os.getenv('PRIVACY_MODE', 'true').lower() == 'true'

# Performance features (DISABLED - awaiting proper async implementation)
FEATURE_ASYNC_ZOHO = os.getenv('FEATURE_ASYNC_ZOHO', 'false').lower() == 'true'

# Zoho API integration (Phase 4 - dual data source support)
USE_ZOHO_API = os.getenv('USE_ZOHO_API', 'false').lower() == 'true'

# AI features
FEATURE_LLM_SENTIMENT = os.getenv('FEATURE_LLM_SENTIMENT', 'true').lower() == 'true'
FEATURE_GROWTH_EXTRACTION = os.getenv('FEATURE_GROWTH_EXTRACTION', 'true').lower() == 'true'

# Teams Bot Natural Language Processing
ENABLE_NLP_CARDS = os.getenv('ENABLE_NLP_CARDS', 'false').lower() == 'true'
ENABLE_AZURE_AI_SEARCH = os.getenv('ENABLE_AZURE_AI_SEARCH', 'false').lower() == 'true'

# Teams Bot async processing (Phase 3 - Service Bus integration - ENABLED 2025-10-15)
USE_ASYNC_DIGEST = os.getenv('USE_ASYNC_DIGEST', 'true').lower() == 'true'

# UX features (Phase 3 - not implemented yet)
FEATURE_AUDIENCE_FILTERING = os.getenv('FEATURE_AUDIENCE_FILTERING', 'false').lower() == 'true'
FEATURE_CANDIDATE_SCORING = os.getenv('FEATURE_CANDIDATE_SCORING', 'false').lower() == 'true'

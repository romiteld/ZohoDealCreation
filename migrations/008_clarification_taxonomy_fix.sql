-- Migration: Add ambiguous_query and multiple_intents to clarification taxonomy
-- Description: Expand ambiguity type constraint to support new clarification patterns
-- Author: Senior Software Engineer
-- Date: 2025-10-08
-- Related: Phase 1 - Intent Taxonomy Alignment

ALTER TABLE clarification_sessions DROP CONSTRAINT IF EXISTS valid_ambiguity_type;

ALTER TABLE clarification_sessions ADD CONSTRAINT valid_ambiguity_type CHECK (
    ambiguity_type IN (
        'missing_timeframe', 'missing_entity', 'vague_search',
        'multiple_matches', 'ambiguous_query', 'multiple_intents'
    )
);

COMMENT ON CONSTRAINT valid_ambiguity_type ON clarification_sessions IS
'Updated 2025-10-08: Added ambiguous_query and multiple_intents';

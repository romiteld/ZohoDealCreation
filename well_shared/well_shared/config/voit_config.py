"""
VoIT (Value-of-Insight Tree) Configuration Module
Shared configuration for adaptive reasoning depth control across Outlook and TalentWell systems.
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')


class VoITConfig:
    """
    Centralized VoIT configuration for both Outlook intake and TalentWell systems.

    Configuration includes:
    - Model tier selection thresholds
    - Processing budgets by context
    - Quality targets
    - Model pricing
    - Environment variable mappings
    """

    # Model pricing (per 1M tokens)
    MODEL_COSTS = {
        "gpt-5-nano": {"input": 0.05, "output": 0.15},   # $0.05 per 1M input
        "gpt-5-mini": {"input": 0.25, "output": 0.75},   # $0.25 per 1M input
        "gpt-5": {"input": 1.25, "output": 3.75}         # $1.25 per 1M input
    }

    # Complexity thresholds for model tier selection
    # Based on transcript/email length (characters)
    COMPLEXITY_THRESHOLDS = {
        "gpt-5-nano": (0, 3000),      # < 3K chars → nano
        "gpt-5-mini": (3000, 7000),   # 3K-7K chars → mini
        "gpt-5": (7000, float('inf'))  # > 7K chars → full
    }

    # Default processing budgets by context
    DEFAULT_BUDGETS = {
        "email_intake": 2.0,      # $2.00 budget for single email
        "talentwell_digest": 5.0,  # $5.00 budget for digest generation
        "batch_processing": 10.0,  # $10.00 budget for batch processing
        "research_enrichment": 3.0 # $3.00 budget for research/enrichment
    }

    # Quality targets by context
    QUALITY_TARGETS = {
        "email_intake": 0.85,      # 85% accuracy for email extraction
        "talentwell_digest": 0.90,  # 90% accuracy for digest cards
        "batch_processing": 0.80,   # 80% accuracy for batch (speed priority)
        "research_enrichment": 0.90 # 90% accuracy for enrichment
    }

    # Model environment variable mappings
    MODEL_ENV_VARS = {
        "gpt-5-nano": "GPT_5_NANO_MODEL",
        "gpt-5-mini": "GPT_5_MINI_MODEL",
        "gpt-5": "GPT_5_MODEL"
    }

    # Default model fallbacks
    MODEL_DEFAULTS = {
        "gpt-5-nano": "gpt-5-nano",
        "gpt-5-mini": "gpt-5-mini",
        "gpt-5": "gpt-5"
    }

    @classmethod
    def get_model_for_complexity(cls, text_length: int) -> str:
        """
        Select appropriate model tier based on text complexity.

        Args:
            text_length: Length of input text in characters

        Returns:
            Model tier name (e.g., 'gpt-5-nano', 'gpt-5-mini', 'gpt-5')
        """
        for model, (min_len, max_len) in cls.COMPLEXITY_THRESHOLDS.items():
            if min_len <= text_length < max_len:
                return model
        return "gpt-5"  # Default to most capable model

    @classmethod
    def get_actual_model_name(cls, model_tier: str) -> str:
        """
        Get actual OpenAI model name from environment variable.

        Args:
            model_tier: VoIT model tier (e.g., 'gpt-5-mini')

        Returns:
            Actual OpenAI model name (e.g., 'gpt-4o-mini')
        """
        env_var = cls.MODEL_ENV_VARS.get(model_tier)
        if env_var:
            return os.getenv(env_var, cls.MODEL_DEFAULTS.get(model_tier, "gpt-4o-mini"))
        return cls.MODEL_DEFAULTS.get(model_tier, "gpt-4o-mini")

    @classmethod
    def get_budget_for_context(cls, context: str) -> float:
        """
        Get processing budget for specific context.

        Args:
            context: Processing context (e.g., 'email_intake', 'talentwell_digest')

        Returns:
            Budget in dollars
        """
        return cls.DEFAULT_BUDGETS.get(context, 5.0)

    @classmethod
    def get_quality_target(cls, context: str) -> float:
        """
        Get quality target for specific context.

        Args:
            context: Processing context (e.g., 'email_intake', 'talentwell_digest')

        Returns:
            Quality target (0.0-1.0)
        """
        return cls.QUALITY_TARGETS.get(context, 0.9)

    @classmethod
    def calculate_cost(cls, model_tier: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for a VoIT operation.

        Args:
            model_tier: VoIT model tier (e.g., 'gpt-5-mini')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in dollars
        """
        model_cost = cls.MODEL_COSTS.get(model_tier, cls.MODEL_COSTS["gpt-5-mini"])
        cost = (
            (input_tokens * model_cost["input"]) +
            (output_tokens * model_cost["output"])
        ) / 1_000_000
        return round(cost, 4)

    @classmethod
    def get_config_for_context(cls, context: str) -> Dict[str, Any]:
        """
        Get complete VoIT configuration for a specific context.

        Args:
            context: Processing context (e.g., 'email_intake', 'talentwell_digest')

        Returns:
            Configuration dict with budget, quality_target, model_costs
        """
        return {
            "budget": cls.get_budget_for_context(context),
            "target_quality": cls.get_quality_target(context),
            "model_costs": cls.MODEL_COSTS,
            "complexity_thresholds": cls.COMPLEXITY_THRESHOLDS,
            "context": context
        }


# Feature flags from environment
FEATURE_C3 = os.getenv("FEATURE_C3", "true").lower() == "true"
FEATURE_VOIT = os.getenv("FEATURE_VOIT", "true").lower() == "true"

# C³ configuration
C3_DELTA = float(os.getenv("C3_DELTA", "0.01"))  # Risk bound (1%)

# Export singleton instance
voit_config = VoITConfig()

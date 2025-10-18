"""
Unit tests for feature flags configuration.

Tests environment variable parsing and default values for all feature flags,
with special focus on new NLP and Azure AI Search flags.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, mock_open
import importlib
import sys


class TestFeatureFlags:
    """Test suite for feature flags configuration."""

    def setup_method(self):
        """Setup test environment before each test."""
        # Clear any cached imports
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']

    def teardown_method(self):
        """Clean up after each test."""
        # Clean up any environment variables we set
        env_vars = [
            'PRIVACY_MODE', 'FEATURE_ASYNC_ZOHO', 'USE_ZOHO_API',
            'FEATURE_LLM_SENTIMENT', 'FEATURE_GROWTH_EXTRACTION',
            'ENABLE_NLP_CARDS', 'ENABLE_AZURE_AI_SEARCH',
            'USE_ASYNC_DIGEST', 'FEATURE_AUDIENCE_FILTERING',
            'FEATURE_CANDIDATE_SCORING'
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    @patch.dict(os.environ, {}, clear=True)
    @patch('app.config.feature_flags.load_dotenv')
    def test_default_values(self, mock_load_dotenv):
        """Test that all feature flags have correct default values."""
        # Mock load_dotenv to prevent loading actual .env files
        mock_load_dotenv.return_value = None

        # Import fresh module
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        # Privacy and Security
        assert feature_flags.PRIVACY_MODE is True, "PRIVACY_MODE should default to true"

        # Performance
        assert feature_flags.FEATURE_ASYNC_ZOHO is False, "FEATURE_ASYNC_ZOHO should default to false"
        assert feature_flags.USE_ASYNC_DIGEST is True, "USE_ASYNC_DIGEST should default to true"

        # AI features
        assert feature_flags.FEATURE_LLM_SENTIMENT is True, "FEATURE_LLM_SENTIMENT should default to true"
        assert feature_flags.FEATURE_GROWTH_EXTRACTION is True, "FEATURE_GROWTH_EXTRACTION should default to true"
        assert feature_flags.ENABLE_NLP_CARDS is False, "ENABLE_NLP_CARDS should default to false"
        assert feature_flags.ENABLE_AZURE_AI_SEARCH is False, "ENABLE_AZURE_AI_SEARCH should default to false"

        # Data sources
        assert feature_flags.USE_ZOHO_API is False, "USE_ZOHO_API should default to false"

        # UX features
        assert feature_flags.FEATURE_AUDIENCE_FILTERING is False, "FEATURE_AUDIENCE_FILTERING should default to false"
        assert feature_flags.FEATURE_CANDIDATE_SCORING is False, "FEATURE_CANDIDATE_SCORING should default to false"

    @patch.dict(os.environ, {'ENABLE_NLP_CARDS': 'true'})
    def test_enable_nlp_cards_true(self):
        """Test ENABLE_NLP_CARDS flag when set to true."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        assert feature_flags.ENABLE_NLP_CARDS is True

    @patch.dict(os.environ, {'ENABLE_NLP_CARDS': 'false'})
    def test_enable_nlp_cards_false(self):
        """Test ENABLE_NLP_CARDS flag when explicitly set to false."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        assert feature_flags.ENABLE_NLP_CARDS is False

    @patch.dict(os.environ, {'ENABLE_NLP_CARDS': 'TRUE'})
    def test_enable_nlp_cards_case_insensitive(self):
        """Test ENABLE_NLP_CARDS flag is case insensitive."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        assert feature_flags.ENABLE_NLP_CARDS is True

    @patch.dict(os.environ, {'ENABLE_AZURE_AI_SEARCH': 'true'})
    def test_enable_azure_ai_search_true(self):
        """Test ENABLE_AZURE_AI_SEARCH flag when set to true."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        assert feature_flags.ENABLE_AZURE_AI_SEARCH is True

    @patch.dict(os.environ, {'ENABLE_AZURE_AI_SEARCH': 'false'})
    def test_enable_azure_ai_search_false(self):
        """Test ENABLE_AZURE_AI_SEARCH flag when explicitly set to false."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        assert feature_flags.ENABLE_AZURE_AI_SEARCH is False

    @patch.dict(os.environ, {
        'ENABLE_NLP_CARDS': 'true',
        'ENABLE_AZURE_AI_SEARCH': 'true'
    })
    def test_both_nlp_flags_enabled(self):
        """Test both NLP flags can be enabled simultaneously."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        assert feature_flags.ENABLE_NLP_CARDS is True
        assert feature_flags.ENABLE_AZURE_AI_SEARCH is True

    @patch.dict(os.environ, {'ENABLE_NLP_CARDS': 'invalid'})
    def test_invalid_value_defaults_to_false(self):
        """Test that invalid values default to false."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        assert feature_flags.ENABLE_NLP_CARDS is False

    @patch.dict(os.environ, {'PRIVACY_MODE': 'false'})
    def test_privacy_mode_can_be_disabled(self):
        """Test PRIVACY_MODE can be disabled despite default true."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        assert feature_flags.PRIVACY_MODE is False

    @patch.dict(os.environ, {
        'PRIVACY_MODE': 'true',
        'FEATURE_ASYNC_ZOHO': 'false',
        'USE_ZOHO_API': 'false',
        'FEATURE_LLM_SENTIMENT': 'true',
        'FEATURE_GROWTH_EXTRACTION': 'true',
        'ENABLE_NLP_CARDS': 'false',
        'ENABLE_AZURE_AI_SEARCH': 'false',
        'USE_ASYNC_DIGEST': 'true',
        'FEATURE_AUDIENCE_FILTERING': 'false',
        'FEATURE_CANDIDATE_SCORING': 'false'
    })
    def test_all_flags_with_explicit_defaults(self):
        """Test all flags when explicitly set to their default values."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        # Verify all flags match expected defaults
        assert feature_flags.PRIVACY_MODE is True
        assert feature_flags.FEATURE_ASYNC_ZOHO is False
        assert feature_flags.USE_ZOHO_API is False
        assert feature_flags.FEATURE_LLM_SENTIMENT is True
        assert feature_flags.FEATURE_GROWTH_EXTRACTION is True
        assert feature_flags.ENABLE_NLP_CARDS is False
        assert feature_flags.ENABLE_AZURE_AI_SEARCH is False
        assert feature_flags.USE_ASYNC_DIGEST is True
        assert feature_flags.FEATURE_AUDIENCE_FILTERING is False
        assert feature_flags.FEATURE_CANDIDATE_SCORING is False

    @patch.dict(os.environ, {
        'ENABLE_NLP_CARDS': '1',
        'ENABLE_AZURE_AI_SEARCH': '0'
    })
    def test_numeric_values_not_treated_as_boolean(self):
        """Test that numeric values like 1 and 0 are not treated as true/false."""
        # Clear and reimport
        if 'app.config.feature_flags' in sys.modules:
            del sys.modules['app.config.feature_flags']
        from app.config import feature_flags

        # '1' != 'true' so should be false
        assert feature_flags.ENABLE_NLP_CARDS is False
        # '0' != 'true' so should be false
        assert feature_flags.ENABLE_AZURE_AI_SEARCH is False

    def test_flags_are_boolean_type(self):
        """Test that all flags are actual boolean types, not strings."""
        from app.config import feature_flags

        flags_to_check = [
            'PRIVACY_MODE', 'FEATURE_ASYNC_ZOHO', 'USE_ZOHO_API',
            'FEATURE_LLM_SENTIMENT', 'FEATURE_GROWTH_EXTRACTION',
            'ENABLE_NLP_CARDS', 'ENABLE_AZURE_AI_SEARCH',
            'USE_ASYNC_DIGEST', 'FEATURE_AUDIENCE_FILTERING',
            'FEATURE_CANDIDATE_SCORING'
        ]

        for flag_name in flags_to_check:
            flag_value = getattr(feature_flags, flag_name)
            assert isinstance(flag_value, bool), f"{flag_name} should be a boolean, got {type(flag_value)}"
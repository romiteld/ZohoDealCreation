"""
Test Apollo API key configuration in config_manager.py

This test suite verifies:
- Apollo API key field exists in ExtractionConfig
- Configuration manager loads Apollo API key correctly
- Configuration can be imported and initialized without errors
- Apollo API key is accessible via get_extraction_config()
- Environment variable handling for Apollo API key
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from dataclasses import fields
from typing import Optional

# Import the modules under test
from app.config_manager import (
    ConfigManager,
    ExtractionConfig,
    get_config_manager,
    get_extraction_config
)


class TestApolloAPIKeyConfiguration:
    """Test class for Apollo API key configuration"""

    def test_extraction_config_has_apollo_field(self):
        """Test that ExtractionConfig dataclass has apollo_api_key field"""
        # Get all field names from the dataclass
        field_names = [field.name for field in fields(ExtractionConfig)]

        # Check if apollo_api_key field exists
        assert 'apollo_api_key' in field_names, "apollo_api_key field not found in ExtractionConfig"

        # Check field type and default value
        apollo_field = next(field for field in fields(ExtractionConfig) if field.name == 'apollo_api_key')
        assert apollo_field.type == Optional[str], f"Expected Optional[str], got {apollo_field.type}"
        assert apollo_field.default is None, "apollo_api_key should default to None"

    def test_extraction_config_instantiation(self):
        """Test creating ExtractionConfig instances with apollo_api_key"""
        # Test creating instance with apollo_api_key
        config = ExtractionConfig(apollo_api_key="test-key")
        assert config.apollo_api_key == "test-key"

        # Test creating instance without apollo_api_key (should default to None)
        config_default = ExtractionConfig()
        assert config_default.apollo_api_key is None

    @patch('app.config_manager.logger')
    def test_config_manager_loads_apollo_key_from_env(self, mock_logger):
        """Test that ConfigManager loads Apollo API key from environment variable"""
        test_api_key = "apollo-test-key-12345"

        with patch.dict(os.environ, {'APOLLO_API_KEY': test_api_key}, clear=False):
            config_manager = ConfigManager()

            # Check that the apollo_api_key was loaded
            assert config_manager.extraction.apollo_api_key == test_api_key

    @patch('app.config_manager.logger')
    def test_config_manager_apollo_key_none_when_not_set(self, mock_logger):
        """Test that apollo_api_key is None when environment variable not set"""
        with patch.dict(os.environ, {}, clear=True):
            # Set minimal required env vars to prevent other errors
            with patch.dict(os.environ, {
                'USE_LANGGRAPH': 'true',
                'OPENAI_MODEL': 'gpt-5-mini',
                'OPENAI_TEMPERATURE': '1.0'
            }):
                config_manager = ConfigManager()

                # Check that apollo_api_key is None when not set
                assert config_manager.extraction.apollo_api_key is None

    @patch('app.config_manager.logger')
    def test_get_extraction_config_apollo_access(self, mock_logger):
        """Test that apollo_api_key is accessible via get_extraction_config()"""
        test_api_key = "apollo-access-test-67890"

        with patch.dict(os.environ, {'APOLLO_API_KEY': test_api_key}, clear=False):
            # Clear any existing global config manager
            import app.config_manager
            app.config_manager._config_manager = None

            # Get extraction config
            extraction_config = get_extraction_config()

            # Verify apollo_api_key is accessible
            assert hasattr(extraction_config, 'apollo_api_key'), "apollo_api_key attribute not found"
            assert extraction_config.apollo_api_key == test_api_key

            # Verify other fields are still present
            assert hasattr(extraction_config, 'use_langgraph'), "use_langgraph field missing"
            assert hasattr(extraction_config, 'openai_model'), "openai_model field missing"

    @pytest.mark.parametrize("env_value,expected", [
        ("test-apollo-key-123", "test-apollo-key-123"),
        ("", ""),
        (None, None),
    ])
    @patch('app.config_manager.logger')
    def test_apollo_key_environment_scenarios(self, mock_logger, env_value, expected):
        """Test various environment variable scenarios for Apollo API key"""
        env_dict = {}
        if env_value is not None:
            env_dict['APOLLO_API_KEY'] = env_value

        with patch.dict(os.environ, env_dict, clear=True):
            # Add minimal required vars to prevent other initialization errors
            with patch.dict(os.environ, {
                'USE_LANGGRAPH': 'true',
                'OPENAI_MODEL': 'gpt-5-mini',
                'OPENAI_TEMPERATURE': '1.0'
            }, clear=False):
                config_manager = ConfigManager()

                actual = config_manager.extraction.apollo_api_key
                assert actual == expected, f"Expected {expected}, got {actual}"

    @patch('app.config_manager.logger')
    def test_apollo_secret_retrieval_integration(self, mock_logger):
        """Test integration with the _get_secret method for Apollo API key"""
        config_manager = ConfigManager()

        # Mock the _get_secret method to verify it's called correctly
        with patch.object(config_manager, '_get_secret', return_value='mocked-apollo-key') as mock_get_secret:
            # Call _configure_extraction to trigger secret retrieval
            config_manager._configure_extraction()

            # Verify _get_secret was called with correct parameters for Apollo API key
            apollo_calls = [call for call in mock_get_secret.call_args_list
                          if call[0][0] == 'apollo-api-key']

            assert len(apollo_calls) > 0, "_get_secret not called for apollo-api-key"

            # Check the call arguments
            call_args = apollo_calls[0]
            assert call_args[0][0] == 'apollo-api-key', "Wrong secret name"
            assert call_args[0][1] == 'APOLLO_API_KEY', "Wrong fallback env name"

            # Verify the mocked value was set
            assert config_manager.extraction.apollo_api_key == 'mocked-apollo-key'

    def test_apollo_enabled_helper_function(self):
        """Test helper function to check if Apollo enrichment is enabled"""

        def is_apollo_enabled() -> bool:
            """Check if Apollo enrichment is enabled"""
            config = get_extraction_config()
            return config.apollo_api_key is not None and config.apollo_api_key.strip() != ""

        # Test with API key present
        with patch.dict(os.environ, {'APOLLO_API_KEY': 'test-key'}, clear=False):
            # Clear cached config
            import app.config_manager
            app.config_manager._config_manager = None

            enabled = is_apollo_enabled()
            assert enabled == True, "Apollo should be enabled when API key is present"

        # Test with empty API key
        with patch.dict(os.environ, {'APOLLO_API_KEY': ''}, clear=False):
            # Clear cached config
            import app.config_manager
            app.config_manager._config_manager = None

            enabled = is_apollo_enabled()
            assert enabled == False, "Apollo should be disabled when API key is empty"

        # Test with no API key
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(os.environ, {'USE_LANGGRAPH': 'true', 'OPENAI_MODEL': 'gpt-5-mini'}):
                # Clear cached config
                import app.config_manager
                app.config_manager._config_manager = None

                enabled = is_apollo_enabled()
                assert enabled == False, "Apollo should be disabled when API key is not set"

    @patch('app.config_manager.logger')
    def test_config_manager_initialization_with_apollo(self, mock_logger):
        """Test that ConfigManager can be imported and initialized with Apollo config"""
        # Test direct instantiation
        config_manager = ConfigManager()
        assert config_manager._initialized, "ConfigManager should be initialized"
        assert hasattr(config_manager.extraction, 'apollo_api_key'), "apollo_api_key should be accessible"

        # Test global instance
        global_config = get_config_manager()
        assert hasattr(global_config.extraction, 'apollo_api_key'), "apollo_api_key should be accessible via global config"

    def test_apollo_config_consistency(self):
        """Test consistency between different configuration access methods"""
        test_key = "apollo-consistency-test-key"

        with patch.dict(os.environ, {'APOLLO_API_KEY': test_key}, clear=False):
            # Clear any cached config
            import app.config_manager
            app.config_manager._config_manager = None

            # Pattern 1: Global config manager first
            global_manager = get_config_manager()
            apollo_key_1 = global_manager.extraction.apollo_api_key

            # Pattern 2: Get global config again (should be same cached instance)
            global_manager_2 = get_config_manager()
            apollo_key_2 = global_manager_2.extraction.apollo_api_key

            # Pattern 3: Extraction config function (should use cached manager)
            extraction_config = get_extraction_config()
            apollo_key_3 = extraction_config.apollo_api_key

            # Verify all patterns return the same value
            assert apollo_key_1 == apollo_key_2 == apollo_key_3 == test_key, "All access patterns should return consistent values"

            # Verify global config instances are cached
            assert global_manager is global_manager_2, "Global config manager should be cached"


@pytest.mark.integration
class TestApolloConfigurationIntegration:
    """Integration tests for Apollo configuration"""

    def test_real_environment_apollo_config(self):
        """Test Apollo configuration with real environment variables"""
        # Clear any cached config to ensure fresh read
        import app.config_manager
        app.config_manager._config_manager = None

        # This test uses the actual environment to verify configuration works
        config = get_extraction_config()

        # Check that apollo_api_key field exists and is properly typed
        assert hasattr(config, 'apollo_api_key'), "apollo_api_key field should exist"

        # The apollo_api_key should be either a string or None
        assert config.apollo_api_key is None or isinstance(config.apollo_api_key, str), \
            f"apollo_api_key should be None or string, got {type(config.apollo_api_key)}"

        # If APOLLO_API_KEY is set in environment, verify field is accessible
        env_apollo_key = os.getenv('APOLLO_API_KEY')
        if env_apollo_key:
            # Verify config has a value (may not match exactly due to test isolation)
            assert config.apollo_api_key is not None, "apollo_api_key should not be None when environment variable is set"
        else:
            # If not set, should be None
            assert config.apollo_api_key is None, "apollo_api_key should be None when not set in environment"
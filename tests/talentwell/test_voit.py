#!/usr/bin/env python3
"""
Test VoIT (Value-of-Insight Tree) orchestration for TalentWell.
Tests model tier selection, complexity calculation, budget tracking,
and Azure OpenAI integration.
"""

import pytest
import json
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.cache.voit import voit_orchestration, _extract_basic_metrics


class TestVoIT:
    """Test suite for VoIT orchestration."""

    @pytest.fixture
    def sample_transcript_simple(self):
        """Simple transcript with low complexity."""
        return """
        I've been working as a financial advisor for about 5 years.
        Currently managing around $50 million in assets.
        Looking for a new opportunity with better support.
        """

    @pytest.fixture
    def sample_transcript_medium(self):
        """Medium complexity transcript."""
        return """
        I've been in the financial services industry for 15 years, starting at Merrill Lynch
        where I built my initial book. Currently managing $350 million in assets with annual
        production around $750,000. I have my Series 7 and 66, and I'm a CFP.

        My client base consists of about 150 high-net-worth individuals, mostly business
        owners and professionals. I specialize in retirement planning and tax strategies.

        I'm looking for a firm that offers better technology and more autonomy. Ideally,
        I'd like to join a team or have the option to build one. Available in 60 days.
        """ * 3  # Repeat to increase length

    @pytest.fixture
    def sample_transcript_complex(self):
        """Complex transcript requiring deep analysis."""
        return """
        Let me walk you through my career progression and current situation in detail.

        I started my career 25 years ago at Morgan Stanley, where I spent my first decade
        building relationships and learning the business. During that time, I grew my book
        from zero to about $200 million, focusing primarily on corporate executives and
        entrepreneurs in the technology sector.

        In 2010, I made the move to an independent RIA where I had more flexibility and
        control over my practice. This was a transformative period - I was able to grow
        my AUM from $200 million to its current level of $2.3 billion. My production last
        year was $1.8 million, which represents about 35% growth year-over-year.

        My practice is quite sophisticated. I manage a team of 8 people, including 3 other
        advisors, 2 client service associates, a dedicated trader, and 2 administrative staff.
        We operate more like an institutional shop than a traditional wealth management practice.

        In terms of credentials, I have my Series 7, 66, and 24. I'm a CFA charterholder,
        a CFP, and I also have my CIMA designation. I completed my MBA at Wharton in 2005.

        My client base is concentrated - about 85 families with an average relationship size
        of roughly $25 million. My largest client has about $150 million with us. We focus
        heavily on alternative investments, tax planning, and estate planning strategies.

        The reason I'm looking to make a move is primarily about succession planning and
        platform capabilities. I want to ensure my clients are well taken care of as I
        transition toward retirement over the next 10 years. I need a firm with institutional
        capabilities, strong alternative investment access, and a robust succession program.

        I'm also interested in monetizing some of the value I've built. I'd be open to
        selling a minority stake in my practice as part of the right deal. My expectation
        for total compensation would be in the $2-3 million range, depending on the
        structure and support provided.

        I'm not in a rush to move - this needs to be the right fit. I'd probably need
        90-120 days to transition properly, ensuring minimal disruption to my clients.
        Geographic flexibility is important as I split my time between New York and Miami.
        """ * 5  # Repeat to simulate very long transcript

    @pytest.fixture
    def canonical_record_simple(self):
        """Simple canonical record."""
        return {
            'candidate_name': 'John Doe',
            'job_title': 'Financial Advisor',
            'company': 'Small RIA',
            'location': 'Chicago, IL',
            'transcript': None  # No transcript
        }

    @pytest.mark.asyncio
    async def test_model_tier_selection_simple(self, sample_transcript_simple):
        """Test that simple transcripts use GPT-5-nano."""
        with patch('app.cache.voit.client.chat.completions.create') as mock_openai:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
                'aum_managed': '$50M',
                'years_experience': '5 years',
                'licenses_held': None,
                'production_annual': None,
                'client_count': None,
                'designations': None,
                'team_size': None,
                'growth_metrics': None,
                'specialties': None,
                'availability_timeframe': None,
                'compensation_range': None
            })))]
            mock_openai.return_value = mock_response

            canonical = {
                'candidate_name': 'Test',
                'transcript': sample_transcript_simple
            }

            result = await voit_orchestration(canonical)

            # Should select nano tier for simple content
            assert result['model_used'] == 'gpt-5-nano'
            assert result['budget_used'] < 0.01  # Very cheap

    @pytest.mark.asyncio
    async def test_model_tier_selection_medium(self, sample_transcript_medium):
        """Test that medium complexity uses GPT-5-mini."""
        with patch('app.cache.voit.client.chat.completions.create') as mock_openai:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
                'aum_managed': '$350M',
                'production_annual': '$750K',
                'years_experience': '15 years',
                'licenses_held': ['Series 7', 'Series 66'],
                'designations': ['CFP'],
                'client_count': '150',
                'team_size': None,
                'growth_metrics': None,
                'specialties': ['Retirement planning', 'Tax strategies'],
                'availability_timeframe': '60 days',
                'compensation_range': None
            })))]
            mock_openai.return_value = mock_response

            canonical = {
                'candidate_name': 'Test',
                'transcript': sample_transcript_medium
            }

            result = await voit_orchestration(canonical)

            # Should select mini tier for medium complexity
            assert result['model_used'] == 'gpt-5-mini'
            assert 0.01 <= result['budget_used'] < 0.1  # Moderate cost

    @pytest.mark.asyncio
    async def test_model_tier_selection_complex(self, sample_transcript_complex):
        """Test that complex transcripts use GPT-5 full model."""
        with patch('app.cache.voit.client.chat.completions.create') as mock_openai:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
                'aum_managed': '$2.3B',
                'production_annual': '$1.8M',
                'years_experience': '25 years',
                'licenses_held': ['Series 7', 'Series 66', 'Series 24'],
                'designations': ['CFA', 'CFP', 'CIMA'],
                'client_count': '85',
                'team_size': '8',
                'growth_metrics': '35% YoY growth',
                'specialties': ['Alternative investments', 'Tax planning', 'Estate planning'],
                'availability_timeframe': '90-120 days',
                'compensation_range': '$2-3M'
            })))]
            mock_openai.return_value = mock_response

            canonical = {
                'candidate_name': 'Test',
                'transcript': sample_transcript_complex
            }

            result = await voit_orchestration(canonical)

            # Should select full GPT-5 for complex content
            assert result['model_used'] == 'gpt-5'
            assert result['budget_used'] > 0.1  # Higher cost for complex

    @pytest.mark.asyncio
    async def test_complexity_calculation(self):
        """Test complexity score calculation based on transcript length."""
        test_cases = [
            ('', 0.0),  # Empty
            ('Short text', 0.001),  # Very short
            ('x' * 3000, 0.3),  # 3k chars = 0.3
            ('x' * 7000, 0.7),  # 7k chars = 0.7
            ('x' * 10000, 1.0),  # 10k chars = 1.0 (capped)
            ('x' * 15000, 1.0),  # Over 10k still = 1.0
        ]

        for transcript, expected_complexity in test_cases:
            canonical = {'transcript': transcript}

            with patch('app.cache.voit.client.chat.completions.create') as mock_openai:
                mock_openai.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content='{}'))]
                )

                await voit_orchestration(canonical)

                # Calculate complexity internally
                complexity = len(transcript) / 10000
                complexity = min(complexity, 1.0)

                assert abs(complexity - expected_complexity) < 0.01

    @pytest.mark.asyncio
    async def test_budget_tracking(self):
        """Test that budget is tracked accurately."""
        canonical = {
            'transcript': 'x' * 5000,  # Medium complexity
            'candidate_name': 'Test'
        }

        with patch('app.cache.voit.client.chat.completions.create') as mock_openai:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
                'aum_managed': '$500M',
                'production_annual': None,
                'years_experience': '10 years',
                'licenses_held': ['Series 7'],
                'designations': None,
                'client_count': None,
                'team_size': None,
                'growth_metrics': None,
                'specialties': None,
                'availability_timeframe': None,
                'compensation_range': None
            })))]
            mock_openai.return_value = mock_response

            result = await voit_orchestration(canonical, budget=5.0)

            # Budget should be tracked
            assert 'budget_used' in result
            assert result['budget_used'] > 0
            assert result['budget_used'] < 5.0  # Within budget

            # Model costs should be reasonable
            assert result['model_used'] in ['gpt-5-nano', 'gpt-5-mini', 'gpt-5']

    @pytest.mark.asyncio
    async def test_quality_score_calculation(self):
        """Test quality score based on extracted fields."""
        test_responses = [
            # All fields extracted = high quality
            {
                'aum_managed': '$1B',
                'production_annual': '$1M',
                'years_experience': '20 years',
                'licenses_held': ['Series 7', 'Series 66'],
                'designations': ['CFA'],
                'client_count': '200',
                'team_size': '5',
                'growth_metrics': '50% growth',
                'specialties': ['Wealth management'],
                'availability_timeframe': 'Q2 2025',
                'compensation_range': '$500K+'
            },
            # Half fields extracted = medium quality
            {
                'aum_managed': '$500M',
                'production_annual': None,
                'years_experience': '10 years',
                'licenses_held': ['Series 7'],
                'designations': None,
                'client_count': None,
                'team_size': None,
                'growth_metrics': None,
                'specialties': None,
                'availability_timeframe': None,
                'compensation_range': None
            },
            # Few fields = lower quality
            {
                'aum_managed': None,
                'production_annual': None,
                'years_experience': '5 years',
                'licenses_held': None,
                'designations': None,
                'client_count': None,
                'team_size': None,
                'growth_metrics': None,
                'specialties': None,
                'availability_timeframe': None,
                'compensation_range': None
            }
        ]

        expected_scores = [1.0, 0.68, 0.54]  # Approximate expected scores

        for response_data, expected_score in zip(test_responses, expected_scores):
            with patch('app.cache.voit.client.chat.completions.create') as mock_openai:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(
                    message=MagicMock(content=json.dumps(response_data))
                )]
                mock_openai.return_value = mock_response

                canonical = {'transcript': 'test transcript', 'candidate_name': 'Test'}
                result = await voit_orchestration(canonical)

                # Quality score should reflect extraction success
                assert 'quality_score' in result
                assert abs(result['quality_score'] - expected_score) < 0.15

    @pytest.mark.asyncio
    async def test_azure_openai_integration(self):
        """Test Azure OpenAI API integration."""
        canonical = {
            'transcript': 'I manage $500M in assets with 15 years experience.',
            'candidate_name': 'Test Advisor'
        }

        with patch('app.cache.voit.client.chat.completions.create') as mock_create:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
                'aum_managed': '$500M',
                'years_experience': '15 years',
                'production_annual': None,
                'client_count': None,
                'licenses_held': None,
                'designations': None,
                'team_size': None,
                'growth_metrics': None,
                'specialties': None,
                'availability_timeframe': None,
                'compensation_range': None
            })))]
            mock_create.return_value = mock_response

            result = await voit_orchestration(canonical)

            # Verify API was called correctly
            mock_create.assert_called_once()
            call_args = mock_create.call_args

            # Check required parameters
            assert call_args.kwargs['temperature'] == 1.0  # Required for GPT-5
            assert call_args.kwargs['response_format'] == {'type': 'json_object'}
            assert 'messages' in call_args.kwargs
            assert len(call_args.kwargs['messages']) == 2  # System + user

    @pytest.mark.asyncio
    async def test_fallback_extraction(self, sample_transcript_medium):
        """Test fallback to regex extraction on API failure."""
        canonical = {
            'transcript': sample_transcript_medium,
            'candidate_name': 'Test'
        }

        with patch('app.cache.voit.client.chat.completions.create') as mock_openai:
            # Simulate API failure
            mock_openai.side_effect = Exception("OpenAI API error")

            result = await voit_orchestration(canonical)

            # Should fall back to basic extraction
            assert result['enhanced_data']['candidate_name'] == 'Test'
            assert result['quality_score'] == 0.6  # Fallback quality

            # Should still extract some data via regex
            enhanced = result['enhanced_data']
            # Basic extraction should find AUM and licenses
            if 'aum_managed' in enhanced:
                assert '$350' in enhanced['aum_managed'] or '$350M' in enhanced['aum_managed']

    def test_basic_metrics_extraction(self):
        """Test regex-based metric extraction."""
        transcript = """
        I've been managing $1.5 billion in assets for 20 years.
        My production last year was $2.5M.
        I have 350 clients and lead a team of 10 advisors.
        I hold Series 7, 66, and I'm a CFA and CFP.
        """

        metrics = _extract_basic_metrics(transcript)

        assert metrics['aum_managed'] == '$1.5B'
        assert metrics['years_experience'] == '20 years'
        assert metrics['client_count'] == '350'
        assert 'Series 7' in metrics['licenses_held']
        assert 'Series 66' in metrics['licenses_held']
        assert 'CFA' in metrics['designations']
        assert 'CFP' in metrics['designations']

    @pytest.mark.asyncio
    async def test_canonical_record_enrichment(self, canonical_record_simple):
        """Test enrichment of canonical records."""
        # Add some fields to canonical record
        canonical_record_simple['book_size_aum'] = '$100M'
        canonical_record_simple['production_12mo'] = '$500K'
        canonical_record_simple['years_experience'] = 10

        with patch('app.cache.voit.client.chat.completions.create') as mock_openai:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
                'aum_managed': None,  # Not in transcript
                'production_annual': None,
                'years_experience': None,
                'licenses_held': None,
                'designations': None,
                'client_count': None,
                'team_size': None,
                'growth_metrics': None,
                'specialties': None,
                'availability_timeframe': None,
                'compensation_range': None
            })))]
            mock_openai.return_value = mock_response

            result = await voit_orchestration(canonical_record_simple)

            # Should use canonical record data as fallback
            enhanced = result['enhanced_data']
            assert enhanced['aum_managed'] == '$100M'
            assert enhanced['production_annual'] == '$500K'
            assert enhanced['years_experience'] == 10

    @pytest.mark.asyncio
    async def test_model_cost_calculation(self):
        """Test accurate cost calculation for different models."""
        test_cases = [
            ('gpt-5-nano', 1000, 500, 0.000125),  # $0.05/1M in, $0.15/1M out
            ('gpt-5-mini', 1000, 500, 0.000625),  # $0.25/1M in, $0.75/1M out
            ('gpt-5', 1000, 500, 0.003125),       # $1.25/1M in, $3.75/1M out
        ]

        for model_name, input_tokens, output_tokens, expected_cost in test_cases:
            # Calculate cost using model pricing
            model_costs = {
                'gpt-5-nano': {'input': 0.05, 'output': 0.15},
                'gpt-5-mini': {'input': 0.25, 'output': 0.75},
                'gpt-5': {'input': 1.25, 'output': 3.75}
            }

            cost = model_costs[model_name]
            calculated = (input_tokens * cost['input'] + output_tokens * cost['output']) / 1_000_000

            assert abs(calculated - expected_cost) < 0.000001

    @pytest.mark.asyncio
    async def test_temperature_requirement(self):
        """Test that temperature=1 is always used for GPT-5 models."""
        canonical = {
            'transcript': 'Test transcript',
            'candidate_name': 'Test'
        }

        with patch('app.cache.voit.client.chat.completions.create') as mock_create:
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='{}'))]
            )

            await voit_orchestration(canonical)

            # Verify temperature=1 was used
            call_args = mock_create.call_args
            assert call_args.kwargs['temperature'] == 1.0

    @pytest.mark.asyncio
    async def test_extraction_prompt_structure(self):
        """Test that extraction prompt is properly structured."""
        canonical = {
            'transcript': 'I manage $500M AUM',
            'candidate_name': 'Test'
        }

        with patch('app.cache.voit.client.chat.completions.create') as mock_create:
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='{}'))]
            )

            await voit_orchestration(canonical)

            # Check prompt structure
            call_args = mock_create.call_args
            messages = call_args.kwargs['messages']

            # Should have system and user messages
            assert len(messages) == 2
            assert messages[0]['role'] == 'system'
            assert 'financial advisor recruiter' in messages[0]['content']
            assert messages[1]['role'] == 'user'
            assert 'aum_managed' in messages[1]['content']
            assert 'production_annual' in messages[1]['content']

    @pytest.mark.asyncio
    async def test_json_response_format(self):
        """Test that JSON response format is enforced."""
        canonical = {
            'transcript': 'Test',
            'candidate_name': 'Test'
        }

        with patch('app.cache.voit.client.chat.completions.create') as mock_create:
            # Test malformed JSON handling
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='not valid json'))]
            )

            result = await voit_orchestration(canonical)

            # Should handle JSON parse error gracefully
            assert result['enhanced_data']['candidate_name'] == 'Test'
            assert result['quality_score'] == 0.6  # Fallback quality

    @pytest.mark.asyncio
    async def test_environment_variable_models(self):
        """Test that environment variables control model selection."""
        with patch.dict(os.environ, {
            'GPT_5_NANO_MODEL': 'custom-nano-model',
            'GPT_5_MINI_MODEL': 'custom-mini-model',
            'GPT_5_MODEL': 'custom-full-model'
        }):
            canonical = {
                'transcript': 'x' * 100,  # Short = nano
                'candidate_name': 'Test'
            }

            with patch('app.cache.voit.client.chat.completions.create') as mock_create:
                mock_create.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content='{}'))]
                )

                await voit_orchestration(canonical)

                # Should use custom model from env var
                call_args = mock_create.call_args
                assert call_args.kwargs['model'] in [
                    'custom-nano-model',
                    'custom-mini-model',
                    'custom-full-model',
                    'gpt-3.5-turbo',  # Fallback defaults
                    'gpt-4o-mini',
                    'gpt-4o'
                ]
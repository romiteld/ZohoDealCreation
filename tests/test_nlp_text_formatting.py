"""
Test suite for Teams bot NLP text-only formatting and parsing.
Tests the refactored text-based responses and flexible input parsing.
"""
import pytest
import json
from typing import List, Dict, Any
from datetime import datetime

# Import the modules to test
from app.api.teams.nlp_formatters import (
    format_clarification_text,
    format_suggestions_as_text,
    format_results_as_text,
    format_medium_confidence_text,
    format_error_text,
    format_help_text,
    _format_single_result
)

from app.api.teams.nlp_parser import (
    parse_clarification_response,
    extract_candidate_reference,
    parse_refinement_input,
    extract_conversation_context,
    validate_and_sanitize_input,
    detect_query_intent
)


class TestTextFormatters:
    """Test text formatting functions."""

    def test_format_clarification_text(self):
        """Test clarification text formatting with options."""
        options = [
            {"title": "Search by Name", "value": "search_name"},
            {"title": "Search by Company", "value": "search_company"},
            {"title": "View Recent Activity", "value": "recent_activity"}
        ]
        context = "show me recent stuff"
        question = "What would you like to see?"

        result = format_clarification_text(options, context, question)

        assert "🤔 **I need a bit more information...**" in result
        assert 'You asked: "show me recent stuff"' in result
        assert "What would you like to see?" in result
        assert "1️⃣ Search by Name" in result
        assert "2️⃣ Search by Company" in result
        assert "3️⃣ View Recent Activity" in result
        assert "Reply with a number (1-3)" in result

    def test_format_suggestions_as_text(self):
        """Test low confidence suggestions formatting."""
        suggestions = [
            "View top performing advisors",
            "Show highly rated candidates",
            "Display deals with high probability"
        ]
        confidence = 0.45
        original_query = "show me the good ones"

        result = format_suggestions_as_text(suggestions, confidence, original_query)

        assert "I'm 45% confident" in result
        assert 'You asked: "show me the good ones"' in result
        assert "• View top performing advisors" in result
        assert "• Show highly rated candidates" in result
        assert "Try rephrasing or pick one" in result

    def test_format_results_as_text_candidates(self):
        """Test formatting candidate search results."""
        results = {
            "items": [
                {
                    "name": "John Smith",
                    "title": "Senior Advisor",
                    "location": "New York, NY",
                    "compensation": "$500K",
                    "aum": "$2.5M",
                    "availability": "Q1 2025"
                },
                {
                    "name": "Jane Doe",
                    "title": "Portfolio Manager",
                    "location": "Chicago, IL",
                    "compensation": "$750K",
                    "aum": "$5M",
                    "availability": "Immediately"
                }
            ]
        }

        result = format_results_as_text(results, "find advisors", "candidate")

        assert "Found 2 candidate(s)" in result
        assert "**1. John Smith** - Senior Advisor" in result
        assert "📍 New York, NY | 💰 $500K" in result
        assert "📊 $2.5M AUM | Q1 2025" in result
        assert "**2. Jane Doe** - Portfolio Manager" in result

    def test_format_results_as_text_deals(self):
        """Test formatting deal search results."""
        results = {
            "items": [
                {
                    "name": "ABC Corp Deal",
                    "stage": "Negotiation",
                    "owner": "Steve Perry",
                    "probability": 75,
                    "amount": "$2.5M"
                }
            ]
        }

        result = format_results_as_text(results, "show deals", "deal")

        assert "Found 1 deal(s)" in result
        assert "**1. ABC Corp Deal**" in result
        assert "📈 Negotiation | 👤 Steve Perry" in result
        assert "🎯 75% probability | 💵 $2.5M" in result

    def test_format_medium_confidence_text(self):
        """Test medium confidence response formatting."""
        result = {
            "text": "I found 3 candidates in New York with high AUM."
        }
        confidence = 0.65
        query = "show me good candidates in NY"

        formatted = format_medium_confidence_text(result, confidence, query)

        assert "I found 3 candidates" in formatted
        assert "💡 _I'm 65% confident" in formatted
        assert "try being more specific" in formatted

    def test_format_error_text(self):
        """Test error message formatting."""
        # Test rate limit error
        error = format_error_text("rate_limit")
        assert "⏱️ **Too Many Requests**" in error
        assert "wait a few minutes" in error

        # Test not found error
        error = format_error_text("not_found")
        assert "🔍 **No Results Found**" in error

        # Test general error with details
        error = format_error_text("general", "Database connection failed")
        assert "❌ **Something went wrong**" in error
        assert "Database connection failed" in error

    def test_format_help_text(self):
        """Test help text formatting."""
        help_text = format_help_text()

        assert "🤖 **Here's what I can help you with:**" in help_text
        assert "📊 Data Queries" in help_text
        assert "🔍 Search" in help_text
        assert "/help" in help_text
        assert "Tips:" in help_text


class TestParsers:
    """Test input parsing functions."""

    def test_parse_clarification_response_number(self):
        """Test parsing numeric responses."""
        options = [
            {"title": "Option 1", "value": "opt1"},
            {"title": "Option 2", "value": "opt2"},
            {"title": "Option 3", "value": "opt3"}
        ]

        # Direct number
        result = parse_clarification_response("2", options)
        assert result == {"title": "Option 2", "value": "opt2"}

        # Number with extra text
        result = parse_clarification_response("I'll take 3", options)
        assert result == {"title": "Option 3", "value": "opt3"}

    def test_parse_clarification_response_hash(self):
        """Test parsing hash notation responses."""
        options = [
            {"title": "First Choice", "value": "first"},
            {"title": "Second Choice", "value": "second"}
        ]

        # Hash notation
        result = parse_clarification_response("#1", options)
        assert result == {"title": "First Choice", "value": "first"}

        # Hash in sentence
        result = parse_clarification_response("Give me option #2 please", options)
        assert result == {"title": "Second Choice", "value": "second"}

    def test_parse_clarification_response_words(self):
        """Test parsing word number responses."""
        options = [
            {"title": "Alpha", "value": "a"},
            {"title": "Beta", "value": "b"},
            {"title": "Gamma", "value": "c"}
        ]

        # Word numbers
        result = parse_clarification_response("first", options)
        assert result == {"title": "Alpha", "value": "a"}

        result = parse_clarification_response("the second one", options)
        assert result == {"title": "Beta", "value": "b"}

        result = parse_clarification_response("last", options)
        assert result == {"title": "Gamma", "value": "c"}

    def test_parse_clarification_response_fuzzy(self):
        """Test fuzzy text matching."""
        options = [
            {"title": "Search by Name", "value": "search_name"},
            {"title": "Search by Company", "value": "search_company"}
        ]

        # Partial match
        result = parse_clarification_response("name", options)
        assert result == {"title": "Search by Name", "value": "search_name"}

        # Case insensitive
        result = parse_clarification_response("COMPANY", options)
        assert result == {"title": "Search by Company", "value": "search_company"}

    def test_extract_candidate_reference(self):
        """Test extracting candidate references from text."""
        # Hash notation
        action, index = extract_candidate_reference("tell me more about #1")
        assert action == "details"
        assert index == 1

        # Number reference
        action, index = extract_candidate_reference("show details for candidate 3")
        assert action == "details"
        assert index == 3

        # Word numbers
        action, index = extract_candidate_reference("what about the second one")
        assert action == "more"
        assert index == 2

        # No reference
        result = extract_candidate_reference("show me all candidates")
        assert result is None

    def test_parse_refinement_input(self):
        """Test parsing query refinement input."""
        # Time range extraction
        parsed = parse_refinement_input("show me deals from last month")
        assert parsed["time_range"]["value"] == "last month"
        assert parsed["action"] == "show"

        # Amount extraction
        parsed = parse_refinement_input("candidates with $500K+ compensation")
        assert "$500K" in parsed["amounts"]

        # Location extraction
        parsed = parse_refinement_input("advisors in New York")
        assert "new york" in parsed["locations"]

        # Quoted entities
        parsed = parse_refinement_input('search for "John Smith" in deals')
        assert "John Smith" in parsed["entities"]
        assert parsed["action"] == "search"

    def test_validate_and_sanitize_input(self):
        """Test input validation and sanitization."""
        # Valid input
        valid, sanitized, error = validate_and_sanitize_input("  Hello world  ")
        assert valid is True
        assert sanitized == "Hello world"
        assert error is None

        # Empty input
        valid, sanitized, error = validate_and_sanitize_input("")
        assert valid is False
        assert error == "Input cannot be empty"

        # Too long input
        long_text = "x" * 1001
        valid, sanitized, error = validate_and_sanitize_input(long_text)
        assert valid is False
        assert "too long" in error

        # Script injection attempt
        valid, sanitized, error = validate_and_sanitize_input("<script>alert('xss')</script>Normal text")
        assert valid is True
        assert "<script>" not in sanitized
        assert "Normal text" in sanitized

    def test_detect_query_intent(self):
        """Test query intent detection."""
        # Greeting
        intent = detect_query_intent("Hello there!")
        assert intent["intent"] == "greeting"
        assert intent["confidence"] >= 0.9

        # Search
        intent = detect_query_intent("find candidates in Boston")
        assert intent["intent"] == "search"

        # Help
        intent = detect_query_intent("how do I search for deals?")
        assert intent["intent"] == "help"

        # Analytics
        intent = detect_query_intent("show me performance metrics")
        assert intent["intent"] == "analytics"

        # Unknown
        intent = detect_query_intent("asdfghjkl")
        assert intent["intent"] == "unknown"
        assert intent["confidence"] < 0.5

    def test_extract_conversation_context(self):
        """Test conversation context extraction."""
        current = "what about those?"
        previous = [
            {"role": "user", "content": "show me top candidates"},
            {"role": "assistant", "content": "Here are 3 candidates..."}
        ]

        context = extract_conversation_context(current, previous)

        assert context["refers_to_previous"] is True
        assert "those" in context["pronouns_requiring_context"]
        assert context["continuing_thought"] is False

        # Test continuing thought
        current2 = "and also show their compensation"
        context2 = extract_conversation_context(current2, previous)
        assert context2["continuing_thought"] is True


class TestIntegration:
    """Integration tests for the complete flow."""

    def test_clarification_flow(self):
        """Test complete clarification interaction flow."""
        # Step 1: Format clarification
        options = [
            {"title": "Recent Deals", "value": "deals"},
            {"title": "Recent Candidates", "value": "candidates"}
        ]
        clarification = format_clarification_text(options, "show recent", "What type of recent activity?")

        assert "1️⃣ Recent Deals" in clarification
        assert "2️⃣ Recent Candidates" in clarification

        # Step 2: User responds
        user_response = "1"
        matched = parse_clarification_response(user_response, options)

        assert matched == {"title": "Recent Deals", "value": "deals"}

        # Step 3: Process refined query
        refined_query = f"show recent {matched['value']}"
        assert refined_query == "show recent deals"

    def test_confidence_based_formatting(self):
        """Test different formatting based on confidence levels."""
        # Low confidence (<0.5) - should trigger clarification
        low_conf_query = "show good stuff"
        confidence_low = 0.3

        # Would format as clarification
        options = [{"title": "Good Deals", "value": "deals"}]
        low_response = format_clarification_text(options, low_conf_query, "What do you consider 'good'?")
        assert "🤔" in low_response

        # Medium confidence (0.5-0.8) - should show with suggestion
        med_conf_result = {"text": "Found 5 results"}
        confidence_med = 0.65
        med_response = format_medium_confidence_text(med_conf_result, confidence_med, "query")
        assert "65% confident" in med_response

        # High confidence (>0.8) - should show direct results
        high_conf_results = {"items": [{"name": "Result 1"}]}
        high_response = format_results_as_text(high_conf_results, "query", "search")
        assert "✅" in high_response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
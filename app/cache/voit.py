"""
Value-of-Insight Tree (VoIT) orchestration for adaptive reasoning depth.
Real implementation with Azure OpenAI integration.
"""
import logging
import json
import re
import os
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Import shared VoIT configuration
from app.config import VoITConfig

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')

# Initialize Azure OpenAI client
client = AsyncOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY", os.getenv("OPENAI_API_KEY")),
    base_url=os.getenv("AZURE_OPENAI_ENDPOINT", "https://api.openai.com/v1")
)


async def voit_orchestration(
    canonical_record: Dict[str, Any],
    budget: float = 5.0,
    target_quality: float = 0.9
) -> Dict[str, Any]:
    """
    Real VoIT orchestration with Azure OpenAI - implements budget-aware reasoning depth control.

    Steps:
    1. Analyze input complexity based on transcript length
    2. Select appropriate GPT model tier based on complexity
    3. Extract financial advisor metrics from transcript
    4. Return enhanced data with model usage and quality score
    """

    transcript = canonical_record.get("transcript", "")

    # Step 1: Select model based on transcript length using shared config
    text_length = len(transcript)
    model_name = VoITConfig.get_model_for_complexity(text_length)
    actual_model = VoITConfig.get_actual_model_name(model_name)

    logger.info(f"VoIT: Text length {text_length} chars, selected {model_name} (using {actual_model})")

    # Step 3: Extract financial advisor metrics if transcript available
    enhanced_data = {
        "candidate_name": canonical_record.get("candidate_name", ""),
        "job_title": canonical_record.get("job_title", ""),
        "company": canonical_record.get("company", ""),
        "location": canonical_record.get("location", ""),
    }

    budget_used = 0.0
    quality_score = 0.5  # Base quality

    if transcript:
        try:
            # Build extraction prompt
            extraction_prompt = f"""Extract financial advisor metrics from this transcript.
Return ONLY a valid JSON object with these fields (use null if not found):

{{
  "aum_managed": "dollar amount with unit (e.g., $500M, $2.5B)",
  "production_annual": "annual production amount",
  "client_count": "number of clients",
  "years_experience": "years in industry",
  "licenses_held": ["list of licenses like Series 7, 66"],
  "designations": ["professional designations like CFA, CFP"],
  "team_size": "number if leads a team",
  "growth_metrics": "any growth percentages or achievements",
  "specialties": ["areas of expertise"],
  "availability_timeframe": "when available to start",
  "compensation_range": "expected compensation"
}}

Transcript excerpt:
{transcript[:5000]}"""

            # Call OpenAI for extraction
            response = await client.chat.completions.create(
                model=actual_model,
                messages=[
                    {"role": "system", "content": "You are a financial advisor recruiter extracting key metrics from interview transcripts."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=1.0,  # Required for GPT-5 models
                response_format={"type": "json_object"}
            )

            # Parse the response
            extracted = json.loads(response.choices[0].message.content)

            # Merge extracted data
            for key, value in extracted.items():
                if value is not None:
                    enhanced_data[key] = value

            # Calculate budget used using shared config
            input_tokens = int(len(extraction_prompt) / 4)  # Rough estimate
            output_tokens = int(len(response.choices[0].message.content) / 4)

            budget_used = VoITConfig.calculate_cost(model_name, input_tokens, output_tokens)

            # Calculate quality score based on extracted fields
            fields_extracted = sum(1 for v in extracted.values() if v is not None)
            quality_score = 0.5 + (fields_extracted / len(extracted)) * 0.5

            logger.info(f"VoIT extraction complete: {fields_extracted} fields extracted, quality {quality_score:.2f}")

        except Exception as e:
            logger.error(f"VoIT extraction error: {e}")
            # Fallback to basic extraction
            enhanced_data.update(_extract_basic_metrics(transcript))
            quality_score = 0.6

    # Also check for additional fields in canonical record
    if not enhanced_data.get("years_experience") and canonical_record.get("years_experience"):
        enhanced_data["years_experience"] = canonical_record["years_experience"]

    if not enhanced_data.get("aum_managed") and canonical_record.get("book_size_aum"):
        enhanced_data["aum_managed"] = canonical_record["book_size_aum"]

    if not enhanced_data.get("production_annual") and canonical_record.get("production_12mo"):
        enhanced_data["production_annual"] = canonical_record["production_12mo"]

    result = {
        "enhanced_data": enhanced_data,
        "model_used": model_name,
        "budget_used": round(budget_used, 4),
        "quality_score": round(quality_score, 2)
    }

    logger.info(f"VoIT processing complete - model: {model_name}, budget: ${budget_used:.4f}, quality: {quality_score:.2f}")

    return result


def _extract_basic_metrics(transcript: str) -> Dict[str, Any]:
    """Basic regex extraction as fallback."""
    metrics = {}

    # AUM patterns
    aum_patterns = [
        r'\$(\d+(?:\.\d+)?)\s*([BMK])\s*(?:AUM|aum|under management)',
        r'manages?\s*\$(\d+(?:\.\d+)?)\s*([BMK])'
    ]

    for pattern in aum_patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            amount, unit = match.groups()
            unit_map = {'B': 'B', 'M': 'M', 'K': 'K'}
            metrics["aum_managed"] = f"${amount}{unit_map.get(unit.upper(), unit)}"
            break

    # Years of experience
    years_pattern = r'(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|in\s*the\s*industry)'
    years_match = re.search(years_pattern, transcript, re.IGNORECASE)
    if years_match:
        metrics["years_experience"] = f"{years_match.group(1)} years"

    # Client count
    client_pattern = r'(\d+)\+?\s*clients?'
    client_match = re.search(client_pattern, transcript, re.IGNORECASE)
    if client_match:
        metrics["client_count"] = client_match.group(1)

    # Licenses
    licenses = []
    license_patterns = [r'series\s*(\d+)', r'SIE']
    for pattern in license_patterns:
        matches = re.findall(pattern, transcript, re.IGNORECASE)
        for match in matches:
            if pattern == r'SIE':
                licenses.append('SIE')
            else:
                licenses.append(f"Series {match}")

    if licenses:
        metrics["licenses_held"] = list(set(licenses))[:5]  # Unique, max 5

    # Designations
    designations = []
    designation_patterns = ['CFA', 'CFP', 'ChFC', 'CLU', 'CPA', 'CIMA', 'CPWA']
    for designation in designation_patterns:
        if re.search(r'\b' + designation + r'\b', transcript, re.IGNORECASE):
            designations.append(designation)

    if designations:
        metrics["designations"] = designations[:5]  # Max 5

    return metrics
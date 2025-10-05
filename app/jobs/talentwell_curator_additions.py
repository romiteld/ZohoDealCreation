"""
Additional methods for TalentWell Curator.
These should be added to the TalentWellCurator class before the export statement.
"""

async def _extract_growth_metrics(self, transcript: str) -> Optional[str]:
    """
    Extract growth metrics from transcript using pattern matching.

    Looks for patterns like:
    - "grew X%" or "grew by X%"
    - "increased from $X to $Y"
    - "expanded book from X to Y"
    - "growth of X%"

    Returns formatted string like "Grew AUM 50%" or None if no metrics found.
    """
    if not transcript:
        return None

    transcript_lower = transcript.lower()

    # Growth percentage patterns
    growth_patterns = [
        (r'grew\s+(?:book|aum|assets|production|revenue)?\s*(?:by\s+)?(\d+)%', "Grew {} by {}%"),
        (r'(\d+)%\s+growth\s+(?:in\s+)?(book|aum|assets|production|revenue)', "{} growth of {}%"),
        (r'increased\s+(?:book|aum|assets|production|revenue)?\s*(?:by\s+)?(\d+)%', "Increased {} by {}%"),
        (r'expanded\s+(?:book|aum|assets)?\s*(?:by\s+)?(\d+)%', "Expanded {} by {}%")
    ]

    for pattern, template in growth_patterns:
        matches = re.findall(pattern, transcript_lower)
        if matches:
            if isinstance(matches[0], tuple):
                # Handle patterns with multiple capture groups
                if len(matches[0]) == 2:
                    if matches[0][1] in ['book', 'aum', 'assets', 'production', 'revenue']:
                        metric = matches[0][1].upper()
                        percentage = matches[0][0]
                    else:
                        percentage = matches[0][0]
                        metric = "AUM"  # Default to AUM
                    return template.format(metric, percentage)
            else:
                # Single capture group
                return template.format("AUM", matches[0])

    # Dollar amount growth patterns
    amount_patterns = [
        r'(?:grew|increased|expanded)\s+from\s+\$(\d+(?:\.\d+)?)\s*([BMK])\s+to\s+\$(\d+(?:\.\d+)?)\s*([BMK])',
        r'\$(\d+(?:\.\d+)?)\s*([BMK])\s+to\s+\$(\d+(?:\.\d+)?)\s*([BMK])\s+(?:growth|increase)',
    ]

    for pattern in amount_patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            from_amount, from_unit, to_amount, to_unit = match.groups()

            # Convert to same unit for calculation
            unit_multiplier = {'K': 1000, 'M': 1000000, 'B': 1000000000}
            from_value = float(from_amount) * unit_multiplier.get(from_unit.upper(), 1)
            to_value = float(to_amount) * unit_multiplier.get(to_unit.upper(), 1)

            if from_value > 0:
                growth_pct = int(((to_value - from_value) / from_value) * 100)
                if growth_pct > 0:
                    return f"Grew AUM {growth_pct}% (${from_amount}{from_unit} to ${to_amount}{to_unit})"

    return None

async def _analyze_sentiment(self, transcript: str) -> float:
    """
    Analyze sentiment/enthusiasm of candidate from transcript.

    Uses GPT-5-nano to analyze enthusiasm level on a 0.0-1.0 scale.
    Returns sentiment score between 0.0 (negative) and 1.0 (very enthusiastic).
    """
    if not transcript:
        return 0.5  # Neutral default

    try:
        # Use first 2000 chars for sentiment analysis to save tokens
        transcript_excerpt = transcript[:2000]

        sentiment_prompt = f"""Analyze the enthusiasm and sentiment of this financial advisor candidate interview.
Rate their enthusiasm on a scale of 0.0 to 1.0 where:
- 0.0-0.3 = Negative/disinterested
- 0.4-0.6 = Neutral/professional
- 0.7-0.8 = Positive/engaged
- 0.9-1.0 = Very enthusiastic/excited

Consider factors like:
- Enthusiasm about the opportunity
- Confidence in their abilities
- Positive language about career growth
- Excitement about the role

Return ONLY a JSON object like: {{"score": 0.8}}

Transcript excerpt:
{transcript_excerpt}"""

        # Use GPT-5-nano (cheapest) for sentiment analysis
        response = await sentiment_client.chat.completions.create(
            model=os.getenv("GPT_5_NANO_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": "You are an expert recruiter analyzing candidate sentiment."},
                {"role": "user", "content": sentiment_prompt}
            ],
            temperature=1.0,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        sentiment_score = float(result.get("score", 0.5))

        # Ensure score is within bounds
        sentiment_score = max(0.0, min(1.0, sentiment_score))

        logger.info(f"Sentiment analysis complete: score={sentiment_score:.2f}")
        return sentiment_score

    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        return 0.5  # Return neutral on error

def _score_bullet(self, bullet: BulletPoint, sentiment_score: float = 0.5) -> float:
    """
    Score a bullet point with sentiment multiplier.

    Combines the bullet's confidence score with candidate sentiment.
    Higher sentiment increases scores for positive achievements.
    """
    base_score = bullet.confidence

    # Apply sentiment multiplier for achievement-type bullets
    achievement_keywords = [
        'grew', 'increased', 'expanded', 'top', 'achieved',
        'exceeded', 'led', 'managed', 'built', 'developed'
    ]

    is_achievement = any(keyword in bullet.text.lower() for keyword in achievement_keywords)

    if is_achievement:
        # Boost score based on sentiment (0.5 = neutral, 1.0 = max boost)
        sentiment_boost = 1.0 + (sentiment_score - 0.5)  # Range: 0.5 to 1.5
        adjusted_score = base_score * sentiment_boost
    else:
        adjusted_score = base_score

    # Cap at 1.0
    return min(adjusted_score, 1.0)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    reraise=True
)
async def _fetch_transcript_with_retry(self, meeting_ref: str) -> Optional[str]:
    """
    Fetch Zoom transcript with retry logic.

    Retries up to 3 times with exponential backoff (2-10 seconds).
    """
    from app.zoom_client import ZoomClient
    zoom_client = ZoomClient()

    try:
        transcript = await zoom_client.fetch_zoom_transcript_for_meeting(meeting_ref)
        if transcript:
            logger.info(f"Successfully fetched Zoom transcript on attempt")
            return transcript
    except Exception as e:
        logger.warning(f"Zoom transcript fetch failed: {e}")
        raise  # Re-raise to trigger retry

    return None
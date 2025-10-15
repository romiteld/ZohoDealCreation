"""
PostgreSQL Adapter for Vault Candidates

Maps vault_candidates table schema to Zoho-compatible format for Teams Bot queries.
Provides direct PostgreSQL access with schema translation layer.

Schema Mapping:
- PostgreSQL twav_number → candidate_locator
- PostgreSQL title → job_title
- PostgreSQL zoom_meeting_url → transcript_url
- PostgreSQL created_at → date_published
- All vault_candidates are considered published_to_vault=True

Usage:
    from app.api.teams.vault_adapter import query_vault_candidates_postgres

    results = await query_vault_candidates_postgres(
        twav_numbers=["TWAV109867"],
        location="Texas",
        min_aum=100000000,
        limit=50
    )
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from well_shared.database.connection import get_connection_manager

logger = logging.getLogger(__name__)


async def query_vault_candidates_postgres(
    twav_numbers: Optional[List[str]] = None,
    candidate_name: Optional[str] = None,
    location: Optional[str] = None,
    firm: Optional[str] = None,
    min_aum: Optional[float] = None,
    min_production: Optional[float] = None,
    licenses: Optional[str] = None,
    designations: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query vault_candidates from PostgreSQL with schema mapping to Zoho-compatible format.

    Args:
        twav_numbers: List of TWAV candidate locators (e.g., ["TWAV109867"])
        candidate_name: Partial name match (case-insensitive)
        location: City, state, or location string (case-insensitive)
        firm: Firm/company name (case-insensitive)
        min_aum: Minimum AUM (parsed from text field)
        min_production: Minimum production (parsed from text field)
        licenses: License requirements (case-insensitive)
        designations: Professional designations (case-insensitive)
        from_date: Created after this date
        to_date: Created before this date
        limit: Maximum results to return

    Returns:
        List of vault candidates in Zoho-compatible format with fields:
        - candidate_locator (twav_number)
        - candidate_name
        - job_title (title)
        - location (current_location or city, state)
        - firm
        - aum
        - production
        - licenses
        - designations (professional_designations)
        - transcript_url (zoom_meeting_url)
        - date_published (created_at)
        - published_to_vault (always True)

    Example:
        # Find specific candidates
        results = await query_vault_candidates_postgres(
            twav_numbers=["TWAV109867", "TWAV114860"]
        )

        # Search by criteria
        results = await query_vault_candidates_postgres(
            location="Texas",
            min_aum=50000000,
            limit=20
        )
    """
    try:
        manager = await get_connection_manager()

        async with manager.get_connection() as conn:
            # Build WHERE conditions dynamically
            conditions = ["1=1"]
            params = []
            param_idx = 1

            # Filter by TWAV numbers (exact match)
            if twav_numbers:
                placeholders = ",".join([f"${i}" for i in range(param_idx, param_idx + len(twav_numbers))])
                conditions.append(f"twav_number IN ({placeholders})")
                params.extend(twav_numbers)
                param_idx += len(twav_numbers)

            # Filter by candidate name (partial, case-insensitive)
            if candidate_name:
                conditions.append(f"candidate_name ILIKE ${param_idx}")
                params.append(f"%{candidate_name}%")
                param_idx += 1

            # Filter by location (city, state, or current_location)
            if location:
                conditions.append(
                    f"(city ILIKE ${param_idx} OR state ILIKE ${param_idx} OR current_location ILIKE ${param_idx})"
                )
                params.append(f"%{location}%")
                param_idx += 1

            # Filter by firm (partial, case-insensitive)
            if firm:
                conditions.append(f"firm ILIKE ${param_idx}")
                params.append(f"%{firm}%")
                param_idx += 1

            # Filter by licenses (partial, case-insensitive)
            if licenses:
                conditions.append(f"licenses ILIKE ${param_idx}")
                params.append(f"%{licenses}%")
                param_idx += 1

            # Filter by designations (partial, case-insensitive)
            if designations:
                conditions.append(f"professional_designations ILIKE ${param_idx}")
                params.append(f"%{designations}%")
                param_idx += 1

            # Filter by date range
            if from_date:
                conditions.append(f"created_at >= ${param_idx}")
                params.append(from_date)
                param_idx += 1

            if to_date:
                conditions.append(f"created_at <= ${param_idx}")
                params.append(to_date)
                param_idx += 1

            # Note: AUM and Production filtering requires parsing text fields
            # These are stored as strings like "$50M" or "500k"
            # For now, we'll fetch all and filter in memory if needed
            # TODO: Add numeric parsing if performance becomes an issue

            # Build final query
            query = f"""
                SELECT
                    twav_number,
                    candidate_name,
                    title,
                    city,
                    state,
                    current_location,
                    firm,
                    aum,
                    production,
                    licenses,
                    professional_designations,
                    zoom_meeting_url,
                    created_at,
                    updated_at
                FROM vault_candidates
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT ${param_idx}
            """
            params.append(limit)

            logger.info(
                f"Querying vault_candidates: {len(conditions)-1} filters, limit={limit}"
            )

            rows = await conn.fetch(query, *params)

            # Map PostgreSQL schema to Zoho-compatible format
            results = []
            for row in rows:
                # Build location string (prefer current_location)
                location_str = row["current_location"]
                if not location_str and (row["city"] or row["state"]):
                    location_str = f"{row['city'] or ''}, {row['state'] or ''}".strip(", ")

                result = {
                    # Schema mapping: PostgreSQL → Zoho format
                    "candidate_locator": row["twav_number"],
                    "candidate_name": row["candidate_name"],
                    "job_title": row["title"],
                    "location": location_str,
                    "firm": row["firm"],
                    "aum": row["aum"],
                    "production": row["production"],
                    "licenses": row["licenses"],
                    "designations": row["professional_designations"],
                    "transcript_url": row["zoom_meeting_url"],
                    "date_published": row["created_at"].isoformat() if row["created_at"] else None,
                    "published_to_vault": True,  # All vault_candidates are published

                    # Additional fields for completeness
                    "city": row["city"],
                    "state": row["state"],
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }

                # Apply numeric filters if needed (parse text fields)
                if min_aum and row["aum"]:
                    try:
                        aum_value = parse_currency_to_float(row["aum"])
                        if aum_value < min_aum:
                            continue
                    except ValueError:
                        pass  # Skip parsing errors

                if min_production and row["production"]:
                    try:
                        prod_value = parse_currency_to_float(row["production"])
                        if prod_value < min_production:
                            continue
                    except ValueError:
                        pass

                results.append(result)

            logger.info(f"Found {len(results)} vault candidates matching criteria")
            return results

    except Exception as e:
        logger.error(f"Error querying vault_candidates: {e}", exc_info=True)
        raise


def parse_currency_to_float(value: str) -> float:
    """
    Parse currency strings to float values.

    Examples:
        "$50M" → 50000000.0
        "$500k" → 500000.0
        "1.5M" → 1500000.0
        "$100,000" → 100000.0

    Args:
        value: Currency string (e.g., "$50M", "500k")

    Returns:
        Numeric value as float

    Raises:
        ValueError: If string cannot be parsed
    """
    if not value:
        raise ValueError("Empty currency value")

    # Remove common currency symbols and whitespace
    clean = value.strip().replace("$", "").replace(",", "").upper()

    # Handle M/K suffixes
    multiplier = 1.0
    if clean.endswith("M"):
        multiplier = 1_000_000
        clean = clean[:-1]
    elif clean.endswith("K"):
        multiplier = 1_000
        clean = clean[:-1]

    try:
        return float(clean) * multiplier
    except ValueError as e:
        raise ValueError(f"Cannot parse currency value: {value}") from e


async def get_vault_candidate_by_locator(twav_number: str) -> Optional[Dict[str, Any]]:
    """
    Get a single vault candidate by TWAV locator.

    Args:
        twav_number: TWAV candidate locator (e.g., "TWAV109867")

    Returns:
        Candidate data in Zoho-compatible format, or None if not found

    Example:
        candidate = await get_vault_candidate_by_locator("TWAV109867")
        if candidate:
            print(f"Found: {candidate['candidate_name']}")
    """
    results = await query_vault_candidates_postgres(
        twav_numbers=[twav_number.upper()],
        limit=1
    )
    return results[0] if results else None


async def get_vault_candidates_count(filters: Optional[Dict[str, Any]] = None) -> int:
    """
    Get count of vault candidates matching filters.

    Args:
        filters: Dictionary of filter criteria (same as query_vault_candidates_postgres)

    Returns:
        Count of matching candidates

    Example:
        count = await get_vault_candidates_count({"location": "Texas"})
        print(f"Found {count} candidates in Texas")
    """
    filters = filters or {}
    results = await query_vault_candidates_postgres(**filters, limit=100000)
    return len(results)

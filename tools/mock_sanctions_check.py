"""Mock Sanctions & Watchlist Screening tool.

Simulates screening a merchant (individual or business) against consolidated
sanctions lists (UN, OFAC, EU, local regulatory bodies).
"""

from typing import Optional


def screen_individual(
    full_name: str,
    date_of_birth: Optional[str] = None,
    nationality: Optional[str] = None,
) -> dict:
    """Screen an individual against the mock sanctions database.

    Args:
        full_name: Full name of the individual.
        date_of_birth: ISO 8601 date string (YYYY-MM-DD).
        nationality: ISO 3166-1 alpha-2 country code.

    Returns:
        Dict with keys:
          - "hit": bool
          - "matches": list[dict] (each with name, list_name, match_score)
          - "screened_at": str (ISO 8601 timestamp)
    """
    pass


def screen_entity(
    company_name: str,
    registration_number: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> dict:
    """Screen a business entity against the mock sanctions database.

    Args:
        company_name: Registered company name.
        registration_number: Business registration number.
        jurisdiction: ISO 3166-1 alpha-2 country code.

    Returns:
        Dict with keys "hit", "matches", "screened_at".
    """
    pass

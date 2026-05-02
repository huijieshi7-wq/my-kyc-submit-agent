"""Mock Company Registry lookup tool.

Simulates querying a national business registry (e.g., ACRA for Singapore,
Companies House for UK) to verify a merchant's legal entity status.
"""

from typing import Optional


def lookup_company(
    company_name: str,
    registration_number: Optional[str] = None,
    jurisdiction: str = "SG",
) -> dict:
    """Look up a company in the mock business registry.

    Args:
        company_name: Registered company name.
        registration_number: Optional business registration / UEN number.
        jurisdiction: ISO 3166-1 alpha-2 country code.

    Returns:
        Dict with keys:
          - "found": bool
          - "company_name": str
          - "registration_number": str
          - "status": str ("active", "dissolved", "suspended")
          - "incorporation_date": str (YYYY-MM-DD)
          - "registered_address": str
    """
    pass


def search_by_director(director_name: str, jurisdiction: str = "SG") -> list[dict]:
    """Search for companies associated with a given director.

    Args:
        director_name: Full name of the director.
        jurisdiction: ISO 3166-1 alpha-2 country code.

    Returns:
        List of company dicts matching the director.
    """
    pass

"""Entity Recognizer module.

Extracts named entities (company name, person name, ID numbers, addresses)
from OCR-processed KYC documents using NLP / LLM extraction techniques.
"""

from typing import Optional


def extract_company_name(text: str) -> Optional[str]:
    """Extract the registered company name from business-license text.

    Args:
        text: OCR text from a business license or incorporation document.

    Returns:
        Normalized company name, or None if not found.
    """
    pass


def extract_person_name(text: str) -> Optional[str]:
    """Extract a natural person's full name from identity-document text.

    Args:
        text: OCR text from a passport, national ID, or driver's license.

    Returns:
        Full name as "GIVEN_NAME FAMILY_NAME", or None.
    """
    pass


def extract_id_number(text: str, doc_type: str = "passport") -> Optional[str]:
    """Extract a government-issued identification number.

    Args:
        text: OCR text from an identity document.
        doc_type: One of "passport", "national_id", "driver_license".

    Returns:
        The ID/passport number as a string, or None.
    """
    pass


def extract_address(text: str) -> Optional[str]:
    """Extract a physical or registered address from document text.

    Args:
        text: OCR text from a proof-of-address or business-license document.

    Returns:
        Full address string, or None.
    """
    pass


def extract_date_of_birth(text: str) -> Optional[str]:
    """Extract date of birth from identity-document text.

    Args:
        text: OCR text from a passport, national ID, or driver's license.

    Returns:
        Date string in ISO 8601 format (YYYY-MM-DD), or None.
    """
    pass


def extract_registration_number(text: str) -> Optional[str]:
    """Extract the business registration / tax ID number.

    Args:
        text: OCR text from a business license or tax certificate.

    Returns:
        Registration number as a string, or None.
    """
    pass

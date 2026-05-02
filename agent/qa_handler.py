"""QA Handler module.

Manages the interactive question-answer dialogue with the merchant when the
KYC pipeline detects missing information, ambiguous entities, or inconsistent
data across submitted documents.
"""

from typing import Optional


def generate_question(
    gap_type: str,
    context: dict,
    previous_answers: Optional[list[dict]] = None,
) -> str:
    """Generate a natural-language question to fill a KYC information gap.

    Args:
        gap_type: Category of the gap ("missing_doc", "name_mismatch",
                  "address_unverified", "dob_unclear", "company_name_ambiguous",
                  "jurisdiction_override").
        context: Relevant entities and document metadata for the question.
        previous_answers: Prior QA history to avoid redundant questions.

    Returns:
        A merchant-facing question string in the appropriate language.
    """
    pass


def validate_answer(
    question: str,
    answer: str,
    gap_type: str,
    context: dict,
) -> tuple[bool, Optional[str]]:
    """Validate the merchant's answer for correctness and completeness.

    Args:
        question: The question that was asked.
        answer: The merchant's text response.
        gap_type: Same category passed to generate_question.
        context: Original context used to generate the question.

    Returns:
        (is_valid, error_message) tuple. error_message is None if valid.
    """
    pass


def check_consistency(
    new_answer: str,
    existing_entities: dict,
) -> list[str]:
    """Cross-check a new answer against previously extracted entities for
    inconsistencies (e.g., different company name than on the business license).

    Args:
        new_answer: The merchant's latest answer.
        existing_entities: Dict of previously extracted entities.

    Returns:
        List of inconsistency descriptions (empty if consistent).
    """
    pass


def summarize_qa_session(qa_history: list[dict]) -> str:
    """Produce a human-readable summary of the QA dialogue for the audit log.

    Args:
        qa_history: List of {"question": str, "answer": str, "validated": bool}.

    Returns:
        Markdown-formatted summary string.
    """
    pass

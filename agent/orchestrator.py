"""Orchestrator module.

Coordinates the end-to-end KYC submission pipeline: OCR → entity extraction →
rule matching → external checks → decision → QA dialogue → final submission.
"""

from typing import Optional


def run_kyc_pipeline(
    session_id: str,
    uploaded_files: list[str],
    jurisdiction: str,
) -> dict:
    """Execute the full KYC pipeline for a given merchant session.

    Steps:
        1. OCR all uploaded documents.
        2. Classify each document and extract entities.
        3. Match jurisdiction rules to determine required docs + risk level.
        4. Run external verification checks (sanctions, company registry, etc.).
        5. Pass results to the decision engine.
        6. If gaps exist, invoke QA handler to collect missing info.
        7. Produce final submission report.

    Args:
        session_id: Unique session identifier.
        uploaded_files: List of local file paths to uploaded KYC documents.
        jurisdiction: ISO 3166-1 alpha-2 country code.

    Returns:
        Pipeline result dict with keys:
          - "status": "approved" | "rejected" | "pending_review" | "more_info"
          - "report": dict with detailed findings
          - "next_steps": list[str]
    """
    pass


def handle_submission(session_id: str) -> bool:
    """Finalize and submit the approved KYC package to the acquiring bank.

    Args:
        session_id: Unique session identifier.

    Returns:
        True if submission succeeded.
    """
    pass


def get_pipeline_status(session_id: str) -> dict:
    """Return the current status and progress of a running pipeline.

    Args:
        session_id: Unique session identifier.

    Returns:
        Dict with keys "step", "progress_pct", "message".
    """
    pass

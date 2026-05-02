"""Mock Face Recognition / Liveness Detection tool.

Simulates biometric verification: comparing a selfie or video frame against
the photo embedded in an identity document, plus liveness detection.
"""

from typing import Optional


def detect_liveness(
    selfie_path: str,
    video_path: Optional[str] = None,
) -> dict:
    """Run mock liveness detection on a selfie or short video.

    Args:
        selfie_path: Local path to the selfie image.
        video_path: Optional local path to a short video for advanced liveness.

    Returns:
        Dict with keys:
          - "is_live": bool
          - "confidence": float (0.0 - 1.0)
          - "spoof_attempt": bool
          - "quality_score": float (0.0 - 1.0)
    """
    pass


def compare_face_with_id(
    selfie_path: str,
    id_photo_path: str,
) -> dict:
    """Compare a selfie against the photo extracted from an identity document.

    Args:
        selfie_path: Local path to the selfie image.
        id_photo_path: Local path to the photo extracted from the ID document.

    Returns:
        Dict with keys:
          - "match": bool
          - "similarity_score": float (0.0 - 1.0)
          - "threshold_passed": bool
    """
    pass

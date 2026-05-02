"""Mock Face-to-ID one-to-one matching tool.

Convenience wrapper that combines liveness detection and face-vs-ID comparison
into a single verification call, simulating the full biometric check flow.
"""

from typing import Optional


def verify_face_id_match(
    selfie_path: str,
    id_photo_path: str,
    video_path: Optional[str] = None,
    strict_mode: bool = True,
) -> dict:
    """Run the complete biometric verification: liveness + face match.

    Steps:
        1. Liveness detection on the selfie (and optional video).
        2. Face comparison between selfie and the ID-document photo.
        3. Return a combined pass/fail result.

    Args:
        selfie_path: Local path to the selfie image.
        id_photo_path: Local path to the photo extracted from the ID document.
        video_path: Optional video for enhanced liveness detection.
        strict_mode: If True, both liveness AND face match must pass.

    Returns:
        Dict with keys:
          - "passed": bool
          - "liveness_result": dict
          - "face_match_result": dict
          - "failure_reason": str or None
    """
    pass

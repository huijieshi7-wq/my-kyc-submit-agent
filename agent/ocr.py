"""OCR (Optical Character Recognition) module.

Extracts structured text from uploaded KYC documents (passports, business
licenses, bank statements, etc.) and returns normalized text blocks keyed by
document type.
"""

from typing import Optional


def extract_text_from_image(image_path: str, lang: str = "eng") -> str:
    """Extract raw text from a single image file using OCR.

    Args:
        image_path: Local path to the image file (PNG, JPG, TIFF).
        lang: Tesseract language code (default "eng").

    Returns:
        Raw extracted text as a single string.
    """
    pass


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """Extract text page-by-page from a PDF document.

    Args:
        pdf_path: Local path to the PDF file.

    Returns:
        List of dicts, each containing {"page": int, "text": str}.
    """
    pass


def preprocess_document(file_path: str) -> bytes:
    """Apply preprocessing (grayscale, deskew, threshold) to improve OCR accuracy.

    Args:
        file_path: Local path to the document image.

    Returns:
        Preprocessed image as raw bytes (PNG-encoded).
    """
    pass


def classify_document_type(text: str) -> Optional[str]:
    """Guess the KYC document type from its OCR text content.

    Args:
        text: Raw OCR-extracted text.

    Returns:
        One of "passport", "business_license", "bank_statement",
        "proof_of_address", "tax_certificate", or None if unsure.
    """
    pass

"""
    Image Extract
    @author: Nabeel Ahmed Jamil

    OCR helper used by audio_extract_service.py's /extract/image endpoint -- lets a caller
    extract text from a whole image, or just a rectangular region of one (in the image's
    native pixel coordinates), matching the same "mark an area, extract just that" interaction
    the PDF Highlighter screen already uses, but via OCR (pytesseract/Tesseract) instead of
    reading a PDF's embedded text layer.
"""
import pytesseract
from PIL import Image
from etl.util.logging_config import get_logger

logger = get_logger(__name__)

# Image extensions this module accepts as input.
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff")


def extract_text_from_image(image_path: str, x: int = None, y: int = None, width: int = None, height: int = None) -> str:
    """OCRs image_path, cropped to (x, y, x+width, y+height) when all four are given -- the
    region the user marked in the UI, in the image's native pixel coordinates -- otherwise
    OCRs the whole image."""
    image = Image.open(image_path)
    if x is not None and y is not None and width is not None and height is not None:
        logger.info("Cropping to region: x=%d y=%d width=%d height=%d", x, y, width, height)
        image = image.crop((x, y, x + width, y + height))
    else:
        logger.info("No region given -- OCRing the whole image")
    text = pytesseract.image_to_string(image)
    return text.strip()

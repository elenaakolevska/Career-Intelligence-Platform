from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

import pymupdf

from app.core.config import settings
from app.core.exceptions import PDFExtractionError

logger = logging.getLogger(__name__)


def _native_extract(filepath: Path) -> str:
    if not filepath.exists():
        raise PDFExtractionError(f'File not found: {filepath}')

    try:
        doc = pymupdf.open(str(filepath))
    except RuntimeError as exc:
        raise PDFExtractionError(f'Cannot open PDF (corrupted or unsupported): {exc}') from exc

    if doc.needs_pass:
        doc.close()
        raise PDFExtractionError('PDF is encrypted and cannot be processed')

    try:
        pages_text: list[str] = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text('text', sort=True)
            if page_text:
                pages_text.append(page_text.strip())

        full_text = '\n\n'.join(pages_text)
        return full_text.strip()
    finally:
        doc.close()


def _ocr_pages(filepath: Path, languages: list[str]) -> str:
    try:
        import easyocr  # type: ignore
        import numpy as np
    except ImportError as exc:
        raise PDFExtractionError('OCR requested but easyocr is not installed') from exc

    reader = easyocr.Reader(languages, gpu=False)
    doc = pymupdf.open(str(filepath))
    try:
        chunks: list[str] = []
        for page in doc:
            # Render page to image matrix for OCR
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            lines = reader.readtext(img, detail=0, paragraph=True)
            if lines:
                chunks.append('\n'.join(str(line) for line in lines))
        return '\n\n'.join(chunks).strip()
    finally:
        doc.close()


def _ocr_with_timeout(filepath: Path) -> str:
    timeout = max(1, int(settings.ocr_timeout_seconds))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_ocr_pages, filepath, list(settings.ocr_languages))
        try:
            return future.result(timeout=timeout)
        except FuturesTimeout as exc:
            raise PDFExtractionError(f'OCR timed out after {timeout}s') from exc


def extract_pdf_text(filepath: Path, /, *, allow_ocr: bool | None = None) -> tuple[str, str]:
    """
    Extract text from a PDF.

    Returns (text, extraction_method) where method is 'native' or 'ocr'.
    Falls back to EasyOCR when native extraction yields too little text.
    """
    native = _native_extract(filepath)
    use_ocr = settings.ocr_enabled if allow_ocr is None else allow_ocr

    if native and len(native) >= settings.ocr_min_chars:
        return native, 'native'

    if not use_ocr:
        if not native:
            raise PDFExtractionError('PDF contains no extractable text (scanned or image-only document)')
        return native, 'native'

    logger.info('Native extraction yielded %s chars; attempting OCR fallback', len(native or ''))
    try:
        ocr_text = _ocr_with_timeout(filepath)
    except PDFExtractionError:
        if native:
            return native, 'native'
        raise

    if not ocr_text:
        if native:
            return native, 'native'
        raise PDFExtractionError('PDF contains no extractable text (scanned or image-only document)')

    return ocr_text, 'ocr'

from __future__ import annotations

from pathlib import Path

import pymupdf

from app.core.exceptions import PDFExtractionError


def extract_pdf_text(filepath: Path, /) -> str:
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

        stripped = full_text.strip()
        if not stripped or stripped.isspace():
            raise PDFExtractionError('PDF contains no extractable text (scanned or image-only document)')

        return stripped
    finally:
        doc.close()

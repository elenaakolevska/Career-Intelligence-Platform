"""Generate synthetic PDF CVs under pdfs/ for automated tests."""

from __future__ import annotations

from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / 'pdfs'
TEXT_FILES = [
    'junior_backend.txt',
    'senior_fullstack.txt',
    'data_scientist.txt',
    'career_switcher.txt',
    'ats_problematic.txt',
    'ats_clean.txt',
]


def text_to_pdf(text: str, out_path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 72
    for line in text.splitlines():
        if y > 750:
            page = doc.new_page(width=612, height=792)
            y = 72
        page.insert_text((72, y), line[:110], fontsize=10)
        y += 14
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    doc.close()


def scanned_image_pdf(out_path: Path) -> None:
    """Image-only PDF (no text layer) for OCR path testing."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Draw text into a pixmap then insert as image so get_text returns empty
    tmp = fitz.open()
    tpage = tmp.new_page(width=612, height=792)
    tpage.insert_text((72, 120), 'Scanned CV Sample', fontsize=16)
    tpage.insert_text((72, 160), 'Email: scanned.user@example.com', fontsize=12)
    tpage.insert_text((72, 190), 'Skills: Python, SQL, Docker', fontsize=12)
    pix = tpage.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    tmp.close()
    page.insert_image(page.rect, pixmap=pix)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    doc.close()


def main() -> None:
    for name in TEXT_FILES:
        src = ROOT / name
        text_to_pdf(src.read_text(encoding='utf-8'), PDF_DIR / (src.stem + '.pdf'))
    scanned_image_pdf(PDF_DIR / 'scanned_ocr_sample.pdf')
    print(f'Wrote PDFs to {PDF_DIR}')


if __name__ == '__main__':
    main()

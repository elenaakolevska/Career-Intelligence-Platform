import io
import struct
import zlib
from pathlib import Path

import fitz
import pytest

from app.core.exceptions import PDFExtractionError
from app.services.pdf_extractor import extract_pdf_text


def _pdf_hello_world() -> bytes:
    """Generate a minimal valid PDF with 'Hello World' text using fitz."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((100, 700), 'Hello World', fontsize=12)
    bio = io.BytesIO()
    doc.save(bio)
    doc.close()
    return bio.getvalue()


def _pdf_multi_column() -> bytes:
    """Generate a PDF with two-column layout."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 700), 'Skills', fontsize=14)
    page.insert_text((50, 670), 'Python, SQL, Docker', fontsize=10)
    page.insert_text((50, 640), 'Kubernetes, AWS', fontsize=10)
    page.insert_text((350, 700), 'Experience', fontsize=14)
    page.insert_text((350, 670), 'Software Engineer at Acme', fontsize=10)
    page.insert_text((350, 640), '2 years, backend development', fontsize=10)
    page.insert_text((50, 500), 'Education', fontsize=14)
    page.insert_text((50, 470), 'BSc Computer Science', fontsize=10)
    bio = io.BytesIO()
    doc.save(bio)
    doc.close()
    return bio.getvalue()


def _pdf_empty() -> bytes:
    """Generate a PDF page with no text."""
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    bio = io.BytesIO()
    doc.save(bio)
    doc.close()
    return bio.getvalue()


def _pdf_unicode() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((100, 700), 'R\xe9sum\xe9 — Candidat', fontsize=14)
    page.insert_text((100, 670), 'Education: Universit\xe9 de Paris', fontsize=10)
    bio = io.BytesIO()
    doc.save(bio)
    doc.close()
    return bio.getvalue()


class TestPdfExtractor:
    def test_extracts_text_from_simple_pdf(self, tmp_path):
        pdf_path = tmp_path / 'simple.pdf'
        pdf_path.write_bytes(_pdf_hello_world())
        text = extract_pdf_text(pdf_path)
        assert 'Hello World' in text

    def test_extracts_text_from_unicode_pdf(self, tmp_path):
        pdf_path = tmp_path / 'unicode.pdf'
        pdf_path.write_bytes(_pdf_unicode())
        text = extract_pdf_text(pdf_path)
        assert 'R\xe9sum\xe9' in text or 'Candidat' in text

    def test_extracts_text_from_multi_column_layout(self, tmp_path):
        pdf_path = tmp_path / 'columns.pdf'
        pdf_path.write_bytes(_pdf_multi_column())
        text = extract_pdf_text(pdf_path)
        assert 'Skills' in text
        assert 'Experience' in text
        assert 'Education' in text
        assert 'Python' in text
        assert 'BSc' in text

    def test_raises_on_empty_or_no_text_pdf(self, tmp_path):
        pdf_path = tmp_path / 'empty.pdf'
        pdf_path.write_bytes(_pdf_empty())
        with pytest.raises(PDFExtractionError, match='no extractable text'):
            extract_pdf_text(pdf_path)

    def test_raises_on_encrypted_pdf(self, tmp_path):
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((100, 700), 'Secret', fontsize=12)
        bio = io.BytesIO()
        doc.save(bio, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='user')
        doc.close()
        pdf_path = tmp_path / 'encrypted.pdf'
        pdf_path.write_bytes(bio.getvalue())
        with pytest.raises(PDFExtractionError, match='encrypted'):
            extract_pdf_text(pdf_path)

    def test_raises_on_corrupted_pdf(self, tmp_path):
        pdf_path = tmp_path / 'corrupt.pdf'
        pdf_path.write_bytes(b'%PDF-1.4 corrupted garbage no valid objects')
        with pytest.raises(PDFExtractionError, match='corrupted'):
            extract_pdf_text(pdf_path)

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(PDFExtractionError, match='File not found'):
            extract_pdf_text(tmp_path / 'nonexistent.pdf')

    def test_whitespace_only_detection(self, tmp_path):
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((100, 700), '   \n   \t  ', fontsize=12)
        bio = io.BytesIO()
        doc.save(bio)
        doc.close()
        pdf_path = tmp_path / 'whitespace.pdf'
        pdf_path.write_bytes(bio.getvalue())
        with pytest.raises(PDFExtractionError, match='no extractable text'):
            extract_pdf_text(pdf_path)

"""PDF tool: extract text from academic papers.

Supports:
- PyMuPDF (local, fast, default)
- Hybrid (PyMuPDF + Gemini OCR on difficult pages)

Parser selection is controlled by env var `PDF_PARSER`:
- `auto` (default): use PyMuPDF
- `pymupdf`: use PyMuPDF
- `hybrid`: use PyMuPDF by default and trigger Gemini OCR by heuristics
"""

import os
import re
from typing import Optional

import pymupdf  # PyMuPDF


DEFAULT_MAX_CHARS = 15_000
DEFAULT_GEMINI_OCR_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")

# OCR trigger thresholds (heuristics calibrated on academic PDF samples)
_MIN_TEXT_DENSITY = 35       # chars/line; below this suggests a scanned/image PDF
_MIN_SIGNAL_CHARS = 1_200    # very short windows usually mean failed text extraction
_FORMULA_TOKEN_THRESHOLD = 15
_TABLE_TOKEN_THRESHOLD = 10

# OCR quality guardrail: reject OCR output that is clearly worse than PyMuPDF baseline
_OCR_MIN_CHARS = 500
_OCR_MIN_RATIO = 0.30  # OCR output must be >= 30% of PyMuPDF baseline length to accept


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) > max_chars:
        text = text[:max_chars]
        text += (
            f"\n\n[TRUNCATED: paper exceeds {max_chars} characters. "
            f"Analysis based on first {max_chars} chars.]"
        )
    return text


def _read_pages(doc, indices, label: bool = False, separator: str = "\n") -> str:
    """Extract text from an open PyMuPDF document for the given page indices."""
    parts = []
    for i in indices:
        text = doc[i].get_text()
        parts.append(f"[PAGE {i + 1}]\n{text}" if label else text)
    return separator.join(parts).strip()


def _extract_text_pymupdf(pdf_path: str) -> str:
    doc = pymupdf.open(pdf_path)
    text = _read_pages(doc, range(len(doc)))
    doc.close()
    return text


def _extract_text_pymupdf_pages(pdf_path: str, max_pages: int) -> str:
    doc = pymupdf.open(pdf_path)
    text = _read_pages(doc, range(min(max_pages, len(doc))), label=True, separator="\n\n")
    doc.close()
    return text


def _count_tokens(text: str, patterns: list[str]) -> int:
    return sum(len(re.findall(p, text, flags=re.IGNORECASE)) for p in patterns)


def analyze_hybrid_trigger(text: str) -> dict:
    """Analyze extracted text and decide whether OCR should be triggered.

    Triggers on any of: low text density, high formula signal, high table signal.
    """
    chars = len(text)
    lines = text.count("\n") + (1 if text else 0)
    density = chars / max(lines, 1)

    formula_tokens = _count_tokens(
        text,
        [r"\\alpha", r"\\beta", r"\\sum", r"\\int", r"\\theta", r"\bequation\b", r"="],
    )
    table_tokens = _count_tokens(text, [r"\btable\b", r"\btab\.?\b", r"\brow\b", r"\bcolumn\b"])

    reasons = []
    if density < _MIN_TEXT_DENSITY or chars < _MIN_SIGNAL_CHARS:
        reasons.append("low_text_density")
    if formula_tokens >= _FORMULA_TOKEN_THRESHOLD:
        reasons.append("high_formula_signal")
    if table_tokens >= _TABLE_TOKEN_THRESHOLD:
        reasons.append("high_table_signal")

    return {
        "chars": chars,
        "lines": lines,
        "char_density": round(density, 2),
        "formula_tokens": formula_tokens,
        "table_tokens": table_tokens,
        "should_use_ocr": bool(reasons),
        "trigger_reasons": reasons,
    }


def _extract_text_gemini_ocr(pdf_path: str, max_pages: int = 3, model: Optional[str] = None, dpi: int = 220) -> str:
    """Extract text from page images using Gemini OCR."""
    model = model or DEFAULT_GEMINI_OCR_MODEL
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    doc = pymupdf.open(pdf_path)
    page_count = min(max_pages, len(doc))
    if page_count <= 0:
        doc.close()
        return ""

    page_texts = []
    for page_index in range(page_count):
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
        png_bytes = pix.tobytes("png")

        prompt = (
            "You are doing OCR for an academic paper page. "
            "Extract all visible text accurately. Preserve equations and table content as text when possible. "
            "Do not summarize. Return plain text only."
        )

        response = client.models.generate_content(
            model=model,
            contents=[
                prompt,
                types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
            ],
        )

        text = (response.text or "").strip()
        if not text:
            text = f"[EMPTY_OCR_PAGE_{page_index + 1}]"
        page_texts.append(f"[PAGE {page_index + 1}]\n{text}")

    doc.close()
    return "\n\n".join(page_texts).strip()


def extract_text_hybrid_with_meta(
    pdf_path: str,
    max_chars: Optional[int] = None,
    max_ocr_pages: int = 3,
    model: Optional[str] = None,
    signal_pages: int = 3,
) -> tuple[str, dict]:
    """Hybrid extraction with trigger metadata.

    Returns:
        (extracted_text, metadata)
    """
    if max_chars is None:
        max_chars = int(os.environ.get("PDF_MAX_CHARS", str(DEFAULT_MAX_CHARS)))

    # Single PDF open: collect all page text, signal window, and total page count.
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    all_text_parts = []
    signal_parts = []
    for i in range(total_pages):
        page_text = doc[i].get_text()
        all_text_parts.append(page_text)
        if i < signal_pages:
            signal_parts.append(f"[PAGE {i + 1}]\n{page_text}")
    doc.close()

    pym_text_full = "\n".join(all_text_parts).strip()
    pym_signal_window = "\n\n".join(signal_parts).strip()
    trigger = analyze_hybrid_trigger(pym_signal_window)

    meta = {
        "used_ocr": False,
        "ocr_parser": "gemini",
        "ocr_model": model or DEFAULT_GEMINI_OCR_MODEL,
        "signal_window_pages": signal_pages,
        "max_ocr_pages": max_ocr_pages,
        "trigger": trigger,
        "compare_window_text": pym_signal_window,
        "decision": "pymupdf",
        "decision_reason": "trigger_not_fired",
        "error": "",
    }

    if trigger.get("should_use_ocr"):
        meta["decision_reason"] = "trigger_fired"
        try:
            ocr_window = _extract_text_gemini_ocr(
                pdf_path,
                max_pages=max_ocr_pages,
                model=model,
            )
            # Guardrail: only accept OCR if it is not clearly degraded versus baseline window.
            baseline_chars = max(len(pym_signal_window), 1)
            ocr_chars = len(ocr_window)
            ocr_ratio = ocr_chars / baseline_chars
            if ocr_chars < _OCR_MIN_CHARS or ocr_ratio < _OCR_MIN_RATIO:
                meta["decision"] = "pymupdf"
                meta["decision_reason"] = "ocr_quality_guard_fallback"
                return _truncate_text(pym_text_full, max_chars), meta

            if total_pages > max_ocr_pages:
                # Use already-extracted page text — no need to reopen the PDF.
                remainder_parts = [
                    f"[PAGE {i + 1}]\n{all_text_parts[i]}"
                    for i in range(max_ocr_pages, total_pages)
                ]
                remainder = "\n\n".join(remainder_parts).strip()
                # OCR covers first pages; PyMuPDF provides fallback context for the rest.
                hybrid_text = f"{ocr_window}\n\n[PYMUPDF_FALLBACK_CONTEXT]\n{remainder}"
            else:
                hybrid_text = ocr_window

            meta["used_ocr"] = True
            meta["compare_window_text"] = ocr_window
            meta["decision"] = "hybrid_ocr"
            meta["decision_reason"] = "ocr_accepted"
            return _truncate_text(hybrid_text, max_chars), meta
        except Exception as e:
            meta["error"] = str(e)
            meta["decision"] = "pymupdf"
            meta["decision_reason"] = "ocr_error_fallback"

    return _truncate_text(pym_text_full, max_chars), meta


def extract_text(pdf_path: str, max_chars: Optional[int] = None) -> str:
    """Extract text from a PDF file.

    Args:
        pdf_path: Path to the PDF file.
        max_chars: Maximum characters to return. If None, uses env PDF_MAX_CHARS
            (default: 15000). Longer papers are truncated.

    Returns:
        Extracted plain text. If truncated, ends with a truncation notice.
    """
    if max_chars is None:
        max_chars = int(os.environ.get("PDF_MAX_CHARS", str(DEFAULT_MAX_CHARS)))

    parser = os.environ.get("PDF_PARSER", "auto").strip().lower()

    if parser == "hybrid":
        text, _meta = extract_text_hybrid_with_meta(
            pdf_path,
            max_chars=max_chars,
            max_ocr_pages=int(os.environ.get("HYBRID_OCR_MAX_PAGES", "3")),
            model=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_OCR_MODEL),
            signal_pages=int(os.environ.get("HYBRID_SIGNAL_PAGES", "3")),
        )
        return text

    # Default path: fast local parser.
    pymupdf_text = _extract_text_pymupdf(pdf_path)
    return _truncate_text(pymupdf_text, max_chars)

"""PDF tool: extract text from academic papers using PyMuPDF."""

import pymupdf  # PyMuPDF

# Academic papers are often long. Cap at ~100k chars to stay within LLM context limits.
# At ~4 chars/token, 100k chars ≈ 25k tokens — comfortable for most models.
MAX_CHARS = 15_000


def extract_text(pdf_path: str, max_chars: int = MAX_CHARS) -> str:
    """Extract text from a PDF file.

    Args:
        pdf_path: Path to the PDF file.
        max_chars: Maximum characters to return. Longer papers are truncated.

    Returns:
        Extracted plain text. If truncated, ends with a truncation notice.
    """
    doc = pymupdf.open(pdf_path)

    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())

    doc.close()

    full_text = "\n".join(pages_text).strip()

    if len(full_text) > max_chars:
        full_text = full_text[:max_chars]
        full_text += f"\n\n[TRUNCATED: paper exceeds {max_chars} characters. Analysis based on first {max_chars} chars.]"

    return full_text

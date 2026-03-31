"""arXiv tool: search papers via Gemini Google Search and download PDFs.

Search uses Gemini + Google Search grounding (no arXiv API dependency).
PDF download still fetches directly from arxiv.org.
"""

import json
import os
import re
import time
from typing import Optional
import tempfile
from urllib.parse import urlparse

import requests
from tools.relevance import evaluate_search_candidate, parse_query_constraints

ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}"
ARXIV_ABS_URL = "https://arxiv.org/abs/{arxiv_id}"
ACADEMIC_SOURCE_DOMAINS = (
    "arxiv.org",
    "ssrn.com",
    "nber.org",
    "sciencedirect.com",
    "springer.com",
    "link.springer.com",
    "onlinelibrary.wiley.com",
    "tandfonline.com",
    "journals.uchicago.edu",
    "academic.oup.com",
    "cambridge.org",
    "aeaweb.org",
)
OFFICIAL_SOURCE_DOMAINS = (
    "fred.stlouisfed.org",
    "sec.gov",
    "federalreserve.gov",
    "ecb.europa.eu",
    "bis.org",
    "imf.org",
    "worldbank.org",
    "treasury.gov",
    "cmegroup.com",
    "nasdaq.com",
    "nyse.com",
)


def normalize_arxiv_id(arxiv_id: str) -> str:
    """Normalize arXiv ID by stripping version suffix and whitespace."""
    if not arxiv_id:
        return ""
    normalized = arxiv_id.strip()
    normalized = re.sub(r"v\d+$", "", normalized)
    return normalized


def _safe_filename(s: str) -> str:
    """Replace characters unsafe for filenames with underscores."""
    return re.sub(r"[^\w.\-]", "_", s)


def _classify_source_url(url: str) -> Optional[str]:
    domain = urlparse((url or "").strip()).netloc.lower().split(":")[0]
    if any(domain == allowed or domain.endswith(f".{allowed}") for allowed in ACADEMIC_SOURCE_DOMAINS):
        return "academic"
    if any(domain == allowed or domain.endswith(f".{allowed}") for allowed in OFFICIAL_SOURCE_DOMAINS):
        return "official"
    return None


# ---------------------------------------------------------------------------
# Gemini helper
# ---------------------------------------------------------------------------

def _get_gemini_client():
    """Return a (client, model_id) tuple using env vars."""
    import google.genai as genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model_id = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    return client, model_id


def _gemini_search(client, model_id, prompt, max_retries: int = 3) -> str:
    """Call Gemini with Google Search grounding, retrying on empty/RECITATION."""
    from google.genai import types
    tools = [types.Tool(google_search=types.GoogleSearch())]

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(tools=tools),
            )
        except Exception:
            time.sleep(2 * (attempt + 1))
            continue

        text = (getattr(response, "text", "") or "").strip()
        if not text:
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                parts = getattr(getattr(candidates[0], "content", None), "parts", None) or []
                text = "\n".join(
                    getattr(part, "text", "").strip()
                    for part in parts
                    if getattr(part, "text", None)
                ).strip()
        if text:
            return text
        time.sleep(2 * (attempt + 1))

    return ""


def _strip_code_fences(text: str) -> str:
    """Remove markdown ```json ... ``` fences."""
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _search_arxiv_ids(client, model_id, query: str, max_results: int) -> list:
    """Stage 1: Stable ID-only search (minimal, most reliable).
    
    Returns list of dicts with arxiv_id and sources_tried.
    """
    sources_tried = []
    
    # Try 1: Ask for JSON array of IDs
    prompt_ids = (
        f"List up to {max_results} arXiv paper IDs about: {query}\n\n"
        "Return ONLY a JSON array of strings (just the IDs, no objects).\n"
        'Format: ["2406.18394", "2602.14670", ...]\n'
        "No markdown. No other text."
    )
    text = _gemini_search(client, model_id, prompt_ids, max_retries=2)
    sources_tried.append("gemini_json_ids")
    
    ids = []
    if text:
        text = _strip_code_fences(text)
        try:
            raw_ids = json.loads(text)
            if isinstance(raw_ids, list):
                for item in raw_ids:
                    if isinstance(item, str):
                        normalized = normalize_arxiv_id(item)
                        if normalized:
                            ids.append(normalized)
        except json.JSONDecodeError:
            pass
    
    # Try 2: Fallback to one-per-line format
    if not ids:
        prompt_lines = (
            f"List {max_results} arXiv paper IDs about: {query}.\n"
            "One ID per line, nothing else."
        )
        text = _gemini_search(client, model_id, prompt_lines, max_retries=2)
        sources_tried.append("gemini_line_ids")
        
        if text:
            for line in text.split('\n'):
                line = line.strip()
                normalized = normalize_arxiv_id(line)
                if normalized:
                    ids.append(normalized)
    
    # Deduplicate
    ids = list(dict.fromkeys(ids))[:max_results]
    
    return [
        {"arxiv_id": aid, "sources_tried": sources_tried}
        for aid in ids
    ]


def _validate_paper_record(paper: dict) -> bool:
    """Check if paper record has required fields."""
    required = ["arxiv_id", "title", "authors", "published"]
    for field in required:
        val = paper.get(field)
        if isinstance(val, (list, str)):
            if not val:  # empty list or empty string
                return False
        else:
            if val is None:
                return False
    return True


def _enrich_from_arxiv_abs_page(arxiv_id: str) -> dict:
    """Fetch metadata from arXiv abstract page (deterministic, reliable).
    
    Parses title, authors, and published date from the arXiv abs page.
    Returns dict with found metadata or empty dict on failure.
    """
    if not arxiv_id:
        return {}
    
    try:
        abs_url = ARXIV_ABS_URL.format(arxiv_id=arxiv_id)
        response = requests.get(abs_url, timeout=10)
        response.raise_for_status()
    except Exception:
        return {}
    
    html = response.text
    metadata = {}
    
    # Extract title (arXiv format: <h1 class="title mathjax">Title Here</h1>)
    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    if title_match:
        title = title_match.group(1).strip()
        title = re.sub(r'\s+', ' ', title)  # normalize whitespace
        if title.lower().startswith('title:'):
            title = title[6:].strip()
        metadata['title'] = title
    
    # Extract authors (format: <div class="authors"><a>Author Name</a>, <a>Author 2</a></div>)
    authors_match = re.search(r'<div[^>]*class="[^"]*authors[^"]*"[^>]*>(.+?)</div>', html, re.DOTALL)
    if authors_match:
        authors_html = authors_match.group(1)
        authors = re.findall(r'>([^<]+)</a>', authors_html)
        if authors:
            metadata['authors'] = [a.strip() for a in authors]
    
    # Extract date (format: <div class="dateline">Submitted on ... (v1) ... [last updated ...]</div>)
    date_match = re.search(r'Submitted on (\d+ \w+ \d{4})', html)
    if date_match:
        # Try to parse date string to YYYY-MM-DD
        date_str = date_match.group(1)
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, '%d %b %Y')
            metadata['published'] = dt.strftime('%Y-%m-%d')
        except (ValueError, ImportError):
            metadata['published'] = date_str

    # Extract abstract (format: <blockquote class="abstract mathjax">Abstract: ...</blockquote>)
    abstract_match = re.search(
        r'<blockquote[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</blockquote>',
        html,
        re.DOTALL,
    )
    if abstract_match:
        abstract = abstract_match.group(1).strip()
        # Strip leading "Abstract:" label arXiv includes
        abstract = re.sub(r'^<span[^>]*>Abstract:</span>\s*', '', abstract)
        abstract = re.sub(r'^Abstract:\s*', '', abstract)
        # Remove HTML tags, decode entities, and normalize whitespace
        abstract = re.sub(r'<[^>]+>', '', abstract)
        import html as _html
        abstract = _html.unescape(abstract)
        abstract = re.sub(r'\s+', ' ', abstract).strip()
        if abstract:
            metadata['abstract'] = abstract

    return metadata


# ---------------------------------------------------------------------------
# Public: search_papers
# ---------------------------------------------------------------------------

def search_papers(query: str, max_results: int = 5) -> list:
    """Search arXiv papers using Gemini + Google Search (no arXiv API).

    Strategy (ID-first, multi-source enrichment):
      1. Search for arXiv IDs only (most reliable)
      2. Validate IDs
      3. Enrich metadata (title, authors, published):
         - Stage 1: Read from arXiv abstract page (deterministic)
         - Stage 2: Gemini fallback (LLM-based, if Stage 1 incomplete)
      4. Return papers with validated flag and sources_tried for tracking

    Args:
        query: Search keywords (e.g. "momentum strategy stock market")
        max_results: Maximum number of papers to return

    Returns:
        List of dicts with: arxiv_id, title, authors, abstract, pdf_url, published, validated, sources_tried
    """
    client, model_id = _get_gemini_client()
    constraints = parse_query_constraints(query)

    # --- Step 1: Find arXiv IDs (most stable) ---
    paper_drafts = _search_arxiv_ids(client, model_id, query, max_results)
    if not paper_drafts:
        return []

    # --- Step 2: Build paper shells with IDs ---
    papers = []
    for draft in paper_drafts:
        aid = draft["arxiv_id"]
        sources = draft.get("sources_tried", [])
        
        paper = {
            "arxiv_id": aid,
            "title": "",
            "authors": [],
            "abstract": "",
            "pdf_url": ARXIV_PDF_URL.format(arxiv_id=aid),
            "published": "",
            "sources_tried": sources,
        }
        papers.append(paper)
    
    # --- Step 3a: Enrich via arXiv abstract pages (Stage 1, deterministic) ---
    for paper in papers:
        metadata = _enrich_from_arxiv_abs_page(paper["arxiv_id"])
        if metadata:
            paper["sources_tried"].append("arxiv_abs_page_success")
            if metadata.get("title") and not paper["title"]:
                paper["title"] = metadata["title"]
            if metadata.get("authors") and not paper["authors"]:
                paper["authors"] = metadata["authors"]
            if metadata.get("published") and not paper["published"]:
                paper["published"] = metadata["published"]
            if metadata.get("abstract") and not paper["abstract"]:
                paper["abstract"] = metadata["abstract"]
        else:
            paper["sources_tried"].append("arxiv_abs_page_failed")
    
    # --- Step 3b: Enrich missing metadata via Gemini (Stage 2, fallback) ---
    ids_still_needing_enrich = [
        p["arxiv_id"] for p in papers
        if not p["title"] or not p["authors"] or not p["published"]
    ]
    if ids_still_needing_enrich:
        _enrich_papers_via_gemini_fallback(client, model_id, papers, ids_still_needing_enrich)
    
    # --- Step 4: Validate and mark papers ---
    filtered_papers = []
    for paper in papers:
        relevance = evaluate_search_candidate(paper, constraints)
        paper.update(relevance)
        paper["validated"] = _validate_paper_record(paper)
        if constraints.get("market_targets") and not paper["market_match"] and not paper["uncertain_market_match"]:
            continue
        filtered_papers.append(paper)

    return filtered_papers


def _enrich_papers_via_gemini_fallback(client, model_id, papers: list, arxiv_ids: list) -> None:
    """Fallback: Fetch missing metadata for papers by asking Gemini to read their arXiv pages.
    
    This is Stage 2 enrichment; Stage 1 should be official API or deterministic source.
    Track sources_tried to mark enrichment came from LLM.
    """
    if not arxiv_ids:
        return
    
    ids_str = ", ".join(arxiv_ids)
    prompt = (
        f"For these arXiv papers: {ids_str}\n\n"
        "Visit each paper's arXiv page and provide:\n"
        "- arxiv_id\n"
        "- title\n"
        "- authors (list)\n"
        "- summary (2-3 sentences in your own words, NOT a verbatim copy)\n"
        "- published (YYYY-MM-DD)\n\n"
        "Return ONLY a JSON array. Keys: arxiv_id, title, authors, summary, published."
    )

    text = _gemini_search(client, model_id, prompt, max_retries=2)
    if not text:
        # Track: tried Gemini, got nothing
        for paper in papers:
            if "sources_tried" not in paper:
                paper["sources_tried"] = []
            if "gemini_enrich_failed" not in paper["sources_tried"]:
                paper["sources_tried"].append("gemini_enrich_failed")
        return

    text = _strip_code_fences(text)
    try:
        enriched = json.loads(text)
    except json.JSONDecodeError:
        # Gemini returned bad JSON; try regex fallback
        enriched = []
        for item_match in re.finditer(r'"arxiv_id"\s*:\s*"([^"]+)"', text):
            enriched.append({"arxiv_id": item_match.group(1)})

    # Build lookup
    lookup = {}
    for e in enriched:
        aid = normalize_arxiv_id(e.get("arxiv_id", ""))
        if aid:
            lookup[aid] = e

    # Merge into papers
    for paper in papers:
        aid = normalize_arxiv_id(paper["arxiv_id"])
        
        if "sources_tried" not in paper:
            paper["sources_tried"] = []
        
        if aid in lookup:
            e = lookup[aid]
            paper["sources_tried"].append("gemini_enrich_success")
            
            if not paper["title"] and e.get("title"):
                paper["title"] = e["title"]
            
            if not paper["authors"] and e.get("authors"):
                authors = e["authors"]
                if isinstance(authors, str):
                    authors = [a.strip() for a in authors.split(",")]
                paper["authors"] = authors
            
            if not paper["abstract"] and (e.get("summary") or e.get("abstract")):
                paper["abstract"] = e.get("summary", "") or e.get("abstract", "")
            
            if not paper["published"] and e.get("published"):
                paper["published"] = e["published"]
        else:
            paper["sources_tried"].append("gemini_enrich_lookup_miss")


def search_external_evidence(query: str, max_results: int = 5) -> list[dict]:
    """Search approved academic and official sources using Gemini Google Search."""
    client, model_id = _get_gemini_client()
    prompt = (
        f"Find up to {max_results} high-quality sources for this finance research question: {query}\n\n"
        "Allowed sources only:\n"
        "- Academic: arXiv, SSRN, NBER, journal / publisher pages\n"
        "- Official: FRED, SEC, Federal Reserve, ECB, exchanges, government / central bank pages\n\n"
        "Return ONLY a JSON array. Each item must include these keys:\n"
        "- title\n"
        "- url\n"
        "- source_name\n"
        "- snippet\n"
        "- published\n"
        "- relevance_reason\n\n"
        "Do not include news sites, blogs, forums, or social media."
    )
    text = _gemini_search(client, model_id, prompt, max_retries=2)
    if not text:
        return []

    text = _strip_code_fences(text)
    try:
        raw_items = json.loads(text)
    except json.JSONDecodeError:
        return []

    normalized = []
    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        source_type = _classify_source_url(url)
        if source_type is None:
            continue
        normalized.append(
            {
                "title": str(item.get("title", "")).strip() or url,
                "url": url,
                "source_name": str(item.get("source_name", "")).strip(),
                "snippet": str(item.get("snippet", "")).strip() or str(item.get("relevance_reason", "")).strip(),
                "published": str(item.get("published", "")).strip(),
                "source_type": source_type,
                "score": 1.0,
            }
        )

    return normalized[:max_results]


# ---------------------------------------------------------------------------
# Public: download_pdf
# ---------------------------------------------------------------------------

def download_pdf(arxiv_id: str, tmp_dir: Optional[str] = None) -> str:
    """Download a paper's PDF from arXiv with exponential backoff retry.

    Args:
        arxiv_id: arXiv paper ID (e.g. "2301.00001" or "2301.00001v2")
        tmp_dir: Directory to save PDF. Defaults to system temp dir.

    Returns:
        Absolute path to the downloaded PDF file.

    Raises:
        requests.HTTPError: If download fails after all retries.
    """
    import random
    
    normalized_id = normalize_arxiv_id(arxiv_id)
    request_id = arxiv_id.strip()
    
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp(prefix="arxiv_")

    safe_id = _safe_filename(normalized_id)
    pdf_path = os.path.join(tmp_dir, f"{safe_id}.pdf")

    # Return if already cached locally
    if os.path.exists(pdf_path):
        return pdf_path

    # Retry config: exponential backoff
    max_attempts = 3
    base_delay = 1.0  # seconds
    max_delay = 5.0
    
    last_error = None
    
    for attempt in range(max_attempts):
        try:
            url = ARXIV_PDF_URL.format(arxiv_id=request_id)
            
            # Add jitter to avoid thundering herd
            if attempt > 0:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                jitter = random.uniform(0, delay * 0.1)
                time.sleep(delay + jitter)
            
            response = requests.get(url, timeout=60, stream=True)

            # If versioned URL 404s, retry without version suffix
            if response.status_code == 404 and request_id != normalized_id:
                url = ARXIV_PDF_URL.format(arxiv_id=normalized_id)
                response = requests.get(url, timeout=60, stream=True)

            response.raise_for_status()

            # Successfully got response, write PDF
            with open(pdf_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return pdf_path

        except requests.RequestException as e:
            last_error = e
            # Continue to next retry
            continue
    
    # All retries exhausted
    if last_error:
        raise requests.HTTPError(
            f"Failed to download PDF for {normalized_id} after {max_attempts} attempts: {last_error}"
        )
    else:
        raise requests.HTTPError(
            f"Failed to download PDF for {normalized_id} after {max_attempts} attempts"
        )

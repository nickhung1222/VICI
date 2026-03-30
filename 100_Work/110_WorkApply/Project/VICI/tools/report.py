"""Report tool: save structured paper records and Markdown reports to outputs/."""

import json
import os
import re
from datetime import datetime

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
PAPERS_DIR  = os.path.join(OUTPUTS_DIR, "papers")
REPORTS_DIR = os.path.join(OUTPUTS_DIR, "reports")
INDEX_PATH  = os.path.join(OUTPUTS_DIR, "paper_index.json")


def _normalize_arxiv_id(arxiv_id: str) -> str:
    """Normalize arXiv ID by stripping version suffix and whitespace."""
    if not arxiv_id:
        return ""
    normalized = arxiv_id.strip()
    normalized = re.sub(r"v\d+$", "", normalized)
    return normalized


# ---------------------------------------------------------------------------
# Knowledge base: per-paper JSON records
# ---------------------------------------------------------------------------

def save_paper_record(record: dict) -> str:
    """Save a structured JSON record for a single paper to the knowledge base.

    Args:
        record: Full structured paper record. Must contain 'arxiv_id'.

    Returns:
        Absolute path to the saved JSON file.

    Raises:
        ValueError: If 'arxiv_id' is missing from the record.
    """
    arxiv_id = _normalize_arxiv_id(record.get("arxiv_id", ""))
    if not arxiv_id:
        raise ValueError("record must contain 'arxiv_id'")

    record["arxiv_id"] = arxiv_id

    os.makedirs(PAPERS_DIR, exist_ok=True)

    safe_id = re.sub(r"[^\w.\-]", "_", arxiv_id)
    filepath = os.path.join(PAPERS_DIR, f"{safe_id}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    _update_paper_index(record)

    return filepath


def _update_paper_index(record: dict) -> None:
    """Add or update a paper entry in the global paper_index.json."""
    arxiv_id = _normalize_arxiv_id(record.get("arxiv_id", ""))

    # Load existing index or create a fresh one
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {
            "schema_version": "1.0.0",
            "last_updated": "",
            "paper_count": 0,
            "papers": {}
        }

    # Build the denormalized index entry (enough to filter without opening the full record)
    core_hypothesis = record.get("core_hypothesis", {})
    safe_arxiv_id = re.sub(r"[^\w.\-]", "_", arxiv_id)
    index["papers"][arxiv_id] = {
        "title": record.get("title", ""),
        "paper_type": record.get("paper_type", ""),
        "strategy_taxonomy_tags": record.get("strategy_taxonomy_tags", []),
        "system_modules": record.get("system_modules", []),
        "economic_mechanism": core_hypothesis.get("economic_mechanism", "") if isinstance(core_hypothesis, dict) else "",
        "session_topic": record.get("session_topic", ""),
        "extracted_at": record.get("extracted_at", ""),
        "file": f"papers/{safe_arxiv_id}.json",
    }

    index["paper_count"] = len(index["papers"])
    index["last_updated"] = datetime.now().isoformat(timespec="seconds")

    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def check_paper_exists(arxiv_id: str) -> str:
    """Check if a paper already exists in the knowledge base.

    Args:
        arxiv_id: arXiv paper ID, e.g. '2602.14670'.

    Returns:
        JSON string of existing index entry if found, or 'not_found'.
    """
    if not os.path.exists(INDEX_PATH):
        return "not_found"

    normalized_id = _normalize_arxiv_id(arxiv_id)

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index = json.load(f)

    papers = index.get("papers", {})

    entry = papers.get(normalized_id)
    if entry:
        return json.dumps(entry, ensure_ascii=False)

    # Backward compatibility for old index keys that may include version suffixes.
    for existing_id, existing_entry in papers.items():
        if _normalize_arxiv_id(existing_id) == normalized_id:
            return json.dumps(existing_entry, ensure_ascii=False)

    # Fallback to existing paper file if index is stale.
    safe_id = re.sub(r"[^\w.\-]", "_", normalized_id)
    paper_path = os.path.join(PAPERS_DIR, f"{safe_id}.json")
    if os.path.exists(paper_path):
        return json.dumps({"file": f"papers/{safe_id}.json"}, ensure_ascii=False)

    return "not_found"


# ---------------------------------------------------------------------------
# Human-readable Markdown report
# ---------------------------------------------------------------------------

def save_report(content: str, topic: str) -> str:
    """Save a Markdown summary report to the reports directory.

    Args:
        content: Markdown report content.
        topic: Research topic (used in filename).

    Returns:
        Absolute path to the saved report file.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)

    safe_topic = re.sub(r"[^\w\s\-]", "", topic).strip()
    safe_topic = re.sub(r"\s+", "_", safe_topic)[:50]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{safe_topic}_{timestamp}.md"
    filepath = os.path.join(REPORTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath

"""Report tool: save structured paper records and Markdown reports to outputs/."""

import json
import os
import re
from datetime import datetime

from tools.arxiv import _safe_filename, normalize_arxiv_id as _normalize_arxiv_id
from tools.schema_audit import (
    audit_paper_record as run_schema_audit,
    write_paper_audit_artifact,
)

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
PAPERS_DIR  = os.path.join(OUTPUTS_DIR, "papers")
REPORTS_DIR = os.path.join(OUTPUTS_DIR, "reports")
CHUNKS_DIR  = os.path.join(OUTPUTS_DIR, "chunks")
INDEX_PATH  = os.path.join(OUTPUTS_DIR, "paper_index.json")


# ---------------------------------------------------------------------------
# Knowledge base: per-paper JSON records
# ---------------------------------------------------------------------------

def _build_rag_metadata(record: dict) -> dict:
    """Build a flat metadata dict for vector DB filtering from existing record fields."""
    market = record.get("market_structure", {}) or {}
    checklist = record.get("methodology_checklist", {}) or {}
    return {
        "asset_class": market.get("asset_classes", []),
        "has_out_of_sample": checklist.get("out_of_sample") is True,
        "has_transaction_costs": checklist.get("transaction_costs_included") is True,
        "code_available": record.get("code_available", False) is True,
        "strategy_tags": record.get("strategy_taxonomy_tags", []),
    }


def save_paper_record(record: dict) -> str:
    """Save a structured JSON record for a single paper to the knowledge base.

    Args:
        record: Full structured paper record. Must contain 'arxiv_id'.

    Returns:
        Absolute path to the saved JSON file.

    Raises:
        ValueError: If 'arxiv_id' is missing from the record.
    """
    audit_result = run_schema_audit(record, apply_autofill=True, increment_call_count=False)
    record_to_save = audit_result["record"]

    arxiv_id = _normalize_arxiv_id(record_to_save.get("arxiv_id", ""))
    if not arxiv_id:
        raise ValueError("record must contain 'arxiv_id'")

    record_to_save["arxiv_id"] = arxiv_id
    record_to_save["rag_metadata"] = _build_rag_metadata(record_to_save)

    os.makedirs(PAPERS_DIR, exist_ok=True)

    safe_id = _safe_filename(arxiv_id)
    filepath = os.path.join(PAPERS_DIR, f"{safe_id}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record_to_save, f, ensure_ascii=False, indent=2)

    _update_paper_index(record_to_save)
    _save_rag_chunk(record_to_save, arxiv_id)
    write_paper_audit_artifact(
        audit_result,
        outputs_dir=OUTPUTS_DIR,
        record_path=f"papers/{safe_id}.json",
    )

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
    safe_arxiv_id = _safe_filename(arxiv_id)
    index["papers"][arxiv_id] = {
        "title": record.get("title", ""),
        "paper_type": record.get("paper_type", ""),
        "strategy_taxonomy_tags": record.get("strategy_taxonomy_tags", []),
        "system_modules": record.get("system_modules", []),
        "economic_mechanism": core_hypothesis.get("economic_mechanism", "") if isinstance(core_hypothesis, dict) else "",
        "session_topic": record.get("session_topic", ""),
        "extracted_at": record.get("extracted_at", ""),
        "file": f"papers/{safe_arxiv_id}.json",
        "rag_metadata": record.get("rag_metadata", {}),
        "market_match": record.get("market_match", False),
        "market_match_basis": record.get("market_match_basis", []),
        "multi_market_match": record.get("multi_market_match", False),
        "background_only_reason": record.get("background_only_reason", ""),
        "storage_sanitized": record.get("storage_sanitized", False),
    }

    index["paper_count"] = len(index["papers"])
    index["last_updated"] = datetime.now().isoformat(timespec="seconds")

    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _save_rag_chunk(record: dict, arxiv_id: str) -> None:
    """Generate and save a plain-text RAG chunk optimised for embedding."""
    lines = []

    title = record.get("title", "")
    if title:
        lines.append(f"Title: {title}")

    authors = record.get("authors", [])
    if authors:
        lines.append(f"Authors: {', '.join(authors)}")

    published = record.get("published", "")
    if published:
        lines.append(f"Published: {published}")

    abstract = record.get("abstract", "")
    if abstract:
        lines.append(f"Abstract: {abstract}")

    tags = record.get("strategy_taxonomy_tags", [])
    if tags:
        lines.append(f"Strategy Type: {', '.join(tags)}")

    market = record.get("market_structure", {})
    if isinstance(market, dict):
        asset_classes = market.get("asset_classes", [])
        indices = market.get("indices", [])
        timeframe = market.get("timeframe", "")
        parts = []
        if asset_classes:
            parts.append(", ".join(asset_classes))
        if indices:
            parts.append(", ".join(indices))
        if timeframe:
            parts.append(timeframe)
        if parts:
            lines.append(f"Market: {' | '.join(parts)}")

    modules = record.get("system_modules", [])
    if modules:
        lines.append(f"System Modules: {', '.join(modules)}")

    lines.append("")  # blank line before prose sections

    motivation = record.get("research_motivation", {})
    if isinstance(motivation, dict):
        gap = motivation.get("gap", "")
        if gap:
            lines.append(f"Research Gap: {gap}")
        contribution = motivation.get("claimed_contribution", "")
        if contribution:
            lines.append(f"Contribution: {contribution}")

    model = record.get("model_method", {})
    if isinstance(model, dict):
        desc = model.get("description", "")
        if desc:
            lines.append(f"\nWhat it does: {desc}")
        components = model.get("components", [])
        if components:
            lines.append(f"Key components: {', '.join(components)}")
        method_detail = model.get("method_detail", "")
        if method_detail and method_detail != "Not stated in paper":
            lines.append(f"\nMethod detail: {method_detail}")

    hypothesis = record.get("core_hypothesis", {})
    if isinstance(hypothesis, dict):
        why = hypothesis.get("why_it_works", "")
        if why:
            lines.append(f"\nWhy it works: {why}")
        mechanism = hypothesis.get("mechanism_detail", "") or hypothesis.get("economic_mechanism", "")
        if mechanism:
            lines.append(f"Economic mechanism: {mechanism}")
        decay = hypothesis.get("decay_risk", "")
        if decay:
            lines.append(f"Decay risk: {decay}")

    perf = record.get("performance", {})
    if isinstance(perf, dict):
        summary = perf.get("summary", "")
        if summary:
            lines.append(f"\nPerformance: {summary}")
        metrics = perf.get("metrics", [])
        for m in metrics:
            if isinstance(m, dict) and m.get("value") is not None:
                lines.append(f"  - {m.get('name', '')}: {m['value']} {m.get('unit', '')} ({m.get('period', '')})")

    risks = record.get("risks_limitations", [])
    if risks:
        lines.append(f"\nLimitations: {'; '.join(risks)}")

    checklist = record.get("methodology_checklist", {})
    if isinstance(checklist, dict):
        flags = [k for k, v in checklist.items() if v is True]
        if flags:
            lines.append(f"Methodology: {', '.join(flags)}")

    chunk_text = "\n".join(lines)

    os.makedirs(CHUNKS_DIR, exist_ok=True)
    safe_id = _safe_filename(arxiv_id)
    chunk_path = os.path.join(CHUNKS_DIR, f"{safe_id}.txt")
    with open(chunk_path, "w", encoding="utf-8") as f:
        f.write(chunk_text)


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
    safe_id = _safe_filename(normalized_id)
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

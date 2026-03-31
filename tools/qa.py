"""Knowledge-base retrieval and answer assembly helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from tools.report import CHUNKS_DIR, INDEX_PATH, OUTPUTS_DIR, PAPERS_DIR
from tools.relevance import evaluate_record_market_match, has_explicit_market_constraint, parse_query_constraints

ACADEMIC_DOMAINS = (
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
OFFICIAL_DOMAINS = (
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
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "does",
    "for",
    "how",
    "in",
    "is",
    "it",
    "market",
    "of",
    "on",
    "or",
    "paper",
    "papers",
    "research",
    "say",
    "the",
    "to",
    "what",
    "when",
    "which",
    "with",
}
TOP_K_LOCAL = 4
TOP_K_EXTERNAL = 3


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9&.+-]+", (text or "").lower())
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0]


def classify_url(url: str) -> Optional[str]:
    domain = _domain(url)
    if any(domain == allowed or domain.endswith(f".{allowed}") for allowed in ACADEMIC_DOMAINS):
        return "academic"
    if any(domain == allowed or domain.endswith(f".{allowed}") for allowed in OFFICIAL_DOMAINS):
        return "official"
    return None


def build_memory(previous: Optional[dict[str, Any]], question: str) -> dict[str, Any]:
    memory = dict(previous or {})
    lowered = question.lower()
    constraints = parse_query_constraints(question)

    if constraints["market_targets"]:
        memory["market"] = constraints["market_targets"][0]
    if "S&P 500" in constraints["market_targets"]:
        memory["asset_class"] = "equity_us"
    if "market timing" in lowered or "entry" in lowered or "exit" in lowered:
        memory["method_preference"] = "market_timing"
    if "regime" in lowered:
        memory["method_preference"] = "regime_detection"
    if re.search(r"\b(?:19|20)\d{2}\b", lowered):
        years = re.findall(r"\b(?:19|20)\d{2}\b", lowered)
        if years:
            memory["time_range"] = question
    memory["query_constraints"] = constraints
    memory["source_policy"] = "knowledge_base_first"
    memory["trusted_sources"] = ["academic", "official"]
    return memory


@dataclass
class Evidence:
    source_type: str
    title: str
    summary: str
    score: float
    arxiv_id: Optional[str] = None
    published: str = ""
    locator: str = ""
    url: str = ""
    citation_detail: str = ""
    evidence_basis: str = ""
    primary_evidence_eligible: bool = True
    freshness_note: str = ""
    market_match: bool = False

    def to_citation(self) -> dict[str, Any]:
        citation = {
            "source_type": self.source_type,
            "title": self.title,
            "locator": self.locator,
        }
        if self.arxiv_id:
            citation["arxiv_id"] = self.arxiv_id
        if self.url:
            citation["url"] = self.url
        if self.citation_detail:
            citation["detail"] = self.citation_detail
        return citation


def _paper_answer_eligibility(record: dict[str, Any], sidecar: Optional[dict[str, Any]]) -> bool:
    if not sidecar:
        return True
    answer_readiness = sidecar.get("answer_readiness") or {}
    if "primary_evidence_eligible" in answer_readiness:
        return bool(answer_readiness["primary_evidence_eligible"])
    return sidecar.get("summary", {}).get("error_count", 0) == 0


def _paper_text_for_scoring(record: dict[str, Any], chunk_text: str) -> str:
    parts = [
        record.get("title", ""),
        record.get("abstract", ""),
        record.get("session_topic", ""),
        " ".join(record.get("strategy_taxonomy_tags", [])),
        " ".join(record.get("system_modules", [])),
        " ".join(record.get("datasets_used", [])),
        " ".join((record.get("market_structure") or {}).get("indices", [])),
        " ".join((record.get("market_structure") or {}).get("asset_classes", [])),
        " ".join(record.get("risks_limitations", [])),
        chunk_text,
    ]
    return "\n".join(part for part in parts if part)


def _score_text(question: str, text: str, market_hint: Optional[str]) -> float:
    question_tokens = _tokenize(question)
    haystack = (text or "").lower()
    score = 0.0
    for token in question_tokens:
        if token in haystack:
            score += 1.0
    if market_hint and market_hint.lower() in haystack:
        score += 3.0
    return score


def retrieve_local_evidence(question: str, memory: Optional[dict[str, Any]] = None, limit: int = TOP_K_LOCAL) -> list[Evidence]:
    index_path = Path(INDEX_PATH)
    papers_dir = Path(PAPERS_DIR)
    chunks_dir = Path(CHUNKS_DIR)
    audits_dir = Path(OUTPUTS_DIR) / "audits" / "papers"
    if not index_path.exists() or not papers_dir.exists():
        return []

    market_hint = (memory or {}).get("market")
    constraints = (memory or {}).get("query_constraints") or parse_query_constraints(question)
    index = _load_json(index_path)
    evidence: list[Evidence] = []

    for arxiv_id, entry in (index.get("papers") or {}).items():
        paper_path = papers_dir / Path(entry.get("file", f"{arxiv_id}.json")).name
        if not paper_path.exists():
            continue
        record = _load_json(paper_path)
        chunk_path = chunks_dir / f"{paper_path.stem}.txt"
        sidecar_path = audits_dir / f"{paper_path.stem}.json"
        chunk_text = chunk_path.read_text(encoding="utf-8") if chunk_path.exists() else ""
        sidecar = _load_json(sidecar_path) if sidecar_path.exists() else None
        market_result = evaluate_record_market_match(record, constraints, chunk_text=chunk_text)
        score = _score_text(question, _paper_text_for_scoring(record, chunk_text), market_hint)
        if score <= 0:
            continue

        performance = record.get("performance") or {}
        performance_summary = performance.get("summary", "")
        summary = performance_summary or record.get("abstract", "")[:500]
        evidence.append(
            Evidence(
                source_type="knowledge_base",
                title=record.get("title", "Untitled paper"),
                summary=summary,
                score=score,
                arxiv_id=record.get("arxiv_id"),
                published=record.get("published", ""),
                locator=f"outputs/papers/{paper_path.name}",
                citation_detail=f"paper={record.get('arxiv_id', '')}",
                evidence_basis="verified_knowledge_base",
                primary_evidence_eligible=_paper_answer_eligibility(record, sidecar),
                freshness_note="Knowledge-base evidence from previously audited records.",
                market_match=(sidecar or {}).get("market_match", market_result["market_match"]),
            )
        )

    evidence.sort(key=lambda item: (item.primary_evidence_eligible, item.score, item.published), reverse=True)
    return evidence[:limit]


def should_search_externally(question: str, local_evidence: list[Evidence]) -> bool:
    if not local_evidence:
        return True
    if "latest" in question.lower() or "recent" in question.lower():
        return True
    eligible = [item for item in local_evidence if item.primary_evidence_eligible]
    if not eligible:
        return True
    if any(getattr(item, "market_match", False) for item in eligible):
        return False
    top_score = eligible[0].score
    if top_score < 3:
        return True
    return False


def normalize_external_evidence(items: list[dict[str, Any]]) -> list[Evidence]:
    normalized: list[Evidence] = []
    for item in items or []:
        url = str(item.get("url", "")).strip()
        source_type = classify_url(url)
        if source_type is None:
            continue
        normalized.append(
            Evidence(
                source_type=source_type,
                title=str(item.get("title", "")).strip() or url,
                summary=str(item.get("snippet", "")).strip(),
                score=float(item.get("score", 0) or 0),
                locator=url,
                url=url,
                published=str(item.get("published", "")).strip(),
                citation_detail=str(item.get("source_name", "")).strip(),
                evidence_basis="latest_external_supplement",
                primary_evidence_eligible=True,
                freshness_note="External supplement from approved academic or official domains; not yet ingested into the local knowledge base.",
            )
        )
    return normalized


def build_fallback_answer(
    question: str,
    local_evidence: list[Evidence],
    external_evidence: list[Evidence],
) -> dict[str, Any]:
    constraints = parse_query_constraints(question)
    has_market_constraint = has_explicit_market_constraint(constraints)
    matched_local = [item for item in local_evidence if item.primary_evidence_eligible and item.market_match]
    citations = [item.to_citation() for item in (local_evidence + external_evidence)[:4]]
    if has_market_constraint and local_evidence and not matched_local and not external_evidence:
        answer = (
            f"I found related methodology for '{question}', but not enough primary evidence that explicitly uses the requested market in experiments or datasets."
        )
        evidence_basis = "Only background-only local papers were available; none satisfied the market constraint as primary evidence."
        confidence = "low"
        freshness = "No market-matched primary evidence was available in the audited local records."
    elif local_evidence:
        top = local_evidence[0]
        answer = (
            f"Based on the current knowledge base, the strongest match for '{question}' is "
            f"'{top.title}'. {top.summary}"
        )
        evidence_basis = "Used verified knowledge-base records first."
        confidence = "medium"
        freshness = "Answer grounded primarily in audited local records."
    elif external_evidence:
        top = external_evidence[0]
        answer = (
            f"The local knowledge base did not have enough verified evidence, so I relied on an external supplement. "
            f"The strongest approved source is '{top.title}'. {top.summary}"
        )
        evidence_basis = "Used approved external supplement because local evidence was insufficient."
        confidence = "low"
        freshness = "This answer includes external supplement evidence that is not yet fully ingested into the local knowledge base."
    else:
        answer = (
            f"I could not find enough verified knowledge-base evidence to answer '{question}' confidently."
        )
        evidence_basis = "No sufficient verified evidence was available."
        confidence = "low"
        freshness = "No external supplement was available."

    return {
        "answer": answer,
        "citations": citations,
        "evidence_basis": evidence_basis,
        "freshness_note": freshness,
        "confidence": confidence,
    }


def format_evidence_for_prompt(local_evidence: list[Evidence], external_evidence: list[Evidence]) -> str:
    payload = {
        "verified_knowledge_base": [
            {
                "title": item.title,
                "arxiv_id": item.arxiv_id,
                "published": item.published,
                "summary": item.summary,
                "citation_detail": item.citation_detail,
                "primary_evidence_eligible": item.primary_evidence_eligible,
            }
            for item in local_evidence
        ],
        "latest_external_supplement": [
            {
                "title": item.title,
                "url": item.url,
                "published": item.published,
                "summary": item.summary,
                "source_type": item.source_type,
                "citation_detail": item.citation_detail,
            }
            for item in external_evidence
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

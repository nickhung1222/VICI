"""Constraint parsing, market relevance gating, and deterministic record sanitization."""

from __future__ import annotations

import copy
import re
from typing import Any

DEFAULT_QUERY_CONSTRAINTS = {
    "market_targets": [],
    "asset_targets": [],
    "task_targets": [],
}

MARKET_ALIASES = {
    "S&P 500": ("s&p 500", "sp500", "sp 500", "spy"),
    "NASDAQ 100": ("nasdaq 100", "ndx", "qqq"),
    "DJI": ("dji", "dow jones industrial average", "dow jones", "dia"),
    "FTSE 100": ("ftse 100",),
    "CSI 300": ("csi 300", "hs300"),
    "SSE50": ("sse50", "sse 50"),
}
ASSET_ALIASES = {
    "equity_us": ("us equity", "u.s. equity", "us stock", "american equity"),
    "equity_cn_a_shares": ("china a shares", "cn a shares", "china equity", "chinese equity"),
}
TASK_ALIASES = {
    "market_timing": ("market timing", "entry exit", "entry/exit", "timing signal"),
    "regime_detection": ("regime", "regime detection"),
    "portfolio_construction": ("portfolio", "allocation"),
}
RESULT_CUE_TOKENS = (
    "dataset",
    "datasets",
    "experiment",
    "experiments",
    "tested on",
    "results on",
    "using",
    "market",
    "index",
    "indices",
    "sample",
)

TOP_LEVEL_SCHEMA_KEYS = {
    "$schema_version",
    "arxiv_id",
    "title",
    "authors",
    "published",
    "pdf_url",
    "abstract",
    "extracted_at",
    "extraction_source",
    "session_topic",
    "paper_type",
    "research_motivation",
    "problem_solved",
    "model_method",
    "performance",
    "risks_limitations",
    "market_structure",
    "strategy_taxonomy_tags",
    "system_modules",
    "datasets_used",
    "code_available",
    "code_url",
    "methodology_checklist",
    "core_hypothesis",
    "related_arxiv_ids",
    "rag_metadata",
    "market_match",
    "market_match_basis",
    "multi_market_match",
    "storage_sanitized",
    "background_only_reason",
}
NESTED_ALLOWED_KEYS = {
    "research_motivation": {"gap", "prior_limitation", "claimed_contribution"},
    "problem_solved": {"problem_type", "description", "prior_approaches", "limitation_of_prior"},
    "model_method": {"name", "category", "components", "description", "method_detail"},
    "performance": {"metrics", "summary"},
    "market_structure": {"asset_classes", "indices", "timeframe", "training_period", "test_period"},
    "methodology_checklist": {
        "out_of_sample",
        "survivorship_bias_free",
        "transaction_costs_included",
        "stress_period_included",
        "parameter_sensitivity",
    },
    "core_hypothesis": {
        "why_it_works",
        "economic_mechanism",
        "mechanism_detail",
        "decay_risk",
        "testable_prediction",
    },
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _contains_alias(text: str, aliases: tuple[str, ...]) -> bool:
    normalized = _normalize_text(text)
    return any(alias in normalized for alias in aliases)


def parse_query_constraints(query: str) -> dict[str, list[str]]:
    constraints = copy.deepcopy(DEFAULT_QUERY_CONSTRAINTS)
    normalized_query = _normalize_text(query)

    for canonical, aliases in MARKET_ALIASES.items():
        if any(alias in normalized_query for alias in aliases):
            constraints["market_targets"].append(canonical)

    for canonical, aliases in ASSET_ALIASES.items():
        if any(alias in normalized_query for alias in aliases):
            constraints["asset_targets"].append(canonical)

    for canonical, aliases in TASK_ALIASES.items():
        if any(alias in normalized_query for alias in aliases):
            constraints["task_targets"].append(canonical)

    return constraints


def has_explicit_market_constraint(constraints: dict[str, Any]) -> bool:
    return bool((constraints or {}).get("market_targets"))


def _matched_markets_in_strings(values: list[str]) -> list[str]:
    matches = []
    for value in values:
        normalized_value = _normalize_text(str(value))
        for canonical, aliases in MARKET_ALIASES.items():
            if any(alias in normalized_value for alias in aliases):
                matches.append(canonical)
    return sorted(set(matches))


def _join_text(parts: list[Any]) -> str:
    return "\n".join(str(part) for part in parts if part)


def evaluate_search_candidate(paper: dict[str, Any], constraints: dict[str, Any]) -> dict[str, Any]:
    if not has_explicit_market_constraint(constraints):
        return {
            "market_match": True,
            "uncertain_market_match": False,
            "market_match_basis": ["no_explicit_market_constraint"],
            "multi_market_match": False,
            "background_only_reason": "",
        }

    query_markets = constraints.get("market_targets", [])
    title_abstract = _join_text([paper.get("title", ""), paper.get("abstract", "")])
    metadata_matches = _matched_markets_in_strings([title_abstract])
    overlapping = [market for market in metadata_matches if market in query_markets]

    if overlapping:
        return {
            "market_match": False,
            "uncertain_market_match": True,
            "market_match_basis": [f"lightweight_candidate:{market}" for market in overlapping],
            "multi_market_match": len(metadata_matches) > 1,
            "background_only_reason": "needs_fulltext_market_verification",
        }

    if metadata_matches:
        return {
            "market_match": False,
            "uncertain_market_match": False,
            "market_match_basis": [f"search_metadata_conflict:{market}" for market in metadata_matches],
            "multi_market_match": len(metadata_matches) > 1,
            "background_only_reason": "conflicting_market_in_search_metadata",
        }

    return {
        "market_match": False,
        "uncertain_market_match": True,
        "market_match_basis": [],
        "multi_market_match": False,
        "background_only_reason": "needs_fulltext_market_verification",
    }


def _extract_record_evidence_values(record: dict[str, Any], chunk_text: str = "") -> dict[str, list[str]]:
    performance = record.get("performance") if isinstance(record.get("performance"), dict) else {}
    metric_datasets = []
    for metric in performance.get("metrics", []) or []:
        if isinstance(metric, dict) and metric.get("dataset"):
            metric_datasets.append(str(metric.get("dataset")))

    market_structure = record.get("market_structure") if isinstance(record.get("market_structure"), dict) else {}
    return {
        "datasets_used": [str(item) for item in record.get("datasets_used", []) or []],
        "indices": [str(item) for item in market_structure.get("indices", []) or []],
        "metric_datasets": metric_datasets,
        "chunk_text": [chunk_text] if chunk_text else [],
        "generic_text": [record.get("abstract", ""), record.get("title", "")],
    }


def _chunk_contains_result_evidence(chunk_text: str, market_targets: list[str]) -> list[str]:
    normalized_chunk = _normalize_text(chunk_text)
    if not normalized_chunk:
        return []
    matched = []
    has_result_cue = any(token in normalized_chunk for token in RESULT_CUE_TOKENS)
    if not has_result_cue:
        return matched
    for market in market_targets:
        aliases = MARKET_ALIASES.get(market, ())
        if any(alias in normalized_chunk for alias in aliases):
            matched.append(market)
    return matched


def evaluate_record_market_match(
    record: dict[str, Any],
    constraints: dict[str, Any],
    *,
    chunk_text: str = "",
) -> dict[str, Any]:
    if not has_explicit_market_constraint(constraints):
        return {
            "market_match": True,
            "uncertain_market_match": False,
            "market_match_basis": ["no_explicit_market_constraint"],
            "multi_market_match": False,
            "background_only_reason": "",
        }

    market_targets = constraints.get("market_targets", [])
    evidence_values = _extract_record_evidence_values(record, chunk_text)

    for field_name in ("datasets_used", "indices", "metric_datasets"):
        matched = _matched_markets_in_strings(evidence_values[field_name])
        overlapping = [market for market in matched if market in market_targets]
        if overlapping:
            multi_market = len(matched) > 1
            return {
                "market_match": True,
                "uncertain_market_match": False,
                "market_match_basis": [f"{field_name}:{market}" for market in overlapping],
                "multi_market_match": multi_market,
                "background_only_reason": "",
            }

    chunk_matches = _chunk_contains_result_evidence(chunk_text, market_targets)
    if chunk_matches:
        return {
            "market_match": True,
            "uncertain_market_match": False,
            "market_match_basis": [f"result_chunk:{market}" for market in chunk_matches],
            "multi_market_match": len(chunk_matches) > 1,
            "background_only_reason": "",
        }

    generic_matches = _matched_markets_in_strings(evidence_values["generic_text"])
    overlapping = [market for market in generic_matches if market in market_targets]
    if overlapping:
        return {
            "market_match": False,
            "uncertain_market_match": True,
            "market_match_basis": [f"generic_text:{market}" for market in overlapping],
            "multi_market_match": len(generic_matches) > 1,
            "background_only_reason": "market_only_in_generic_text",
        }

    return {
        "market_match": False,
        "uncertain_market_match": False,
        "market_match_basis": [],
        "multi_market_match": False,
        "background_only_reason": "no_market_evidence_in_experiment_fields",
    }


def sanitize_record(record: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    working = copy.deepcopy(record or {})
    changes: list[dict[str, Any]] = []

    for key in list(working.keys()):
        if key not in TOP_LEVEL_SCHEMA_KEYS:
            working.pop(key, None)
            changes.append({"path": key, "action": "removed_unknown_field"})

    for key, allowed_keys in NESTED_ALLOWED_KEYS.items():
        value = working.get(key)
        if not isinstance(value, dict):
            continue
        for nested_key in list(value.keys()):
            if nested_key not in allowed_keys:
                value.pop(nested_key, None)
                changes.append({"path": f"{key}.{nested_key}", "action": "removed_unknown_field"})

    title = working.get("title")
    if isinstance(title, str):
        sanitized_title = re.sub(r"[\s}\]]+$", "", title).strip()
        if sanitized_title != title:
            working["title"] = sanitized_title
            changes.append({"path": "title", "action": "normalized_string"})

    authors = working.get("authors")
    if isinstance(authors, list):
        sanitized_authors = [str(author).strip() for author in authors if str(author).strip()]
        if sanitized_authors != authors:
            working["authors"] = sanitized_authors
            changes.append({"path": "authors", "action": "normalized_list"})

    metrics = ((working.get("performance") or {}).get("metrics") if isinstance(working.get("performance"), dict) else None)
    if isinstance(metrics, list):
        sanitized_metrics = [metric for metric in metrics if isinstance(metric, dict) and metric]
        if sanitized_metrics != metrics:
            working["performance"]["metrics"] = sanitized_metrics
            changes.append({"path": "performance.metrics", "action": "removed_invalid_items"})

    for field in ("abstract", "published", "pdf_url", "session_topic"):
        value = working.get(field)
        if isinstance(value, str):
            sanitized_value = re.sub(r"\s+", " ", value).strip()
            if sanitized_value != value:
                working[field] = sanitized_value
                changes.append({"path": field, "action": "normalized_string"})

    return working, changes

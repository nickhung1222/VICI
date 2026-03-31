"""Schema audit helpers for paper records and corpus-level reports."""

import argparse
import copy
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tools.arxiv import (
    ARXIV_PDF_URL,
    _enrich_from_arxiv_abs_page,
    _safe_filename,
    normalize_arxiv_id,
)
from tools.relevance import evaluate_record_market_match, parse_query_constraints, sanitize_record

DEFAULT_OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"
EXPECTED_METHODOLOGY_CHECKLIST_KEYS = (
    "out_of_sample",
    "survivorship_bias_free",
    "transaction_costs_included",
    "stress_period_included",
    "parameter_sensitivity",
)

_SEARCH_METADATA_CACHE: dict[str, dict[str, Any]] = {}
_AUDIT_CALL_COUNTS: dict[str, int] = {}
_LATEST_STORAGE_AUDITS: dict[str, dict[str, Any]] = {}

_ARXIV_ID_RE = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})$", re.IGNORECASE)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PDF_URL_RE = re.compile(r"^https?://arxiv\.org/pdf/([^\s?#]+?)(?:\.pdf)?/?$", re.IGNORECASE)


def reset_runtime_state() -> None:
    """Clear run-local caches used during one agent execution."""
    _SEARCH_METADATA_CACHE.clear()
    _AUDIT_CALL_COUNTS.clear()
    _LATEST_STORAGE_AUDITS.clear()


def cache_search_metadata(papers: list[dict[str, Any]]) -> None:
    """Cache metadata returned from search for later deterministic autofill."""
    for paper in papers or []:
        arxiv_id = normalize_arxiv_id(str(paper.get("arxiv_id", "")))
        if not arxiv_id:
            continue
        _SEARCH_METADATA_CACHE[arxiv_id] = {
            "arxiv_id": arxiv_id,
            "title": paper.get("title", ""),
            "authors": _coerce_string_list(paper.get("authors")),
            "published": paper.get("published", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "abstract": paper.get("abstract", ""),
            "sources_tried": list(paper.get("sources_tried", []) or []),
            "validated": paper.get("validated"),
        }


def get_cached_search_metadata(arxiv_id: str) -> dict[str, Any]:
    """Return cached search metadata for a paper if available."""
    return copy.deepcopy(_SEARCH_METADATA_CACHE.get(normalize_arxiv_id(arxiv_id), {}))


def get_last_saved_audit(arxiv_id: str) -> Optional[dict[str, Any]]:
    """Return the last saved sidecar artifact for an arXiv ID."""
    return copy.deepcopy(_LATEST_STORAGE_AUDITS.get(normalize_arxiv_id(arxiv_id)))


def format_audit_summary(audit_result: dict[str, Any]) -> str:
    """Format a compact audit summary suitable for console output."""
    summary = audit_result.get("summary", {})
    return (
        f"status={summary.get('status', 'unknown')}, "
        f"autofill={summary.get('autofill_count', 0)}, "
        f"warnings={summary.get('warning_count', 0)}, "
        f"errors={summary.get('error_count', 0)}"
    )


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _add_issue(
    issues: list[dict[str, Any]],
    severity: str,
    path: str,
    code: str,
    message: str,
    autofill_source: Optional[str] = None,
) -> None:
    issues.append(
        {
            "severity": severity,
            "path": path,
            "code": code,
            "message": message,
            "autofill_source": autofill_source,
        }
    )


def _first_non_blank(metadata_sources: list[tuple[str, dict[str, Any]]], field: str) -> tuple[Any, Optional[str]]:
    for source_name, metadata in metadata_sources:
        value = metadata.get(field)
        if field == "authors":
            value = _coerce_string_list(value)
        if not _is_blank(value):
            return value, source_name
    return None, None


def apply_deterministic_autofill(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Fill deterministic fields from cached search metadata, then arXiv abs page."""
    issues: list[dict[str, Any]] = []
    arxiv_id = normalize_arxiv_id(str(record.get("arxiv_id", "")))
    if arxiv_id:
        record["arxiv_id"] = arxiv_id

    cached_metadata = get_cached_search_metadata(arxiv_id) if arxiv_id else {}
    missing_fields = {
        "title": _is_blank(record.get("title")),
        "authors": _is_blank(record.get("authors")),
        "published": _is_blank(record.get("published")),
        "pdf_url": _is_blank(record.get("pdf_url")),
        "abstract": _is_blank(record.get("abstract")),
    }

    abs_metadata: dict[str, Any] = {}
    needs_abs_lookup = arxiv_id and any(
        missing_fields[field] and _is_blank(cached_metadata.get(field))
        for field in ("title", "authors", "published", "abstract")
    )
    if needs_abs_lookup:
        abs_metadata = _enrich_from_arxiv_abs_page(arxiv_id)

    metadata_sources = []
    if cached_metadata:
        metadata_sources.append(("search_cache", cached_metadata))
    if abs_metadata:
        metadata_sources.append(("arxiv_abs_page", abs_metadata))

    for field in ("title", "authors", "published", "abstract"):
        if not missing_fields[field]:
            continue
        value, source_name = _first_non_blank(metadata_sources, field)
        if value is None:
            continue
        record[field] = value
        _add_issue(
            issues,
            severity="info",
            path=field,
            code="autofilled_field",
            message=f"Filled '{field}' from {source_name}.",
            autofill_source=source_name,
        )

    if missing_fields["pdf_url"]:
        pdf_url = cached_metadata.get("pdf_url") or (ARXIV_PDF_URL.format(arxiv_id=arxiv_id) if arxiv_id else "")
        if pdf_url:
            source_name = "search_cache" if cached_metadata.get("pdf_url") else "normalized_arxiv_id"
            record["pdf_url"] = pdf_url
            _add_issue(
                issues,
                severity="info",
                path="pdf_url",
                code="autofilled_field",
                message=f"Filled 'pdf_url' from {source_name}.",
                autofill_source=source_name,
            )

    return issues


def _record_market_text(record: dict[str, Any]) -> str:
    market = record.get("market_structure") if isinstance(record.get("market_structure"), dict) else {}
    performance = record.get("performance") if isinstance(record.get("performance"), dict) else {}
    metric_datasets = []
    for metric in performance.get("metrics", []) or []:
        if isinstance(metric, dict) and metric.get("dataset"):
            metric_datasets.append(str(metric.get("dataset")))
    parts = [
        record.get("title", ""),
        record.get("abstract", ""),
        " ".join(record.get("datasets_used", []) or []),
        " ".join(market.get("indices", []) or []),
        " ".join(metric_datasets),
        performance.get("summary", ""),
    ]
    return "\n".join(part for part in parts if part)


def _validate_record(record: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    arxiv_id = record.get("arxiv_id", "")
    if _is_blank(arxiv_id):
        _add_issue(issues, "error", "arxiv_id", "missing_required_field", "Missing required field 'arxiv_id'.")
    elif not isinstance(arxiv_id, str) or not _ARXIV_ID_RE.match(arxiv_id):
        _add_issue(issues, "error", "arxiv_id", "invalid_format", "Field 'arxiv_id' must be a normalized arXiv ID.")

    title = record.get("title")
    if _is_blank(title):
        _add_issue(issues, "warning", "title", "missing_required_field", "Missing required field 'title'.")
    elif not isinstance(title, str):
        _add_issue(issues, "error", "title", "invalid_type", "Field 'title' must be a string.")

    authors = record.get("authors")
    if _is_blank(authors):
        _add_issue(issues, "warning", "authors", "missing_required_field", "Missing required field 'authors'.")
    elif not isinstance(authors, list) or any(not isinstance(author, str) or not author.strip() for author in authors):
        _add_issue(issues, "error", "authors", "invalid_type", "Field 'authors' must be a non-empty list of strings.")

    published = record.get("published")
    if _is_blank(published):
        _add_issue(issues, "warning", "published", "missing_required_field", "Missing required field 'published'.")
    elif not isinstance(published, str) or not _DATE_RE.match(published):
        _add_issue(issues, "error", "published", "invalid_format", "Field 'published' must use YYYY-MM-DD format.")

    pdf_url = record.get("pdf_url")
    if _is_blank(pdf_url):
        _add_issue(issues, "warning", "pdf_url", "missing_required_field", "Missing required field 'pdf_url'.")
    elif not isinstance(pdf_url, str):
        _add_issue(issues, "error", "pdf_url", "invalid_type", "Field 'pdf_url' must be a string.")
    else:
        match = _PDF_URL_RE.match(pdf_url.strip())
        if not match:
            _add_issue(issues, "error", "pdf_url", "invalid_format", "Field 'pdf_url' must point to arxiv.org/pdf/<arxiv_id>.")
        elif isinstance(arxiv_id, str) and _ARXIV_ID_RE.match(arxiv_id):
            pdf_id = normalize_arxiv_id(match.group(1))
            if pdf_id != arxiv_id:
                _add_issue(issues, "error", "pdf_url", "invalid_format", "Field 'pdf_url' must match the normalized 'arxiv_id'.")

    abstract = record.get("abstract")
    if _is_blank(abstract):
        _add_issue(issues, "warning", "abstract", "missing_required_field", "Missing required field 'abstract'.")
    elif not isinstance(abstract, str):
        _add_issue(issues, "error", "abstract", "invalid_type", "Field 'abstract' must be a string.")

    model_method = record.get("model_method")
    if not isinstance(model_method, dict):
        _add_issue(issues, "error", "model_method", "invalid_type", "Field 'model_method' must be an object.")
    else:
        method_detail = model_method.get("method_detail")
        if _is_blank(method_detail):
            _add_issue(
                issues,
                "warning",
                "model_method.method_detail",
                "missing_required_field",
                "Missing required field 'model_method.method_detail'.",
            )
        elif not isinstance(method_detail, str):
            _add_issue(
                issues,
                "error",
                "model_method.method_detail",
                "invalid_type",
                "Field 'model_method.method_detail' must be a string.",
            )

    performance = record.get("performance")
    if not isinstance(performance, dict):
        _add_issue(issues, "warning", "performance", "invalid_type", "Field 'performance' should be an object.")
    else:
        metrics = performance.get("metrics")
        if metrics is None:
            _add_issue(issues, "warning", "performance.metrics", "missing_required_field", "Missing required field 'performance.metrics'.")
        elif not isinstance(metrics, list):
            _add_issue(issues, "error", "performance.metrics", "invalid_type", "Field 'performance.metrics' must be an array.")
        else:
            for index, metric in enumerate(metrics):
                path = f"performance.metrics[{index}]"
                if not isinstance(metric, dict):
                    _add_issue(issues, "error", path, "invalid_type", "Each performance metric must be an object.")
                    continue
                raw_text = metric.get("raw_text")
                if _is_blank(raw_text):
                    _add_issue(
                        issues,
                        "warning",
                        f"{path}.raw_text",
                        "missing_required_field",
                        "Missing required field 'raw_text' for performance metric.",
                    )
                elif not isinstance(raw_text, str):
                    _add_issue(
                        issues,
                        "error",
                        f"{path}.raw_text",
                        "invalid_type",
                        "Field 'raw_text' must be a string.",
                    )
        summary = performance.get("summary")
        if isinstance(summary, str) and summary.strip() and isinstance(metrics, list) and not metrics and re.search(r"\d", summary):
            _add_issue(
                issues,
                "warning",
                "performance.metrics",
                "summary_metrics_mismatch",
                "Performance summary mentions numeric findings but 'performance.metrics' is empty.",
            )

    checklist = record.get("methodology_checklist")
    if not isinstance(checklist, dict):
        _add_issue(
            issues,
            "warning",
            "methodology_checklist",
            "invalid_type",
            "Field 'methodology_checklist' should be an object.",
        )
        return

    for key in EXPECTED_METHODOLOGY_CHECKLIST_KEYS:
        if key not in checklist:
            _add_issue(
                issues,
                "warning",
                f"methodology_checklist.{key}",
                "missing_required_field",
                f"Missing required field 'methodology_checklist.{key}'.",
            )
            continue
        value = checklist[key]
        if value is not None and not isinstance(value, bool):
            _add_issue(
                issues,
                "error",
                f"methodology_checklist.{key}",
                "invalid_type",
                f"Field 'methodology_checklist.{key}' must be true, false, or null.",
            )

    paper_type = record.get("paper_type")
    if paper_type in {"trading_strategy", "hybrid"}:
        market = record.get("market_structure") if isinstance(record.get("market_structure"), dict) else {}
        datasets = record.get("datasets_used")
        has_market = bool((market or {}).get("asset_classes")) or bool((market or {}).get("indices"))
        has_dataset = isinstance(datasets, list) and len(datasets) > 0
        if not has_market:
            _add_issue(
                issues,
                "warning",
                "market_structure",
                "missing_empirical_market_context",
                "Empirical paper is missing market context needed for answer grounding.",
            )
        if not has_dataset:
            _add_issue(
                issues,
                "warning",
                "datasets_used",
                "missing_empirical_dataset_context",
                "Empirical paper is missing dataset context needed for answer grounding.",
            )


def _build_answer_readiness(
    issues: list[dict[str, Any]],
    *,
    market_match: bool,
    background_only_reason: str,
) -> dict[str, Any]:
    blocking_codes = {
        "invalid_format",
        "invalid_type",
        "summary_metrics_mismatch",
        "missing_empirical_market_context",
        "missing_empirical_dataset_context",
    }
    missing_method_detail = any(
        issue["path"] == "model_method.method_detail" and issue["severity"] != "info"
        for issue in issues
    )
    blocking_issue_codes = sorted(
        {
            issue["code"]
            for issue in issues
            if issue["severity"] == "error" or issue["code"] in blocking_codes
        }
    )
    if not market_match and background_only_reason:
        blocking_issue_codes.append("market_constraint_mismatch")
    primary_evidence_eligible = not blocking_issue_codes and not missing_method_detail and market_match
    return {
        "primary_evidence_eligible": primary_evidence_eligible,
        "background_only": not primary_evidence_eligible,
        "blocking_issue_codes": sorted(set(blocking_issue_codes)),
        "background_only_reason": background_only_reason if not primary_evidence_eligible else "",
    }


def audit_paper_record(
    record: dict[str, Any],
    *,
    apply_autofill: bool = True,
    increment_call_count: bool = False,
) -> dict[str, Any]:
    """Audit one paper record and optionally autofill deterministic metadata."""
    sanitized_changes: list[dict[str, Any]] = []
    working_record = copy.deepcopy(record or {})
    issues: list[dict[str, Any]] = []

    working_record, sanitized_changes = sanitize_record(working_record)
    for change in sanitized_changes:
        _add_issue(
            issues,
            "info",
            change["path"],
            "sanitized_field",
            f"Sanitized field '{change['path']}' via deterministic cleaner.",
            autofill_source="sanitizer",
        )

    arxiv_id = normalize_arxiv_id(str(working_record.get("arxiv_id", "")))
    if arxiv_id:
        working_record["arxiv_id"] = arxiv_id

    if apply_autofill:
        issues.extend(apply_deterministic_autofill(working_record))

    _validate_record(working_record, issues)

    constraints = parse_query_constraints(str(working_record.get("session_topic", "")))
    market_result = evaluate_record_market_match(
        working_record,
        constraints,
        chunk_text=_record_market_text(working_record),
    )
    if constraints.get("market_targets") and not market_result["market_match"]:
        severity = "warning" if market_result["uncertain_market_match"] else "error"
        _add_issue(
            issues,
            severity,
            "market_match",
            "market_constraint_mismatch",
            "Paper does not provide enough experiment-level evidence for the query's market constraint.",
        )

    if increment_call_count and arxiv_id:
        _AUDIT_CALL_COUNTS[arxiv_id] = _AUDIT_CALL_COUNTS.get(arxiv_id, 0) + 1

    audit_call_count = _AUDIT_CALL_COUNTS.get(arxiv_id, 0)
    llm_repair_attempted = audit_call_count > 1
    repair_limit_reached = audit_call_count >= 2
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    info_count = sum(1 for issue in issues if issue["severity"] == "info")

    if error_count:
        status = "errors"
    elif warning_count:
        status = "warnings"
    else:
        status = "clean"

    needs_llm_repair = (warning_count > 0 or error_count > 0) and not repair_limit_reached
    answer_readiness = _build_answer_readiness(
        issues,
        market_match=market_result["market_match"],
        background_only_reason=market_result["background_only_reason"],
    )

    working_record["market_match"] = market_result["market_match"]
    working_record["market_match_basis"] = market_result["market_match_basis"]
    working_record["multi_market_match"] = market_result["multi_market_match"]
    working_record["storage_sanitized"] = bool(sanitized_changes)
    working_record["background_only_reason"] = answer_readiness["background_only_reason"]

    return {
        "arxiv_id": arxiv_id,
        "record": working_record,
        "issues": issues,
        "status": status,
        "autofill_applied": info_count > 0,
        "autofill_fields": [issue["path"] for issue in issues if issue["severity"] == "info"],
        "llm_repair_attempted": llm_repair_attempted,
        "repair_limit_reached": repair_limit_reached,
        "needs_llm_repair": needs_llm_repair,
        "audit_call_count": audit_call_count,
        "storage_sanitized": bool(sanitized_changes),
        "market_match": market_result["market_match"],
        "market_match_basis": market_result["market_match_basis"],
        "multi_market_match": market_result["multi_market_match"],
        "background_only_reason": answer_readiness["background_only_reason"],
        "summary": {
            "status": status,
            "issue_count": len(issues),
            "info_count": info_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "autofill_count": info_count,
        },
        "answer_readiness": answer_readiness,
    }


def write_paper_audit_artifact(
    audit_result: dict[str, Any],
    *,
    outputs_dir: Optional[str] = None,
    record_path: Optional[str] = None,
) -> str:
    """Persist the final audit result for one paper as a sidecar JSON file."""
    outputs_root = Path(outputs_dir) if outputs_dir else DEFAULT_OUTPUTS_DIR
    audits_dir = outputs_root / "audits" / "papers"
    audits_dir.mkdir(parents=True, exist_ok=True)

    arxiv_id = audit_result.get("arxiv_id", "") or "unknown"
    safe_id = _safe_filename(arxiv_id or "unknown")
    artifact = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "arxiv_id": arxiv_id,
        "record_path": record_path,
        "status": audit_result.get("status", "unknown"),
        "summary": audit_result.get("summary", {}),
        "issues": audit_result.get("issues", []),
        "autofill_applied": audit_result.get("autofill_applied", False),
        "autofill_fields": audit_result.get("autofill_fields", []),
        "llm_repair_attempted": audit_result.get("llm_repair_attempted", False),
        "repair_limit_reached": audit_result.get("repair_limit_reached", False),
        "answer_readiness": audit_result.get("answer_readiness", {}),
        "storage_sanitized": audit_result.get("storage_sanitized", False),
        "market_match": audit_result.get("market_match", False),
        "market_match_basis": audit_result.get("market_match_basis", []),
        "multi_market_match": audit_result.get("multi_market_match", False),
        "background_only_reason": audit_result.get("background_only_reason", ""),
    }

    artifact_path = audits_dir / f"{safe_id}.json"
    with artifact_path.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)

    if arxiv_id:
        _LATEST_STORAGE_AUDITS[arxiv_id] = artifact

    return str(artifact_path)


def audit_corpus(records_dir: str) -> dict[str, Any]:
    """Audit all paper JSON files in a directory without applying autofill."""
    records_path = Path(records_dir)
    paper_results = []
    path_counter: Counter[str] = Counter()
    code_counter: Counter[str] = Counter()
    severity_counter: Counter[str] = Counter()

    for paper_path in sorted(records_path.glob("*.json")):
        with paper_path.open("r", encoding="utf-8") as f:
            record = json.load(f)

        result = audit_paper_record(record, apply_autofill=False, increment_call_count=False)
        entry = {
            "arxiv_id": result.get("arxiv_id") or paper_path.stem,
            "file": paper_path.name,
            "status": result["status"],
            "summary": result["summary"],
            "issues": result["issues"],
            "answer_readiness": result.get("answer_readiness", {}),
            "market_match": result.get("market_match", False),
            "background_only_reason": result.get("background_only_reason", ""),
        }
        paper_results.append(entry)

        for issue in result["issues"]:
            path_counter[issue["path"]] += 1
            code_counter[issue["code"]] += 1
            severity_counter[issue["severity"]] += 1

    papers_with_issues = sum(1 for result in paper_results if result["summary"]["warning_count"] or result["summary"]["error_count"])

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "records_dir": str(records_path),
        "paper_count": len(paper_results),
        "summary": {
            "papers_with_issues": papers_with_issues,
            "info_count": severity_counter["info"],
            "warning_count": severity_counter["warning"],
            "error_count": severity_counter["error"],
            "primary_evidence_ready": sum(
                1
                for result in paper_results
                if result.get("answer_readiness", {}).get("primary_evidence_eligible") is True
            ),
            "market_match_ready": sum(1 for result in paper_results if result.get("market_match") is True),
        },
        "issue_counts": {
            "by_path": dict(sorted(path_counter.items())),
            "by_code": dict(sorted(code_counter.items())),
        },
        "papers": paper_results,
    }


def write_corpus_audit_report(records_dir: str, output_path: Optional[str] = None) -> str:
    """Write a corpus-level audit report to disk."""
    report = audit_corpus(records_dir)
    records_path = Path(records_dir)
    destination = Path(output_path) if output_path else records_path.parent / "audits" / "corpus_schema_audit.json"
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return str(destination)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for corpus schema audit."""
    parser = argparse.ArgumentParser(description="Audit paper JSON files and write a corpus schema report.")
    parser.add_argument("records_dir", help="Directory containing paper JSON files, e.g. outputs/papers")
    args = parser.parse_args(argv)

    report_path = write_corpus_audit_report(args.records_dir)
    print(f"Corpus schema audit saved to: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

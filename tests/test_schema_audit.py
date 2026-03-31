import json
from pathlib import Path

from tools import schema_audit


def make_record(**overrides):
    record = {
        "$schema_version": "1.0.0",
        "arxiv_id": "2406.18394",
        "title": "AlphaForge",
        "authors": ["Alice", "Bob"],
        "published": "2024-06-26",
        "pdf_url": "https://arxiv.org/pdf/2406.18394",
        "abstract": "Original abstract",
        "extracted_at": "2026-03-30T00:00:00Z",
        "extraction_source": "full_text",
        "session_topic": "alpha mining",
        "paper_type": "methodology",
        "research_motivation": {
            "gap": "Gap",
            "prior_limitation": "Limitation",
            "claimed_contribution": "Contribution",
        },
        "problem_solved": {
            "problem_type": "alpha_discovery",
            "description": "Description",
            "prior_approaches": ["Baseline"],
            "limitation_of_prior": "Weakness",
        },
        "model_method": {
            "name": "AlphaForge",
            "category": "machine_learning",
            "components": ["Encoder"],
            "description": "Input: data -> Process: model -> Output: signal",
            "method_detail": "Detailed explanation of the methodology.",
        },
        "performance": {
            "metrics": [
                {
                    "name": "IC",
                    "value": 0.05,
                    "unit": "ratio",
                    "context": "Test set",
                    "dataset": "CSI300",
                    "period": "2021-01-01 to 2024-12-31",
                    "is_out_of_sample": True,
                    "net_of_costs": False,
                    "raw_text": "IC = 0.05",
                }
            ],
            "summary": "Summary",
        },
        "risks_limitations": ["Risk"],
        "market_structure": {
            "asset_classes": ["equity_cn_a_shares"],
            "indices": ["CSI300"],
            "timeframe": "daily",
            "training_period": "2019-01-01 to 2020-12-31",
            "test_period": "2021-01-01 to 2024-12-31",
        },
        "strategy_taxonomy_tags": ["factor_investing"],
        "system_modules": ["signal_generation"],
        "datasets_used": ["CSI300"],
        "code_available": False,
        "code_url": None,
        "methodology_checklist": {
            "out_of_sample": True,
            "survivorship_bias_free": None,
            "transaction_costs_included": False,
            "stress_period_included": False,
            "parameter_sensitivity": None,
        },
        "core_hypothesis": {
            "why_it_works": "Why",
            "economic_mechanism": "market_inefficiency",
            "mechanism_detail": "Mechanism",
            "decay_risk": "Crowding",
            "testable_prediction": "Prediction",
        },
        "related_arxiv_ids": [],
    }
    record.update(overrides)
    return record


def setup_function():
    schema_audit.reset_runtime_state()


def teardown_function():
    schema_audit.reset_runtime_state()


def test_audit_autofills_abstract_from_search_cache():
    schema_audit.cache_search_metadata(
        [
            {
                "arxiv_id": "2406.18394",
                "title": "AlphaForge",
                "authors": ["Alice", "Bob"],
                "published": "2024-06-26",
                "pdf_url": "https://arxiv.org/pdf/2406.18394",
                "abstract": "Cached abstract from search",
            }
        ]
    )
    record = make_record(abstract="")

    result = schema_audit.audit_paper_record(record, apply_autofill=True, increment_call_count=True)

    assert result["record"]["abstract"] == "Cached abstract from search"
    assert result["summary"]["warning_count"] == 0
    assert any(
        issue["path"] == "abstract" and issue["autofill_source"] == "search_cache"
        for issue in result["issues"]
    )


def test_audit_allows_one_repair_pass_for_method_detail():
    record = make_record(
        model_method={
            "name": "AlphaForge",
            "category": "machine_learning",
            "components": ["Encoder"],
            "description": "Input: data -> Process: model -> Output: signal",
            "method_detail": "",
        }
    )

    first = schema_audit.audit_paper_record(record, apply_autofill=True, increment_call_count=True)

    assert first["needs_llm_repair"] is True
    assert first["llm_repair_attempted"] is False
    assert any(
        issue["path"] == "model_method.method_detail" and issue["code"] == "missing_required_field"
        for issue in first["issues"]
    )

    repaired = first["record"]
    repaired["model_method"]["method_detail"] = "Repaired method detail."
    second = schema_audit.audit_paper_record(repaired, apply_autofill=True, increment_call_count=True)

    assert second["needs_llm_repair"] is False
    assert second["llm_repair_attempted"] is True
    assert second["repair_limit_reached"] is True
    assert not any(
        issue["path"] == "model_method.method_detail" and issue["severity"] != "info"
        for issue in second["issues"]
    )


def test_audit_reports_bad_formats_without_blocking_output():
    record = make_record(
        arxiv_id="bad id",
        published="2024/06/26",
        pdf_url="https://example.com/not-arxiv.pdf",
    )

    result = schema_audit.audit_paper_record(record, apply_autofill=False, increment_call_count=False)
    issues = {(issue["path"], issue["code"]) for issue in result["issues"]}

    assert ("arxiv_id", "invalid_format") in issues
    assert ("published", "invalid_format") in issues
    assert ("pdf_url", "invalid_format") in issues
    assert result["status"] == "errors"


def test_corpus_audit_reports_fixture_gaps(tmp_path):
    records_dir = tmp_path / "papers"
    records_dir.mkdir()

    bad_record = make_record(
        abstract="",
        model_method={
            "name": "AlphaForge",
            "category": "machine_learning",
            "components": ["Encoder"],
            "description": "Input: data -> Process: model -> Output: signal",
            "method_detail": "",
        },
    )
    good_record = make_record(
        arxiv_id="2402.08233",
        title="Good Paper",
        pdf_url="https://arxiv.org/pdf/2402.08233",
        performance={
            "metrics": [
                {
                    "name": "IC",
                    "value": 0.05,
                    "unit": "ratio",
                    "context": "Test set",
                    "dataset": "CSI300",
                    "period": "2021-01-01 to 2024-12-31",
                    "is_out_of_sample": True,
                    "net_of_costs": False,
                    "raw_text": "IC = 0.05",
                }
            ],
            "summary": "IC improved to 0.05.",
        },
    )

    (records_dir / "2406.18394.json").write_text(json.dumps(bad_record), encoding="utf-8")
    (records_dir / "2402.08233.json").write_text(json.dumps(good_record), encoding="utf-8")

    report = schema_audit.audit_corpus(str(records_dir))

    assert report["paper_count"] == 2
    assert report["summary"]["papers_with_issues"] == 1
    assert report["summary"]["primary_evidence_ready"] == 1
    assert report["issue_counts"]["by_path"]["abstract"] == 1
    assert report["issue_counts"]["by_path"]["model_method.method_detail"] == 1

    sample_paper = next(paper for paper in report["papers"] if paper["arxiv_id"] == "2406.18394")
    sample_paths = {issue["path"] for issue in sample_paper["issues"]}
    assert "abstract" in sample_paths
    assert "model_method.method_detail" in sample_paths
    assert sample_paper["answer_readiness"]["primary_evidence_eligible"] is False

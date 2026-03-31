import json
from pathlib import Path

from tools import schema_audit
from tools import report


def make_record(**overrides):
    record = {
        "$schema_version": "1.0.0",
        "arxiv_id": "2406.18394",
        "title": "AlphaForge",
        "authors": ["Alice", "Bob"],
        "published": "2024-06-26",
        "pdf_url": "https://arxiv.org/pdf/2406.18394",
        "abstract": "",
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
        "performance": {"metrics": [], "summary": "Summary"},
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


def test_save_paper_record_writes_sidecar_and_autofills(monkeypatch, tmp_path):
    outputs_dir = tmp_path / "outputs"
    monkeypatch.setattr(report, "OUTPUTS_DIR", str(outputs_dir))
    monkeypatch.setattr(report, "PAPERS_DIR", str(outputs_dir / "papers"))
    monkeypatch.setattr(report, "REPORTS_DIR", str(outputs_dir / "reports"))
    monkeypatch.setattr(report, "CHUNKS_DIR", str(outputs_dir / "chunks"))
    monkeypatch.setattr(report, "INDEX_PATH", str(outputs_dir / "paper_index.json"))

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

    record_path = Path(report.save_paper_record(make_record()))
    sidecar_path = outputs_dir / "audits" / "papers" / "2406.18394.json"

    assert record_path.exists()
    assert sidecar_path.exists()

    with record_path.open("r", encoding="utf-8") as f:
        saved_record = json.load(f)
    with sidecar_path.open("r", encoding="utf-8") as f:
        sidecar = json.load(f)

    assert saved_record["abstract"] == "Cached abstract from search"
    assert saved_record["rag_metadata"]["has_out_of_sample"] is True
    assert sidecar["record_path"] == "papers/2406.18394.json"
    assert sidecar["autofill_applied"] is True
    assert "abstract" in sidecar["autofill_fields"]
    assert sidecar["answer_readiness"]["primary_evidence_eligible"] is True
    assert sidecar["market_match"] is True
    assert sidecar["storage_sanitized"] is False

import json
from pathlib import Path

import agent
from tools import qa


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_retrieve_local_evidence_prefers_matching_market(monkeypatch, tmp_path):
    outputs = tmp_path / "outputs"
    papers_dir = outputs / "papers"
    chunks_dir = outputs / "chunks"
    audits_dir = outputs / "audits" / "papers"
    chunks_dir.mkdir(parents=True)
    audits_dir.mkdir(parents=True)

    index = {
        "schema_version": "1.0.0",
        "paper_count": 2,
        "papers": {
            "2310.07110": {
                "title": "Valuation Duration of the Stock Market",
                "file": "papers/2310.07110.json",
            },
            "2312.05756": {
                "title": "CSI 300 Timing Paper",
                "file": "papers/2312.05756.json",
            },
        },
    }
    sp500_record = {
        "arxiv_id": "2310.07110",
        "title": "Valuation Duration of the Stock Market",
        "abstract": "S&P 500 valuation duration and market timing.",
        "published": "2023-10-11",
        "performance": {"summary": "Sharpe ratio of 0.58.", "metrics": [{"raw_text": "Sharpe ratio of 0.58"}]},
        "session_topic": "S&P 500 market timing",
        "strategy_taxonomy_tags": ["factor_investing"],
        "system_modules": ["entry_exit", "regime_detection"],
        "datasets_used": ["S&P 500"],
        "market_structure": {"asset_classes": ["equity_us"], "indices": ["S&P 500"]},
    }
    csi_record = {
        "arxiv_id": "2312.05756",
        "title": "CSI 300 Timing Paper",
        "abstract": "CSI 300 timing using HMM.",
        "published": "2023-12-10",
        "performance": {"summary": "Works on CSI 300.", "metrics": [{"raw_text": "CSI 300 result"}]},
        "session_topic": "CSI 300 timing",
        "strategy_taxonomy_tags": ["machine_learning"],
        "system_modules": ["entry_exit"],
        "datasets_used": ["CSI 300"],
        "market_structure": {"asset_classes": ["equity_cn_a_shares"], "indices": ["CSI 300"]},
    }
    eligible_sidecar = {"answer_readiness": {"primary_evidence_eligible": True}}

    _write_json(outputs / "paper_index.json", index)
    _write_json(papers_dir / "2310.07110.json", sp500_record)
    _write_json(papers_dir / "2312.05756.json", csi_record)
    (chunks_dir / "2310.07110.txt").write_text("S&P 500 entry exit timing", encoding="utf-8")
    (chunks_dir / "2312.05756.txt").write_text("CSI 300 timing", encoding="utf-8")
    _write_json(audits_dir / "2310.07110.json", eligible_sidecar)
    _write_json(audits_dir / "2312.05756.json", eligible_sidecar)

    monkeypatch.setattr(qa, "INDEX_PATH", str(outputs / "paper_index.json"))
    monkeypatch.setattr(qa, "PAPERS_DIR", str(papers_dir))
    monkeypatch.setattr(qa, "CHUNKS_DIR", str(chunks_dir))
    monkeypatch.setattr(qa, "OUTPUTS_DIR", str(outputs))

    memory = qa.build_memory({}, "When is S&P 500 suitable for market timing entry and exit?")
    evidence = qa.retrieve_local_evidence("When is S&P 500 suitable for market timing entry and exit?", memory)

    assert evidence
    assert evidence[0].arxiv_id == "2310.07110"
    assert evidence[0].source_type == "knowledge_base"
    assert evidence[0].market_match is True


def test_ask_uses_external_supplement_when_local_is_insufficient(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(agent, "_generate_answer_with_gemini", lambda question, memory, local_evidence, external_evidence: {
        "answer": "Short answer",
        "citations": [item.to_citation() for item in external_evidence],
        "evidence_basis": "Used external supplement",
        "freshness_note": "External supplement used",
        "confidence": "low",
    })
    monkeypatch.setattr(agent, "retrieve_local_evidence", lambda question, memory: [])
    monkeypatch.setattr(agent, "search_external_evidence", lambda question, max_results=3: [
        {
            "title": "Federal Reserve source",
            "url": "https://www.federalreserve.gov/example",
            "source_name": "Federal Reserve",
            "snippet": "Official regime discussion.",
            "published": "2026-03-31",
            "source_type": "official",
            "score": 1.0,
        }
    ])

    result = agent.ask("What official evidence discusses macro regime timing?")

    assert result["evidence_basis"] == "Used approved external supplement because local evidence was insufficient."
    assert result["citations"][0]["source_type"] == "official"
    assert result["session_memory"]["source_policy"] == "knowledge_base_first"


def test_finalize_answer_payload_overrides_model_citations_with_stable_metadata():
    local = [
        qa.Evidence(
            source_type="knowledge_base",
            title="Valuation Duration of the Stock Market",
            summary="Sharpe ratio improved.",
            score=5.0,
            arxiv_id="2310.07110",
            locator="outputs/papers/2310.07110.json",
            primary_evidence_eligible=True,
        )
    ,
        qa.Evidence(
            source_type="knowledge_base",
            title="Lower relevance paper",
            summary="Not really about S&P 500.",
            score=1.0,
            arxiv_id="2312.05756",
            locator="outputs/papers/2312.05756.json",
            primary_evidence_eligible=True,
        )
    ]
    payload = {
        "answer": "Model answer.",
        "citations": [{"source_type": "academic", "title": "Wrong citation"}],
        "evidence_basis": "Model-defined basis",
        "freshness_note": "Model-defined freshness",
        "confidence": "low",
    }

    final = agent._finalize_answer_payload(
        "What does the knowledge base say about S&P 500 market timing?",
        payload,
        local,
        [],
    )

    assert final["citations"][0]["source_type"] == "knowledge_base"
    assert final["citations"][0]["arxiv_id"] == "2310.07110"
    assert len(final["citations"]) == 1
    assert final["freshness_note"] == "Answer grounded primarily in audited local records."
    assert final["confidence"] == "high"


def test_fallback_answer_reports_insufficient_market_matched_evidence():
    local = [
        qa.Evidence(
            source_type="knowledge_base",
            title="Background methodology paper",
            summary="Mentions S&P 500 but tests CSI 300.",
            score=4.0,
            arxiv_id="2312.05756",
            locator="outputs/papers/2312.05756.json",
            primary_evidence_eligible=False,
            market_match=False,
        )
    ]

    result = qa.build_fallback_answer("S&P 500 market timing", local, [])

    assert "not enough primary evidence" in result["answer"]
    assert result["confidence"] == "low"

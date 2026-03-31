import agent
from tools import qa


def test_chat_triggers_research_when_local_evidence_is_insufficient(monkeypatch):
    local_calls = {"count": 0}

    def fake_retrieve(question, memory):
        local_calls["count"] += 1
        if local_calls["count"] == 1:
            return []
        return [
            qa.Evidence(
                source_type="knowledge_base",
                title="Valuation Duration of the Stock Market",
                summary="Sharpe ratio improved.",
                score=5.0,
                arxiv_id="2310.07110",
                locator="outputs/papers/2310.07110.json",
                primary_evidence_eligible=True,
                market_match=True,
            )
        ]

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(agent, "retrieve_local_evidence", fake_retrieve)
    monkeypatch.setattr(agent, "should_search_externally", lambda question, local_evidence: False)
    monkeypatch.setattr(agent, "research", lambda topic, max_papers=3: "/tmp/report.md")
    monkeypatch.setattr(
        agent,
        "_generate_answer_payload",
        lambda question, memory, local_evidence, external_evidence: {
            "answer": "Grounded answer",
            "citations": [item.to_citation() for item in local_evidence],
            "evidence_basis": "Used verified knowledge-base records first.",
            "freshness_note": "Answer grounded primarily in audited local records.",
            "confidence": "high",
        },
    )

    result = agent.chat("Find papers about S&P 500 market timing")

    assert result["research_triggered"] is True
    assert result["report_path"] == "/tmp/report.md"
    assert result["citations"][0]["arxiv_id"] == "2310.07110"
    assert result["session_memory"]["last_report_path"] == "/tmp/report.md"


def test_chat_skips_research_when_local_market_matched_evidence_exists(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    local = [
        qa.Evidence(
            source_type="knowledge_base",
            title="Valuation Duration of the Stock Market",
            summary="Sharpe ratio improved.",
            score=5.0,
            arxiv_id="2310.07110",
            locator="outputs/papers/2310.07110.json",
            primary_evidence_eligible=True,
            market_match=True,
        )
    ]
    monkeypatch.setattr(agent, "retrieve_local_evidence", lambda question, memory: local)
    monkeypatch.setattr(agent, "should_search_externally", lambda question, local_evidence: False)
    monkeypatch.setattr(
        agent,
        "_generate_answer_payload",
        lambda question, memory, local_evidence, external_evidence: {
            "answer": "Grounded answer",
            "citations": [item.to_citation() for item in local_evidence],
            "evidence_basis": "Used verified knowledge-base records first.",
            "freshness_note": "Answer grounded primarily in audited local records.",
            "confidence": "high",
        },
    )

    called = {"research": False}

    def fail_if_called(topic, max_papers=3):
        called["research"] = True
        raise AssertionError("research should not be called")

    monkeypatch.setattr(agent, "research", fail_if_called)

    result = agent.chat("What does the knowledge base say about S&P 500 market timing?")

    assert result["research_triggered"] is False
    assert called["research"] is False

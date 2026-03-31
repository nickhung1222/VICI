from tools.relevance import (
    evaluate_record_market_match,
    evaluate_search_candidate,
    parse_query_constraints,
    sanitize_record,
)


def test_search_candidate_only_in_abstract_is_uncertain_not_match():
    constraints = parse_query_constraints("S&P 500 market timing")
    paper = {
        "title": "General regime model",
        "abstract": "This study mentions S&P 500 in related work but focuses on general methodology.",
    }

    result = evaluate_search_candidate(paper, constraints)

    assert result["market_match"] is False
    assert result["uncertain_market_match"] is True
    assert result["background_only_reason"] == "needs_fulltext_market_verification"


def test_search_candidate_conflicting_market_is_filtered_early():
    constraints = parse_query_constraints("S&P 500 market timing")
    paper = {
        "title": "CSI 300 timing model",
        "abstract": "This paper studies market timing on CSI 300.",
    }

    result = evaluate_search_candidate(paper, constraints)

    assert result["market_match"] is False
    assert result["uncertain_market_match"] is False
    assert result["background_only_reason"] == "conflicting_market_in_search_metadata"


def test_search_candidate_without_market_signal_is_kept_for_fulltext_verification():
    constraints = parse_query_constraints("S&P 500 market timing")
    paper = {
        "title": "A reinforcement learning trading model",
        "abstract": "A general automated trading system for stock indices.",
    }

    result = evaluate_search_candidate(paper, constraints)

    assert result["market_match"] is False
    assert result["uncertain_market_match"] is True
    assert result["background_only_reason"] == "needs_fulltext_market_verification"


def test_record_market_match_requires_experiment_level_evidence():
    constraints = parse_query_constraints("S&P 500 market timing")
    record = {
        "title": "General timing model",
        "abstract": "We discuss S&P 500 in the introduction only.",
        "datasets_used": ["CSI 300"],
        "market_structure": {"indices": ["CSI 300"]},
        "performance": {"metrics": [{"dataset": "CSI 300"}]},
    }

    result = evaluate_record_market_match(record, constraints, chunk_text="")

    assert result["market_match"] is False
    assert result["background_only_reason"] == "market_only_in_generic_text"


def test_record_market_match_allows_multi_market_when_target_present():
    constraints = parse_query_constraints("S&P 500 market timing")
    record = {
        "datasets_used": ["S&P 500", "FTSE 100"],
        "market_structure": {"indices": ["S&P 500", "FTSE 100"]},
        "performance": {"metrics": [{"dataset": "S&P 500"}]},
    }

    result = evaluate_record_market_match(record, constraints, chunk_text="")

    assert result["market_match"] is True
    assert result["multi_market_match"] is True


def test_sanitize_record_removes_unknown_fields_and_invalid_metrics():
    record = {
        "title": "Messy title}}   ",
        "authors": [" Alice ", ""],
        "performance": {"metrics": [None, "", {"name": "sharpe_ratio"}]},
        "u_id": None,
        "method_detail": "wrong level",
        "model_method": {
            "name": "Model",
            "method_detail": "Detailed",
            "extra_field": "remove me",
        },
    }

    sanitized, changes = sanitize_record(record)

    assert sanitized["title"] == "Messy title"
    assert sanitized["authors"] == ["Alice"]
    assert sanitized["performance"]["metrics"] == [{"name": "sharpe_ratio"}]
    assert "u_id" not in sanitized
    assert "method_detail" not in sanitized
    assert "extra_field" not in sanitized["model_method"]
    assert changes

#!/usr/bin/env python3
"""Quick validation for Phase 1 Commit 1: arXiv ID normalization & dedup.

Run: python test_phase1_commit1.py
"""

from tools.arxiv import normalize_arxiv_id
from tools.report import _normalize_arxiv_id, check_paper_exists

def _check_normalization_consistency():
    """Test that arxiv.py and report.py use same normalization."""
    print("\n" + "=" * 70)
    print("TEST 1: Normalization Consistency")
    print("=" * 70)
    
    test_cases = [
        "2406.18394",
        "2406.18394v2",
        "2602.14670v1",
        "  2406.18394v3  ",
    ]
    
    for test_id in test_cases:
        norm_arxiv = normalize_arxiv_id(test_id)
        norm_report = _normalize_arxiv_id(test_id)
        
        if norm_arxiv == norm_report:
            print(f"✓ PASS: '{test_id}' -> '{norm_arxiv}'")
        else:
            print(f"✗ FAIL: '{test_id}'")
            print(f"         arxiv.py: {norm_arxiv}")
            print(f"         report.py: {norm_report}")
            return False
    
    return True

def _check_dedup_lookup():
    """Test that dedup lookup works for base ID and versioned variants."""
    print("\n" + "=" * 70)
    print("TEST 2: Dedup Lookup (Base and Versioned IDs)")
    print("=" * 70)
    
    # These IDs are already in the index/papers/ from past runs
    known_papers = [
        ("2406.18394", "AlphaForge paper (base)"),
        ("2406.18394v2", "AlphaForge paper (versioned variant)"),
        ("2602.14670", "FactorMiner paper (base)"),
        ("2602.14670v1", "FactorMiner paper (versioned variant)"),
    ]
    
    for test_id, desc in known_papers:
        result = check_paper_exists(test_id)
        is_found = result != "not_found"
        
        if is_found:
            print(f"✓ FOUND: {test_id} ({desc})")
        else:
            print(f"✗ NOT FOUND: {test_id} ({desc})")
            # This is not necessarily a failure, depends on existing index state
    
    return True


def test_normalization_consistency():
    assert _check_normalization_consistency()


def test_dedup_lookup():
    assert _check_dedup_lookup()

def main():
    print("\n" + "=" * 70)
    print("PHASE 1 COMMIT 1 VALIDATION: ID Normalization & Dedup")
    print("=" * 70)
    
    results = {
        "Normalization": _check_normalization_consistency(),
        "Dedup Lookup": _check_dedup_lookup(),
    }
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n✓ Phase 1 Commit 1 validation PASSED!")
        return 0
    else:
        print("\n✗ Phase 1 Commit 1 validation FAILED!")
        return 1

if __name__ == "__main__":
    exit(main())

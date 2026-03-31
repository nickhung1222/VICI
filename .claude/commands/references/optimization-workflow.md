# Quantitative Research & Optimization Workflow

Use this reference to identify where the current research sits in the development lifecycle and what the natural next research step is.

---

## The Research Lifecycle

```
Stage 1: Hypothesis
    ↓
Stage 2: Data & Universe
    ↓
Stage 3: Signal Construction
    ↓
Stage 4: In-Sample Backtest
    ↓
Stage 5: Out-of-Sample Validation
    ↓
Stage 6: Portfolio Integration
    ↓
Stage 7: Paper Trading / Live Monitoring
    ↓
Stage 8: Ongoing Optimization
```

**Key principle**: Never optimize with out-of-sample data. Each stage's decisions must be fixed before seeing the next stage's data.

---

## Stage 1: Hypothesis Formation

**Goal**: Establish a theoretically grounded reason the signal should work *before* looking at data.

| Approach | Description | Risk |
|---|---|---|
| Theory-first | Economic/behavioral rationale before data mining | Low overfitting risk |
| Data-first | Mine data, find patterns, then rationalize | High overfitting risk |
| Literature replication | Replicate known signal in new market/period | Medium — checks robustness |

**Research gap signal**: If a paper has no clear theoretical motivation (just "we found this works"), the result is likely data-mined. Look for papers that explain *why* the alpha should persist.

**Search keywords**: "risk premium theory", "behavioral finance anomaly explanation", "limits to arbitrage"

---

## Stage 2: Universe & Data

**Decisions that must be made before signal construction**:

- Asset universe (index constituents vs all-listed vs liquidity-filtered)
- Rebalancing frequency (daily / weekly / monthly)
- Look-back period for signals
- Benchmark for performance measurement

**Common issues**:
- Universe definition changes alpha dramatically (small-cap vs large-cap)
- Using current index constituents introduces survivorship bias
- Point-in-time fundamental data vs as-reported data

**Search keywords**: "universe selection backtest", "liquidity filter equity", "survivorship bias correction"

---

## Stage 3: Signal Construction

**Key decisions**:

| Decision | Options | Research keywords |
|---|---|---|
| Raw signal definition | Price-based, fundamental, alternative | "factor definition", "signal construction" |
| Cross-sectional normalization | Z-score, rank, percentile | "cross-sectional normalization", "winsorization" |
| Orthogonalization | Remove market/sector exposure | "factor orthogonalization", "residual momentum" |
| Signal combination | Equal weight, IC-weighted, ML blend | "alpha combination", "IC-weighted signals" |
| Decay/smoothing | EMA, half-life, signal age | "signal decay half-life", "exponential decay alpha" |

---

## Stage 4 & 5: Backtesting & Validation

See `research-methodology.md` for full detail on backtest traps and validation methods.

**Minimum threshold before proceeding to Stage 6**:
- Out-of-sample Sharpe ≥ 0.5 (net of costs)
- t-stat ≥ 2.5 on OOS returns
- Strategy survives 2000, 2008, 2020 stress periods

---

## Stage 6: Portfolio Integration

**How to add a new strategy to an existing portfolio**:

### Marginal Sharpe contribution
A new strategy adds value if its standalone Sharpe and correlation with existing portfolio satisfies:
```
IC_new > Sharpe_existing × correlation(new, portfolio)
```

### Correlation-based selection
Target strategies with correlation < 0.3 to existing strategies. Use diversification ratio as portfolio quality metric.

**Research keywords**: "portfolio of strategies diversification", "strategy correlation", "multi-strategy allocation"

### Dynamic weighting
Weight strategies by:
- Rolling Sharpe (trailing 12-24 months)
- Regime-conditional (momentum weight up in trending, mean reversion up in ranging)
- Equal weight as robust baseline

**Search keywords**: "dynamic strategy allocation", "regime-conditional weighting", "strategy ensemble"

---

## Stage 7 & 8: Live Monitoring & Ongoing Optimization

### Alpha decay monitoring
Track rolling out-of-sample IC (Information Coefficient). If IC drops toward 0, the signal is decaying.

**Signs of alpha decay**:
- IC trending down over 12+ months
- Increasing correlation with other known factors
- Academic publication of the strategy (crowding accelerates after)

**Research keywords**: "alpha decay monitoring", "factor crowding", "post-publication alpha decay"

### Re-optimization triggers
- Performance drawdown exceeds 2× historical average drawdown → investigate
- Regime change (e.g., rate hike cycle begins) → re-examine signal assumptions
- New data source available → test as supplementary signal

---

## Alpha Decay Lifecycle

```
Discovery (academic/practitioner)
    ↓ typically 2-5 years before publication
Academic Publication
    ↓ crowding accelerates
Crowding / Capacity Shrinkage
    ↓ return per unit risk declines
Residual Alpha (only accessible with better execution or in less crowded markets)
    ↓
Full Decay (if too crowded)
```

**Implication for literature research**: Papers published 5+ years ago may have decayed strategies. Look for:
1. Recent papers testing whether the original alpha still holds
2. Papers identifying which versions of the strategy are less crowded
3. Papers applying the strategy in markets where it hasn't been tested (e.g., Taiwan)

**Search keywords**: "factor crowding equity", "post-publication alpha decay", "factor capacity"

---

## Optimization Methods

| Method | Use case | Risk |
|---|---|---|
| Grid search | Small parameter space | High overfitting for large grids |
| Bayesian optimization | Large parameter space, expensive evaluation | Requires careful stopping criteria |
| Genetic algorithm | Non-convex, combinatorial optimization | Overfitting to noise |
| Robust optimization | Minimize worst-case scenario | Conservative, may sacrifice mean performance |

**Rule of thumb**: For every free parameter, you need at least 252 additional days of out-of-sample data to have meaningful evidence.

**Search keywords**: "Bayesian optimization trading strategy", "robust portfolio optimization", "parameter stability"

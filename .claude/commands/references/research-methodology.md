# Quantitative Research Methodology

Use this reference to evaluate the rigor of papers in a report and identify methodological gaps that warrant follow-up research.

---

## Backtest Traps (Red Flags)

### 1. Look-ahead Bias (前視偏差)
Using data that would not have been available at the time of the trade.

- **Examples**: Using end-of-day price to enter at open; using point-in-time data without accounting for publication lag; using revised economic data instead of first-release
- **Red flag**: Paper doesn't specify exact data timestamps or rebalancing point
- **Search for**: "point-in-time data", "look-ahead bias backtest", "real-time data survivorship"

### 2. Survivorship Bias (生存偏差)
Using a universe that excludes companies that went bankrupt, were delisted, or were acquired.

- **Impact**: Overstates returns by 1-2% annually in equity strategies
- **Red flag**: Paper uses current index constituents as the historical universe
- **Search for**: "survivorship bias equity", "delisted stocks", "CRSP survivorship"

### 3. Overfitting / Data Snooping (過擬合 / 資料探勘偏差)
Parameters are tuned to fit historical data, producing inflated in-sample performance.

- **Harvey et al. (2016)** framework: a t-stat threshold of 3.0 (not 2.0) should be required given multiple testing
- **Red flag**: Paper tests many parameter combinations but reports only the best; no out-of-sample test
- **Search for**: "multiple testing correction factor", "Bonferroni correction alpha", "Harvey Liu Zhu", "p-hacking finance"

### 4. Transaction Cost Underestimation
Ignoring bid-ask spread, market impact, borrow costs, and taxes.

- **Typical costs**: Equity bid-ask 0.1-0.5%; borrow 0.5-3% for shorts; Taiwan securities tax 0.3%
- **Red flag**: Paper reports "net of commissions" but ignores market impact; high-turnover strategy with no TCA
- **Search for**: "transaction costs alpha decay", "net of trading costs", "market impact equity"

### 5. Regime Dependence
Strategy works only in specific market conditions tested in the sample.

- **Red flag**: Sample period is a long bull market; no stress-period analysis
- **Search for**: "out-of-sample performance", "regime robustness", "crisis period performance"

---

## Validation Methods

### Walk-Forward Analysis
Train on a rolling window, test on the next period, roll forward.

- Closest to real-world deployment
- Requires sufficient data: typically 3× training window for test
- **Search for**: "walk-forward optimization", "rolling window backtest"

### Purged Cross-Validation (López de Prado)
Cross-validation adapted for financial time series to prevent leakage.

- Removes observations near the fold boundary (purging) and adds an embargo period
- Standard k-fold CV is invalid for financial data due to serial correlation
- **Search for**: "purged cross-validation", "combinatorial purged CV", "López de Prado CPCV"

### Combinatorial Purged Cross-Validation (CPCV)
Generates multiple non-overlapping test paths from a single dataset.

- Provides a distribution of backtest paths, not just one
- Better estimate of out-of-sample Sharpe distribution
- **Search for**: "combinatorial purged cross-validation", "backtest overfitting probability"

---

## Performance Metrics

| Metric | Formula | Notes |
|---|---|---|
| Sharpe Ratio | (R - Rf) / σ | Annualize by √252 (daily). Standard but assumes normality. |
| Sortino Ratio | (R - Rf) / σ_downside | Only penalizes downside vol. Better for skewed returns. |
| Calmar Ratio | Annualized Return / Max Drawdown | Intuitive. Sensitive to single worst drawdown. |
| Information Ratio | Alpha / Tracking Error | Measures skill relative to benchmark. |
| Deflated Sharpe Ratio (DSR) | Adjusts SR for multiple testing and non-normality | Bailey & López de Prado (2014). Best single metric. |
| Maximum Drawdown | Peak-to-trough decline | Must report: depth, duration, and recovery time. |
| Win Rate + Profit Factor | Win% × avg_win / (loss% × avg_loss) | Important for high-frequency strategies. |

**Critical**: Always ask whether Sharpe is before or after transaction costs. A Sharpe of 1.5 pre-cost on a high-turnover strategy may be 0.3 after costs.

---

## Statistical Testing

### T-test for Mean Return
- H₀: mean return = 0
- Required t-stat: ≥ 3.0 per Harvey et al. (2016) given typical search processes
- **Search for**: "statistical significance factor", "t-statistic threshold"

### Bootstrap Methods
- Resample returns to build empirical distribution
- Block bootstrap preserves autocorrelation structure
- **Search for**: "bootstrap Sharpe ratio", "block bootstrap returns"

### Multiple Testing Correction
When testing many strategies/parameters, false discovery rate rises.
- Bonferroni (conservative): α_adjusted = α / n_tests
- Benjamini-Hochberg: controls false discovery rate
- **Search for**: "multiple hypothesis testing finance", "false discovery rate alpha"

---

## Minimum Evidence Standards

A paper is considered methodologically sound if it meets:

- [ ] Out-of-sample test period ≥ 20% of total data
- [ ] Survivorship-bias-free universe
- [ ] Reports performance after realistic transaction costs
- [ ] t-stat ≥ 2.5 on out-of-sample Sharpe
- [ ] Stress period included (2000 dot-com, 2008 GFC, 2020 COVID)
- [ ] Parameter sensitivity analysis (does performance hold nearby?)

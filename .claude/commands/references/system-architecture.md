# Quantitative System Architecture

A complete quant trading system has 6 interconnected modules. Use this reference to identify which modules a paper addresses and what's missing from the research.

---

## Module 1: Signal Generation

**What it does**: Converts raw data into tradeable alpha signals.

| Component | Description | Research keywords |
|---|---|---|
| Factor construction | Define and compute raw signals (momentum, value, etc.) | "factor construction", "signal engineering" |
| Feature engineering | Transform signals (normalize, winsorize, orthogonalize) | "cross-sectional normalization", "signal winsorization" |
| Alpha combination | Combine multiple signals (IC-weighted, regression-based) | "alpha combination", "signal blending", "ensemble alpha" |
| Decay modeling | How quickly a signal loses predictive power | "signal decay", "alpha half-life", "autocorrelation returns" |

**Common gaps in research**: Most papers build signals in isolation. Missing: how does the signal combine with others? What's its correlation with existing factors?

---

## Module 2: Portfolio Construction

**What it does**: Translates signals into target weights.

| Method | Description | Research keywords |
|---|---|---|
| Equal weight | Simple, robust baseline | "equal weight portfolio" |
| Signal-proportional | Weight ∝ signal strength | "signal weighting" |
| Risk parity | Equal risk contribution per asset | "risk parity", "equal risk contribution", "ERC" |
| Mean-variance optimization (MVO) | Maximize Sharpe, minimize variance | "mean variance optimization", "Markowitz" |
| Black-Litterman | Bayesian blend of views with market prior | "Black-Litterman", "portfolio views" |
| Minimum variance | Minimize portfolio vol, no return input | "minimum variance portfolio", "global minimum variance" |
| Maximum diversification | Maximize diversification ratio | "maximum diversification", "diversification ratio" |

**Key insight**: MVO is unstable with noisy inputs. Risk parity and minimum variance are more robust out-of-sample.

---

## Module 3: Entry / Exit Mechanics

**What it does**: Determines exactly when and how to trade.

| Component | Description | Research keywords |
|---|---|---|
| Entry threshold | Signal must exceed a level before entering | "entry threshold", "signal filter" |
| Exit rules | Time-based, signal reversal, stop-loss/take-profit | "exit strategy", "stop loss optimization" |
| Trailing stop | Dynamic stop that follows price | "trailing stop", "dynamic stop loss" |
| Rebalancing frequency | Daily/weekly/monthly rebalance tradeoffs | "rebalancing frequency", "turnover optimization" |
| Position sizing | Fixed fractional, Kelly criterion, vol-scaled | "position sizing", "Kelly criterion", "fractional Kelly" |

**Common trap**: Papers often report signal performance without modeling entry/exit mechanics. Real performance degrades significantly.

---

## Module 4: Risk Management

**What it does**: Prevents catastrophic losses and controls exposure.

| Component | Description | Research keywords |
|---|---|---|
| Portfolio-level VaR/CVaR | Tail risk measurement | "conditional value at risk", "portfolio CVaR" |
| Factor exposure limits | Cap exposure to known risk factors (market beta, sector) | "factor exposure", "beta neutralization" |
| Drawdown control | Reduce position size after drawdown | "drawdown control", "drawdown-based position sizing" |
| Correlation monitoring | Detect when portfolio becomes concentrated | "portfolio concentration", "effective N" |
| Stress testing | Test portfolio under historical scenarios | "stress testing", "historical simulation" |

---

## Module 5: Execution

**What it does**: Minimizes market impact and slippage when trading.

| Component | Description | Research keywords |
|---|---|---|
| TWAP | Time-weighted average price execution | "TWAP execution", "time weighted" |
| VWAP | Volume-weighted average price execution | "VWAP execution", "volume weighted" |
| Slippage model | Estimate market impact cost | "market impact model", "price impact", "Almgren-Chriss" |
| Transaction cost analysis (TCA) | Post-trade performance measurement | "transaction cost analysis", "implementation shortfall" |
| Optimal execution | Minimize expected shortfall | "optimal execution", "optimal liquidation" |

**Taiwan-specific**: Given 10% daily price limit and high retail participation, impact costs can be unusually high for small/mid cap.

---

## Module 6: Market Regime Detection

**What it does**: Identifies the current market environment to apply the right strategy.

| Regime type | Methods | Research keywords |
|---|---|---|
| Trend vs range-bound | ADX, Hurst exponent, moving average slope | "trend detection", "Hurst exponent", "market regime" |
| Volatility regime | VIX level, realized vol percentile, GARCH regime | "volatility regime", "high volatility regime" |
| Bull/bear | Drawdown from peak, moving average crossover | "bear market detection", "market state" |
| Hidden Markov Model | Statistical regime switching | "hidden Markov model returns", "regime switching HMM" |
| Macro regime | Interest rate cycle, credit spread | "macro regime", "risk-on risk-off" |

**Key use**: Regime detection allows **strategy switching** — momentum works in trending regimes, mean reversion in ranging regimes.

---

## Module Dependency Map

```
Market Data
    │
    ▼
Signal Generation ──────────────────────────────┐
    │                                            │
    ▼                                            │
Regime Detection ─→ (gate: is regime suitable?) │
    │                                            │
    ▼                                            │
Portfolio Construction ←────────────────────────┘
    │
    ▼
Risk Management ─→ (adjust weights if limits breached)
    │
    ▼
Entry/Exit Mechanics
    │
    ▼
Execution
    │
    ▼
Performance Attribution ─→ (feedback to Signal Generation)
```

---

## Common Research Gaps by Module

| Module | Most common research gap |
|---|---|
| Signal Generation | Signal combination and turnover control |
| Portfolio Construction | Out-of-sample robustness of optimization |
| Entry/Exit | Real execution with slippage vs theoretical |
| Risk Management | Tail risk and drawdown in extreme events |
| Execution | Market impact in less liquid markets |
| Regime Detection | Regime label uncertainty and transition lag |

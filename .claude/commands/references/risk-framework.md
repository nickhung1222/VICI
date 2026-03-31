# Risk Framework for Quantitative Strategies

Use this reference to systematically evaluate the risks of strategies found in research reports and to identify risk-related literature gaps.

---

## Four Risk Categories

### 1. Market Risk (市場風險)

Risk from adverse price movements in the underlying assets.

| Risk type | Measurement | Research keywords |
|---|---|---|
| Directional / beta exposure | Beta to market index, factor exposures | "market beta exposure", "factor risk decomposition" |
| Tail risk | CVaR at 95%/99%, skewness, kurtosis | "tail risk equity", "conditional VaR", "extreme value theory" |
| Drawdown risk | Max drawdown, drawdown duration, recovery time | "maximum drawdown", "drawdown distribution" |
| Volatility risk | Realized vol, vol-of-vol | "volatility clustering", "GARCH risk" |
| Correlation breakdown | Correlation increases in crises (diversification fails when needed) | "correlation crisis", "contagion risk", "correlation breakdown 2008" |

**Taiwan-specific**: 10% daily price limit creates gap risk at open after limit-hit days. Model this explicitly.

---

### 2. Model Risk (模型風險)

Risk that the model is wrong or stops working.

| Risk type | Description | Research keywords |
|---|---|---|
| Non-stationarity | Statistical relationships change over time | "non-stationarity financial returns", "structural break" |
| Regime change | Strategy designed for one regime fails in another | "regime change strategy failure", "structural break backtest" |
| Overfitting | Model too tuned to historical data | "backtest overfitting", "deflated Sharpe ratio" |
| Estimation error | Input parameters (expected returns, covariance) are noisy | "estimation error portfolio", "Ledoit-Wolf shrinkage" |
| Crowding | When too many investors trade the same signal | "factor crowding", "crowded trades", "strategy capacity" |

**Key question for any paper**: Does the strategy include a mechanism to detect when the model is no longer valid?

---

### 3. Execution Risk (執行風險)

Risk from the process of actually trading.

| Risk type | Description | Research keywords |
|---|---|---|
| Slippage | Price moves before order is filled | "slippage model", "market impact", "price impact equity" |
| Liquidity risk | Cannot trade at desired size without moving price | "liquidity risk", "Amihud illiquidity", "kyle lambda" |
| Short squeeze | Borrow recalled, forced to cover | "short squeeze", "short selling risk", "borrow cost" |
| Operational risk | Technology failure, data errors, connectivity | "algorithmic trading failure", "flash crash" |
| Capacity | Strategy alpha decays as AUM grows | "strategy capacity", "alpha capacity", "scalability trading" |

**Taiwan-specific**: Many mid/small cap stocks have NT$50M–200M daily volume. A strategy managing >NT$100M needs careful capacity analysis.

---

### 4. Regulatory Risk (監管風險)

Risk from changes in rules, restrictions, or enforcement.

| Risk type | Taiwan context | Research keywords |
|---|---|---|
| Short-selling ban | TWSE has imposed temporary short-selling bans during crises | "short selling ban", "short sale restriction effect" |
| Price limit changes | Limit could be tightened (e.g., to ±5%) | "price limit effect", "circuit breaker equity" |
| Tax changes | STT rate has changed historically | "transaction tax impact trading", "securities tax equity" |
| Margin requirement changes | TWSE adjusts margin rates for specific stocks | "margin requirement change", "margin constraint equity" |

---

## Drawdown Analysis Framework

A complete drawdown analysis should report:

| Metric | Definition |
|---|---|
| Maximum Drawdown (MDD) | Largest peak-to-trough decline |
| Average Drawdown | Mean of all drawdown periods |
| Drawdown Duration | Average time from peak to trough |
| Recovery Time | Average time from trough back to new peak |
| Pain Index | Average drawdown over entire period |
| Ulcer Index | RMS of drawdown (sensitive to prolonged drawdowns) |

**Red flag**: Paper only reports MDD without duration or recovery time. A -20% drawdown lasting 3 months is very different from one lasting 3 years.

---

## Stress Testing Checklist

A strategy should be tested against these historical periods:

| Period | Dates | Character |
|---|---|---|
| Asian Financial Crisis | 1997–1998 | EM currency and equity crash |
| Dot-com bubble burst | 2000–2002 | Tech/growth collapse |
| Global Financial Crisis | 2008–2009 | Credit freeze, correlation spike |
| European Debt Crisis | 2011–2012 | Sovereign risk, bank stress |
| Taiwan Specific: 921 Earthquake | 1999 | Local market closure and volatility |
| COVID crash | Feb–Mar 2020 | Fastest -30% ever, liquidity freeze |
| 2022 Rate hike cycle | 2022 | Bond/equity simultaneous decline |

**Minimum**: Strategy must show performance in at least 2008 GFC and 2020 COVID.

---

## Tail Risk Protection Methods

| Method | Description | Research keywords |
|---|---|---|
| Volatility targeting | Scale position size inversely with realized vol | "volatility targeting", "constant volatility strategy" |
| Protective put / tail hedge | Buy OTM puts on index as portfolio insurance | "tail hedging", "portfolio insurance", "long volatility" |
| Trend filter | Exit when market is in downtrend (simple MA filter) | "trend filter equity", "200-day moving average filter" |
| Diversification across regimes | Hold strategies that work in different regimes | "crisis alpha", "managed futures CTA" |
| Cash/de-risking rules | Reduce exposure at circuit breaker triggers | "drawdown-based position sizing", "risk parity" |

---

## Risk-Adjusted Performance: Hierarchy of Metrics

From least to most rigorous for evaluating a strategy:

1. **Raw return** — almost meaningless without risk context
2. **Sharpe Ratio** — assumes normal returns, penalizes upside vol equally
3. **Sortino Ratio** — better for skewed strategies
4. **Calmar Ratio** — intuitive but sensitive to single worst drawdown
5. **Deflated Sharpe Ratio (DSR)** — adjusts for multiple testing, non-normality, and sample length. Best single metric.
6. **Full distribution analysis** — return distribution, tail behavior, regime-conditional returns

**Research gap signal**: If a paper only reports Sharpe and annual return, its risk assessment is incomplete. Suggest searching for papers that report full drawdown analysis and tail statistics.

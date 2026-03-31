# Strategy Taxonomy — Quantitative Trading Strategies

Use this reference to identify where a strategy sits in the landscape, what adjacent areas haven't been explored, and what search keywords to use for follow-up literature.

---

## 1. Momentum / Trend Following

**Core idea**: Assets that recently outperformed continue to outperform (cross-sectional); trends persist over time (time-series).

| Sub-strategy | Key mechanisms | arXiv keywords |
|---|---|---|
| Cross-sectional momentum | Relative strength ranking, portfolio rebalancing | "cross-sectional momentum", "relative strength", "momentum factor" |
| Time-series momentum (TSMOM) | Each asset vs its own past return | "time-series momentum", "trend following", "TSMOM" |
| Momentum crash | Reversal during bear market rebounds | "momentum crash", "momentum reversal", "momentum risk" |
| Dual momentum | Combining absolute + relative momentum | "dual momentum", "absolute momentum" |
| Vol-scaled momentum | Momentum signal scaled by volatility | "volatility scaling", "risk-adjusted momentum" |

**Key interactions**: Momentum + volatility targeting → smoother equity curve. Momentum + value → diversified factor portfolio.

**Decay risk**: One of the most crowded factors post-2010. Check for post-publication decay.

---

## 2. Mean Reversion

**Core idea**: Prices revert toward a long-run equilibrium.

| Sub-strategy | Key mechanisms | arXiv keywords |
|---|---|---|
| Statistical arbitrage | Cointegrated pairs or baskets | "statistical arbitrage", "pairs trading", "cointegration" |
| Ornstein-Uhlenbeck | OU process for spread modeling | "Ornstein-Uhlenbeck", "mean reversion speed", "spread trading" |
| Intraday reversal | Short-term price reversal at open/close | "intraday reversal", "opening auction", "price reversal" |
| Earnings mean reversion | Post-announcement drift reversal | "post-earnings drift", "earnings reversal" |

**Key interactions**: Mean reversion strategies fail in trending regimes — need regime detection.

---

## 3. Factor Investing

**Core idea**: Systematic exposure to risk premia or behavioral anomalies.

| Factor | Definition | arXiv keywords |
|---|---|---|
| Value | Price/book, P/E, EV/EBITDA | "value factor", "value premium", "book-to-market" |
| Size | Small-cap premium | "size factor", "small cap premium", "SMB" |
| Quality | High ROE, low leverage, stable earnings | "quality factor", "profitability factor", "gross profitability" |
| Low volatility | Low-vol stocks outperform on risk-adjusted basis | "low volatility anomaly", "minimum variance", "betting against beta" |
| Liquidity | Illiquid stocks earn premium | "liquidity premium", "illiquidity", "Amihud ratio" |
| Earnings revision | Analyst estimate revisions | "earnings revision", "SUE", "analyst forecast revision" |

**Multi-factor**: Combining factors with low correlation improves Sharpe. Key papers: Fama-French 5-factor, AQR Quality Minus Junk.

---

## 4. Statistical Arbitrage / Market Neutral

**Core idea**: Long/short positions to isolate a spread while hedging market exposure.

| Sub-strategy | arXiv keywords |
|---|---|
| Equity market neutral | "equity market neutral", "long short equity" |
| ETF arbitrage | "ETF arbitrage", "ETF premium discount" |
| Index arbitrage | "index arbitrage", "futures basis" |
| Convertible arbitrage | "convertible bond arbitrage" |

---

## 5. Volatility Strategies

**Core idea**: Trade implied vs realized volatility spread, or volatility as an asset class.

| Sub-strategy | arXiv keywords |
|---|---|
| Variance risk premium (VRP) | "variance risk premium", "VIX futures", "volatility risk premium" |
| Dispersion trading | "dispersion trading", "correlation trading" |
| Vol targeting | "volatility targeting", "constant volatility" |
| GARCH-based signals | "GARCH volatility forecast", "realized volatility prediction" |

---

## 6. Machine Learning Strategies

**Core idea**: Use ML to discover non-linear relationships in financial data.

| Approach | arXiv keywords |
|---|---|
| Tree-based (XGBoost, RF) | "gradient boosting stock prediction", "random forest alpha" |
| Neural networks / LSTM | "LSTM stock prediction", "deep learning trading" |
| Transformer / attention | "transformer financial forecasting", "attention mechanism returns" |
| Reinforcement learning | "reinforcement learning trading", "deep RL portfolio" |
| NLP / sentiment | "sentiment analysis stock returns", "news alpha", "NLP factor" |

**Warning**: ML strategies have high overfitting risk. Always require out-of-sample evidence.

---

## 7. Alternative Data

**Core idea**: Non-traditional data sources generate alpha before they become mainstream.

| Data source | arXiv keywords |
|---|---|
| Satellite imagery | "satellite data alpha", "satellite retail traffic" |
| Social media | "Twitter sentiment stock", "Reddit WallStreetBets", "social media momentum" |
| Credit card transactions | "credit card data alpha", "consumer spending signal" |
| Supply chain networks | "supply chain network alpha", "firm network" |
| ESG / sustainability | "ESG alpha", "sustainable investing returns", "ESG factor" |

---

## 8. High-Frequency / Market Microstructure

**Core idea**: Exploit short-term price formation processes at intraday or tick level.

| Sub-strategy | arXiv keywords |
|---|---|
| Market making | "market making optimal", "Avellaneda Stoikov" |
| Order flow imbalance | "order flow imbalance", "order book alpha" |
| Latency arbitrage | "latency arbitrage", "co-location" |
| Intraday patterns | "intraday seasonality", "time-of-day effect" |

---

## Strategy Relationship Map

```
Momentum ─── tends to fail in ──→ Mean Reversion regimes
    │
    └── pairs with ──→ Volatility Targeting (smoother returns)

Factor Investing ──→ combine low-correlation factors ──→ Multi-factor

ML Strategies ──→ feature engineering from ──→ all of the above

Alt Data ──→ early signal, decays fast ──→ needs frequent update
```

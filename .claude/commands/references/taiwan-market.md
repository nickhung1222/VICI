# Taiwan Market — Structure, Rules & Research Context

Use this reference when the research topic involves Taiwan equities (TWSE/TPEx) or when suggesting market-specific follow-up queries.

---

## Trading Regulations

### Price Limits
- **Daily price limit**: ±10% from previous close (TWSE and TPEx)
- **Impact on strategies**: Limits tail risk but causes price discontinuities; momentum strategies must account for limit-hit days
- **Exception**: First-day listed stocks have ±60% limit for ETFs, no limit for new IPOs on day 1

### Settlement
- **T+2**: Equity trades settle 2 business days after execution
- **Impact**: Short-term strategies must account for capital being tied up 2 days

### Day Trading (當沖)
- Allowed on: Listed stocks with prior-day turnover ≥ NT$200M
- Buy and sell same stock same day (offsetting settlement)
- **Securities transaction tax**: 0.15% per side for day trades (reduced from 0.3%)
- **Margin requirement**: 9:1 leverage cap for margin accounts

### Short Selling (融券/借券)
- **Margin short (融券)**: Allowed on eligible stocks (meet volume/price criteria). Prohibited on stocks hitting lower price limit.
- **Stock lending (借券)**: OTC borrow through TWSE lending system; borrow rates vary 0.5%–5%+
- **Restrictions**: Cannot short on down-tick (uptick rule applies)
- **Impact**: Limits pure short-selling strategies; statistical arbitrage with long/short difficult

### Lot Size
- **Standard lot (張)**: 1,000 shares per lot
- **Odd lot (零股)**: Minimum 1 share, traded in a separate session (13:40–14:30)
- **Impact**: Small-cap strategies may face lot-size granularity issues

---

## Tax Structure

| Tax | Rate | Notes |
|---|---|---|
| Securities Transaction Tax (證交稅) | 0.3% of sale value | Applied to seller only; no capital gains tax |
| Day trade STT | 0.15% | Reduced rate for intraday round-trips |
| Dividend withholding | 21% for foreign investors | Affects dividend capture strategies |
| No capital gains tax | — | Taiwan abolished capital gains tax in 2016 |

**Key implication**: Transaction cost floor is 0.3% per round-trip (0.15% for day trades). Any strategy with Sharpe < 1.5 pre-cost likely unprofitable after tax + commissions.

---

## Market Structure

### Exchanges
- **TWSE (臺灣證券交易所)**: Main board, ~900 listed companies
- **TPEx (證券櫃檯買賣中心)**: OTC market, smaller/growth companies, ~800 companies
- **TAIFEX**: Futures and options exchange (TXF index futures, individual stock options)

### Participant Composition (approximate)
- Retail investors: ~60% of trading volume
- Domestic institutional (SITC, insurance, funds): ~15%
- Foreign institutional investors (FINI): ~25% of holdings, ~20% of volume

**Implication**: High retail participation creates:
- Stronger behavioral biases (overreaction, herding)
- Higher short-term reversals
- Stronger earnings announcement effects

### Market Hours
- Pre-market: 08:30–09:00 (auction only)
- Regular session: 09:00–13:30
- Closing auction: 13:30 (random close 13:30–13:33)
- Odd-lot session: 13:40–14:30

### Liquidity
- Top 50 stocks: highly liquid (comparable to developed markets)
- Mid-cap (~rank 100–500): moderate liquidity
- Small-cap (<rank 500): significant impact costs; avoid for systematic strategies unless capacity is <NT$50M

---

## Data Sources

| Source | Coverage | Cost | Notes |
|---|---|---|---|
| TEJ (台灣經濟新報) | Full historical, fundamentals, events | Paid (academic pricing available) | Gold standard for academic research |
| CMoney | Fundamentals, price, analyst | Paid | Popular for retail quant |
| XQ 全球贏家 | Real-time + historical price | Paid | Good for intraday |
| TWSE Open Data | Daily price, volume, margin | Free | Limited historical depth |
| MOPS (公開資訊觀測站) | Financial statements, announcements | Free | Requires parsing |
| Yahoo Finance / yfinance | Daily price | Free | Missing fundamentals, occasional errors |

---

## What Research Says About Taiwan Factors

### Factors with evidence of effectiveness in Taiwan
- **Momentum**: Weaker than US, decays faster (retail-driven reversals compete)
- **Value (P/B, P/E)**: Documented in academic literature (e.g., Chui & Wei 1998)
- **Size (small cap premium)**: Exists but liquidity-adjusted, less reliable post-2010
- **Low volatility**: Documented anomaly; fewer institutional constraints enables persistence
- **Earnings surprise (SUE)**: Post-earnings drift documented in Taiwan (stronger than US due to delayed reaction)
- **Insider ownership**: High insider ownership → outperformance

### Factors with weak or mixed evidence
- **Quality**: Less studied; mixed results
- **Profitability**: Data quality issues with CMoney vs TEJ

### Suggested search queries for Taiwan-specific research
```
python main.py --topic "momentum factor Taiwan stock market TWSE" --max-papers 5
python main.py --topic "value premium emerging markets Taiwan" --max-papers 5
python main.py --topic "post-earnings drift Taiwan equity anomaly" --max-papers 5
python main.py --topic "low volatility anomaly Asia Pacific equity" --max-papers 5
python main.py --topic "retail investor behavior Taiwan stock market" --max-papers 5
```

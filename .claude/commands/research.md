Help the user run a quantitative research session using this project.

## Your job

The user wants to research a quantitative trading strategy topic. Your job is to:

1. **Identify the topic** — extract it from the user's message (in any language). If unclear, ask one simple question: "你想研究什麼策略主題？"

2. **Ask about paper count** — if not specified, default to 5 and proceed without asking

3. **Run the research command**:
```bash
python3 main.py --topic "<topic>" --max-papers <n>
```

4. **Wait for completion**, then tell the user:
   - The report was saved to `outputs/`
   - They can run `/project:quant-analyst` to get a deeper analysis and next-step recommendations

## Examples of what the user might say

- "我想研究台灣動量策略"  → topic: "momentum strategy Taiwan stock market"
- "幫我找均值回歸的論文"  → topic: "mean reversion statistical arbitrage"
- "research volatility strategies" → topic: "volatility trading strategy equity"
- "波動率套利" → topic: "volatility arbitrage options"

## Topic translation guide

Translate Chinese topics to English keywords for better arXiv results:
- 動量策略 → momentum strategy / momentum factor
- 均值回歸 → mean reversion / statistical arbitrage
- 因子投資 → factor investing / smart beta
- 波動率 → volatility / variance risk premium
- 高頻交易 → high frequency trading / market microstructure
- 台灣股市 → Taiwan stock market / TWSE
- 機器學習 → machine learning / deep learning alpha
- 風險管理 → risk management / portfolio optimization

## After the run completes

Tell the user:
- ✅ Report saved to `outputs/report_<topic>_<timestamp>.md`
- 💡 Next: use `/project:quant-analyst` to analyze findings and get next-step recommendations

# Quant Research Agent — Claude Code 專案指引

## 快速開始

用中文或英文告訴我你想研究什麼，我會直接幫你跑：

> 「我想研究台灣動量策略」
> 「幫我找波動率套利的論文」
> 「research mean reversion」

或使用 slash commands：
- `/project:research` — 開始研究一個主題
- `/project:quant-analyst` — 分析最新報告，給出下一步查詢建議

---

## 專案概述

Python CLI 工具，支援兩種模式：
- `research mode`：輸入量化策略主題，自動搜尋論文、下載 PDF、提取結構化資訊，產生 JSON 知識庫與 Markdown 報告
- `ask mode`：優先查本地知識庫回答問題，必要時再用學術 / 官方來源做外部補充

## 架構

```
main.py          # CLI 入口（research / ask）
agent.py         # research workflow + QA synthesis + session memory
tools/
├── arxiv.py     # arXiv 搜尋、外部學術/官方來源搜尋、PDF 下載
├── pdf.py       # PDF 轉純文字（PyMuPDF / hybrid OCR）
├── qa.py        # 本地知識庫 retrieval、citation assembly、fallback answer
├── report.py    # 知識庫記錄 + Markdown 報告
└── schema_audit.py  # schema / semantic audit + answer readiness
prompts/
├── system.md    # LLM system prompt（從檔案讀取）
└── report_format.md  # Markdown 報告格式模板
outputs/
├── papers/      # 每篇論文一個 JSON（arxiv_id 命名）
├── reports/     # 人類可讀 Markdown 摘要
└── paper_index.json  # 全域索引（去重 + 快速查詢用）
```

## 執行方式

```bash
# 安裝依賴
pip install -r requirements.txt

# 設定 API key
cp .env.example .env
# 編輯 .env 填入 API key

# 深度研究
python main.py --mode research --topic "momentum strategy" --max-papers 3

# 對話問答
python main.py --mode ask --question "What does the knowledge base say about S&P 500 market timing?"
```

## LLM 設計

- `agent.py` 實作 tool use 迴圈：LLM 自主決定呼叫哪些工具
- LLM provider 可替換（目前在 `agent.py` 頂部設定）
- System prompt 從 `prompts/system.md` 讀取，修改 prompt 不需改程式碼

## Tool Use 流程

LLM 可用的 tools：

| Tool | 用途 |
|------|------|
| `search_arxiv` | 搜尋相關論文（回傳標題、摘要、arXiv ID） |
| `check_paper_exists` | 查詢論文是否已在知識庫（去重用） |
| `download_pdf` | 下載論文 PDF |
| `extract_pdf_text` | PDF 轉純文字 |
| `audit_paper_record` | 存檔前 schema / semantic audit |
| `save_paper_record` | 儲存單篇論文的結構化 JSON 至 outputs/papers/ |
| `save_report` | 儲存 Markdown 摘要報告至 outputs/reports/ |

## QA 模式原則

- 本地知識庫優先：先查 `paper_index.json`、`outputs/papers/*.json`、`outputs/chunks/*.txt`
- 外部補充次之：只接受學術與官方來源
- 回答格式：先結論，再引用
- 若外部資料尚未完整入庫，回答需明確標示 freshness note

## 論文提取維度（13 個）

每篇論文 LLM 提取並存為 JSON：

| # | 欄位 | 說明 |
|---|------|------|
| 1 | `paper_type` | trading_strategy / methodology / hybrid |
| 2 | `research_motivation` | gap + prior_limitation + claimed_contribution |
| 3 | `problem_solved` | problem_type + prior_approaches + limitation_of_prior |
| 4 | `model_method` | 方法名稱、類別、元件、描述 |
| 5 | `performance` | 開放式 metrics 陣列（sharpe / annualized_return / MDD / IC 等） |
| 6 | `risks_limitations` | 逐條風險與限制 |
| 7 | `market_structure` | 資產類別、指數、時間框架 |
| 8 | `strategy_taxonomy_tags` | 8 大策略分類標籤 |
| 9 | `system_modules` | 涉及的量化系統模組 |
| 10 | `datasets_used` | 使用的資料集 |
| 11 | `code_available` | 是否開源 |
| 12 | `methodology_checklist` | 5 項嚴謹度評估（out-of-sample、交易成本等） |
| 13 | `core_hypothesis` | why_it_works + economic_mechanism + decay_risk + testable_prediction |

**重要**：只報告論文中明確寫到的數據；`null` 表示數值無法解析，`"Not stated in paper"` 表示文字未提及。

## Available Skills

| Slash Command | 用途 |
|---------------|------|
| `/project:quant-analyst` | 讀取最新報告，從量化角度分析策略，並建議 5 個下一步搜尋查詢 |

**Knowledge base** (`.claude/commands/references/`):
- `strategy-taxonomy.md` — 策略分類地圖（動量/均值回歸/因子/ML 等）
- `system-architecture.md` — 量化系統 6 大模組
- `research-methodology.md` — 回測方法論與陷阱
- `taiwan-market.md` — 台灣市場法規、稅制、結構
- `optimization-workflow.md` — 策略研究生命週期
- `risk-framework.md` — 四類風險框架

## 未來擴充

- PDF 解析升級為 GROBID/Unstructured.io（為 RAG 打基礎）
- 論文資料存入資料庫
- 建立 RAG 系統
- 新增 orchestrator 協調多個專門 agent

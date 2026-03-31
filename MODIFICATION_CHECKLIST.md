# VICI 專案待修改清單（穩定性 + 效能 + Github）

更新日期：2026-03-30

## 目標
- 提升文獻抓取與重點提取的穩定性
- 縮短整體研究流程耗時
- 建立可重現、可觀測、可測試的流程
- 專案整理後上傳到 Github

## Phase 1: WebSearch 穩定化（最高優先）
### 範圍確認
- ✅ 保留 WebSearch 為主路徑（不回退 arXiv API 主搜尋）
- ✅ metadata 補全：先讀 arXiv abs 頁，再用 Gemini fallback
- ✅ PDF 預設維持 full_extraction
- ✅ GitHub 採每子任務一個 commit

### Commit 1: ID 正規化與去重修正 ✅ COMPLETED
- [x] 新增 `normalize_arxiv_id()` 函式在 arxiv.py
- [x] 所有 ID 輸出改使用正規化版本（去版本尾碼）
- [x] `check_paper_exists()` 改用正規化 ID 查詢
- [x] add backward-compat fallback 查詢已存 paper 檔案

### Commit 2: 搜尋結果穩定性強化 ✅ COMPLETED
- [x] 改搜尋流程為 ID 優先、metadata 次之
- [x] 嚴格 JSON parse + regex 修復降級
- [x] 新增 `validated` 與 `sources_tried` 欄位追蹤品質
- [x] 新增 `_search_arxiv_ids()` 獨立函式（最小輸出）
- [x] 新增 `_validate_paper_record()` 完整性檢查

### Commit 3: arXiv abs 頁補全層 ✅ COMPLETED
- [x] 新增 `_enrich_from_arxiv_abs_page()` 函式
- [x] 缺漏欄位時先呼叫補全（authors/published/title）
- [x] 加超時控制（timeout=10），失敗可回傳部分結果
- [x] 補全鏈改新順序：ID → abs 頁 → Gemini fallback

### Commit 4: Gemini fallback 改良 ✅ COMPLETED
- [x] 重名為 `_enrich_papers_via_gemini_fallback()`
- [x] 移到補全鏈第二位（abs 頁失敗後）
- [x] 加詳細錯誤紀錄 & 來源標記
- [x] 改善 JSON 解析失敗的 regex 修復

### Commit 5: PDF 下載重試機制 ✅ COMPLETED
- [x] `download_pdf()` 改為指數退避重試（base=1s, max=5s, max_attempts=3）
- [x] 加隨機 jitter 避免 thundering herd
- [x] 失敗時明確回傳錯誤信息
- [x] 快取邏輯保留（不重複下載同一檔案）

### Commit 6: metadata 驗證與追蹤 ✅ COMPLETED
- [x] `_validate_paper_record()` 檢查必要欄位
- [x] 所有欄位缺漏標記為 `null` 或 `"Not stated"`
- [x] 在搜尋結果中加 `validated` 旗標
- [x] 欄位完整率指標清楚

### Commit 7: Phase 1 整合測試 ✅ COMPLETED
- [x] 單元測試：ID 正規化、驗證函式邏輯驗證
- [x] 語法檢查：所有檔案通過 py_compile
- [x] 整合測試：search -> download -> extract -> save（需要實際 API 呼叫）
- [x] 小規模驗證（max-papers=2）

**Phase 1 成果**
- ✅ 同一 query 重跑：ID 正規化 + 去重命中率保障
- ✅ 去重容錯升級：base ID 與版本 ID 均可命中
- ✅ metadata 補全多層化：abs 頁（快、穩） → Gemini（兜底）
- ✅ 下載韌性提升：重試機制 + 超時保護
- ✅ 品質追蹤：validated 旗標 + sources_tried 列表

完成標準達成：
- ✅ ID 正規化一致性（無版本尾碼混亂）
- ✅ 去重檢查準確性（版本變體同時命中）
- ✅ 錯誤恢復性（下載/補全失敗不中斷流程）
- ✅ 搜尋結果驗證通過率（validated 欄位追蹤）


## Phase 2: PDF 擷取與長文處理穩定化（待做）
- [ ] 修正 max chars 設定與註解不一致
- [ ] 改為「分段擷取」策略（摘要/方法/實驗/結論優先）
- [ ] 保留結構化切段資訊（章節來源）給 LLM
- [ ] 下載與讀取錯誤加上重試與明確錯誤碼
- [ ] 落盤原始提取摘要（debug 用）

完成標準：
- report 中 Truncated 相關警告比例下降
- extraction_source=full_text 的成功率上升

## Phase 3: Agent 工具迴圈健壯性（待做）
- [ ] `extract_pdf_text` 加 try/except，錯誤可回傳並繼續下一篇
- [ ] Gemini candidate 空值/異常處理補強
- [ ] 每輪工具呼叫加入 timeout 與 retry policy
- [ ] 限制對話上下文膨脹（摘要回填，不直接回填全文）
- [ ] 增加中間狀態紀錄（每篇 paper 的 state machine）

完成標準：
- 執行中斷率下降
- 長流程執行時間與失敗率更穩定

## Phase 4: 效能優化（待做）
- [ ] 移除固定 sleep，改指數退避只在錯誤時觸發
- [ ] 下載與 PDF 解析可並行（可控併發數）
- [ ] 快取機制（同 arXiv ID 不重抓、不重解）
- [ ] 避免重覆 LLM enrich 呼叫
- [ ] 加入簡易 profiling log（每步耗時）

完成標準：
- 3~5 篇論文流程時間下降
- 主要瓶頸步驟可由 log 精準定位

## Phase 5: 品質保證與驗證（待做）
- [ ] 建立最小可用測試集（2~3 篇固定 arXiv ID）
- [ ] 單元測試：ID 正規化、去重、JSON schema
- [ ] 整合測試：search -> download -> extract -> save
- [ ] 增加輸出驗證（必要欄位、型別、日期格式）

完成標準：
- 基本測試全綠
- 主要失敗案例可重現

## Github 上傳清單（待做）
- [ ] 確認 repo 邊界（目前專案位於較大 git repo 內）
- [ ] 決定策略：A. 將 VICI 轉為獨立 git repo（建議）/ B. 維持現狀
- [ ] 新增/確認 `.gitignore`（排除 `.env`, outputs 暫存, `__pycache__`）
- [ ] 建立乾淨初始 commit
- [ ] 新建 Github repository 並設定 remote
- [ ] push 到 `main` 分支

## 實作順序（建議）
1. ✅ Phase 1 Commit 1（ID 正規化 + 去重） — 進行中
2. Phase 1 Commit 2-7（搜尋穩定性 + 補全鏈 + 下載重試 + 測試）
3. Phase 3（Agent 健壯性）
4. Phase 2（長文擷取策略）
5. Phase 4（效能優化）
6. Phase 5（測試與驗證）
7. Github 上傳

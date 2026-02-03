# Tech Frontier Newsletter Generator - Context Dump

## 當前開發進度 (2026-01-27)

### 1. 核心基礎設施 (已完成)
- **Vector DB**: 使用 Qdrant 進行本地儲存 (`data/qdrant_storage`)。
- **Embedding**: 採用 `Ollama (qwen3-embedding:latest)` 提供 4096 維的高解析度語義向量。
- **LLM Provider**: 支援 `Ollama (glm-4.7-flash:latest)` 與 `DeepSeek API`。
- **Workspace Cache**: 支援完整工作流的儲存與載入 (`data/workspace_cache.json`)，包含文章池、聚類、選題與報告。

### 2. 資料抓取與處理 (已完成)
- **多源抓取**: 支援 arXiv, GitHub, Hugging Face, Reddit, HN, 以及各大 AI 實驗室 Blog (OpenAI, Anthropic, DeepMind 等)。
- **Hacker News 強化**: 實作 7 天歷史抓取模式 (`front?day=YYYY-MM-DD`)。
- **Reddit 穩定性**: 透過 `domcontentloaded` 與專屬等待邏輯解決 403/Timeout 問題。
- **池子純化**: 實作 LLM 文章評分過濾機制，自動移除低價值雜訊。
- **全文本聚類**: Embedding 現在基於文章前 5000 字的全文本，而非僅限標題。

### 3. 代理人與寫作邏輯 (已完成)
- **Aggregation Agent**: 基於歐幾里得距離的層次聚類，並支援 AI 自動優化閾值 (Auto-Tune)。
- **Editor Agent**: 具備「命名難度檢測」與「敘事凝聚力」優先選題邏輯，並為聚類撰寫 display_title。
- **Newsletter Agent (Adversarial)**: 實作「對抗式生成」(Draft -> Critique -> Refine)，大幅提升技術深度與字數 (目標 2000+ 字)。
- **Chief Editor Agent (鍛碼匠)**: 
    - **人設**: 「技術鑑賞家/鍛碼匠」，風格犀利冷靜。
    - **寫作協議**: 嚴格執行 `Paradox (悖論) -> Gap (缺口) -> Reveal (鍛造) -> Insight (洞察)` 框架。
    - **結構**: 實作分段鍛造 (Segmented Refinement) 與跨篇章轉場代理人 (Flow Agent)。
    - **自動化**: 自動生成文末生字區 (Glossary) 與引用連結 (References)。

### 4. UI/UX (已完成)
- 實作 Streamlit 管理後台，包含：
    - 分階段 Token 消耗監控。
    - 完整工作進度儲存/載入。
    - 向量嵌入測試與餘弦相似度計算工具。
    - LLM 即時測試工具 (支援 Thinking 標籤過濾)。

---
## 下一步計畫
1. **多輪深度檢索**: 在 Phase 2 加入自動化 Arxiv/Google 檢索以補充研究報告。
2. **混合模型策略**: 針對關鍵寫作環節引入付費模型 (GPT-4o/Claude 3.5) 的切換選項。
3. **自動化測試**: 建立針對抓取穩定性的監控機制。
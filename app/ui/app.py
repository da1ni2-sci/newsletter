import streamlit as st
import asyncio
import os
import sys
import json
import re
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- PATH DEBUGGING ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Import our strategies and providers
try:
    from app.ingestion.rss_strategy import RSSStrategy
    from app.ingestion.local_playwright_strategy import LocalPlaywrightStrategy
    from app.adapters.deepseek_provider import DeepSeekProvider
    from app.adapters.openai_provider import OpenAIProvider # 新增 OpenAI
    from app.adapters.ollama_provider import OllamaProvider
    from app.adapters.local_embedding import LocalEmbeddingProvider
    from app.adapters.qdrant_adapter import QdrantAdapter
    from app.agents.aggregation_agent import AggregationAgent
    from app.agents.editor_agent import EditorAgent
    from app.agents.newsletter_agent import NewsletterAgent
    from app.agents.chief_editor_agent import ChiefEditorAgent # 新增
    from app.core.token_tracker import TokenTracker 
    from app.config.llm_config import LLMConfigManager # New Config Manager
    from app.adapters.db_adapter import SubscriberDatabase # 新增
    from app.tools.email_tool import EmailDeliveryTool # 新增
except ImportError as e:
    st.error(f"Import Error: {e}")
    st.stop()

st.set_page_config(page_title="Tech Frontier 電子報管理後台", layout="wide")

# --- Initialize Session State ---
if 'token_tracker' not in st.session_state:
    st.session_state['token_tracker'] = TokenTracker()

# Load Config
if 'llm_config' not in st.session_state:
    st.session_state['llm_config'] = LLMConfigManager.load_config()

st.title("🤖 Tech Frontier 電子報管理後台")
st.markdown("電子報生成與管理儀表板")

# --- Helper: Get LLM ---
def get_llm_for_agent(agent_name: str):
    config = LLMConfigManager.get_agent_config(agent_name, st.session_state.get('llm_config'))
    provider_type = config.get("provider", "Ollama (本地端)")
    model_name = config.get("model_name", "glm-4.7-flash:latest")
    
    if "DeepSeek" in provider_type:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if 'deepseek_api_key' in st.session_state and st.session_state['deepseek_api_key']:
            api_key = st.session_state['deepseek_api_key']
        base_url = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com")
        return DeepSeekProvider(api_key=api_key, base_url=base_url, model_name=model_name)
    elif "OpenAI" in provider_type:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if 'openai_api_key' in st.session_state and st.session_state['openai_api_key']:
            api_key = st.session_state['openai_api_key']
        return OpenAIProvider(api_key=api_key, model_name=model_name)
    else:
        return OllamaProvider(model_name=model_name)

# --- Sidebar Configuration ---
st.sidebar.header("系統設定")

with st.sidebar.expander("⚙️ LLM 模型配置 (Model Config)", expanded=False):
    st.caption("設定各階段使用的模型")
    
    # Global API Key Inputs (Temporary in session)
    st.session_state['deepseek_api_key'] = st.text_input("DeepSeek API Key (Global)", type="password", value=os.getenv("DEEPSEEK_API_KEY", ""))
    st.session_state['openai_api_key'] = st.text_input("OpenAI API Key (Global)", type="password", value=os.getenv("OPENAI_API_KEY", ""))

    agent_types = {
        "default": "預設 (Default)",
        "tagging": "1. 意圖標籤 (Intent Tagging)",
        "aggregation": "2. 聚類核心 (Aggregation Core)",
        "cluster_refinement": "3. 聚類優化 (Merge & Split)",
        "editor": "4. 選題/研究 (Editor)",
        "newsletter": "5. 初稿寫作 (Newsletter)",
        "chief_editor": "6. 總編終審 (Chief Editor)"
    }
    
    # Use Selectbox instead of Tabs for better mobile/sidebar visibility
    selected_agent_key = st.selectbox(
        "選擇要設定的階段 (Select Stage)", 
        options=list(agent_types.keys()), 
        format_func=lambda x: agent_types[x]
    )
    
    # Configuration for the selected agent
    key = selected_agent_key
    label = agent_types[key]
    
    st.markdown(f"#### 設定: {label}")
    
    # Ensure config exists
    if key not in st.session_state['llm_config']: 
        st.session_state['llm_config'][key] = {}
    current_conf = st.session_state['llm_config'][key]
    
    # 1. Provider Selection
    p_idx = 0
    saved_provider = current_conf.get("provider", "Ollama (本地端)")
    if "DeepSeek" in saved_provider: p_idx = 1
    elif "OpenAI" in saved_provider: p_idx = 2
    
    provider_widget_key = f"prov_widget_{key}"
    new_provider = st.selectbox(
        f"Provider ({key})", 
        ["Ollama (本地端)", "DeepSeek (API)", "OpenAI (API)"], 
        index=p_idx, 
        key=provider_widget_key
    )
    
    # 2. Model Name Selection
    saved_model = current_conf.get("model_name", "")
    suggested_model = saved_model
    if new_provider != saved_provider:
        if "OpenAI" in new_provider: suggested_model = "gpt-5-mini-2025-08-07"
        elif "DeepSeek" in new_provider: suggested_model = "deepseek-chat"
        elif "Ollama" in new_provider: suggested_model = "glm-4.7-flash:latest"
        
    if not suggested_model:
        suggested_model = "glm-4.7-flash:latest"

    model_widget_key = f"model_widget_{key}"
    new_model = st.text_input(f"Model Name ({key})", value=suggested_model, key=model_widget_key)
    
    # 3. Update State
    st.session_state['llm_config'][key]["provider"] = new_provider
    st.session_state['llm_config'][key]["model_name"] = new_model

    st.markdown("---")
    if st.button("💾 儲存所有模型設定", use_container_width=True):
        LLMConfigManager.save_config(st.session_state['llm_config'])
        st.toast("✅ 模型設定已儲存！")

st.sidebar.markdown("---")
st.sidebar.subheader("外部服務設定")
use_headless = st.sidebar.checkbox("Headless 模式 (隱藏瀏覽器)", value=True)

# --- Token Usage Widget in Sidebar ---
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Token 消耗監控")
tracker = st.session_state['token_tracker']
total_tokens = tracker.get_total()
st.sidebar.metric("本期總計消耗", f"{total_tokens:,} tokens")

with st.sidebar.expander("分階段明細"):
    for stage, counts in tracker.usage.items():
        st.write(f"**{stage}:** {counts['prompt'] + counts['completion']:,}")

if st.sidebar.button("🗑️ 重置 Token 紀錄"):
    st.session_state['token_tracker'].reset()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("向量資料庫設定")
qdrant_host = st.sidebar.text_input("Qdrant 主機", value="localhost")
qdrant_port = st.sidebar.number_input("Qdrant 連接埠", value=6333)

# --- Helper: Log Tokens ---
def log_tokens(stage: str, provider):
    if hasattr(provider, 'last_usage') and provider.last_usage:
        st.session_state['token_tracker'].add_usage(
            stage, 
            provider.last_usage.get('prompt_tokens', 0), 
            provider.last_usage.get('completion_tokens', 0)
        )

# 新增：渲染評分分佈的輔助函數 (放在最上方確保不會出現 NameError)
def render_purification_stats(dist, read_only=False):
    # Helper to safely get count regardless of key type (int/str)
    def get_items(d, k):
        return d.get(k, d.get(str(k), []))

    st.divider()
    st.subheader("📊 深度評分分佈 (Deep Scoring Distribution)")
    
    # Row 1: 1-5
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("1分 (垃圾)", len(get_items(dist, 1)))
    with c2: st.metric("2分 (低質)", len(get_items(dist, 2)))
    with c3: st.metric("3分 (普通)", len(get_items(dist, 3)))
    with c4: st.metric("4分 (乏味)", len(get_items(dist, 4)))
    with c5: st.metric("5分 (及格)", len(get_items(dist, 5)))
    
    # Row 2: 6-10
    c6, c7, c8, c9, c10 = st.columns(5)
    with c6: st.metric("6分 (不錯)", len(get_items(dist, 6)))
    with c7: st.metric("7分 (優質)", len(get_items(dist, 7)))
    with c8: st.metric("8分 (重要)", len(get_items(dist, 8)))
    with c9: st.metric("9分 (必讀)", len(get_items(dist, 9)))
    with c10: st.metric("10分 (神作)", len(get_items(dist, 10)))

    # 如果是唯讀模式 (執行中)，不顯示互動式元件以避免 DuplicateElementId 錯誤
    if not read_only:
        with st.expander("🔍 檢視各分數段文章列表", expanded=False):
            # Use slider instead of tabs to avoid UI overflow with 10 items
            # Add unique key to avoid conflicts if rendered multiple times
            # Fix: Use a stable key so selection persists across reruns (e.g. when saving)
            selected_score = st.select_slider(
                "選擇分數段 (Slide to select score)", 
                options=range(1, 11), 
                value=6,
                key="purification_score_slider" 
            )
            
            items = get_items(dist, selected_score)
            st.markdown(f"### 📑 {selected_score}分文章列表 ({len(items)} 篇)")
            
            if not items:
                st.info(f"目前沒有評分為 {selected_score} 的文章。 সন")
            else:
                for art in items:
                    st.markdown(f"- **{art['title']}** [連結]({art['link']})")

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📡 資料抓取", "🧠 LLM 測試", "🧬 向量嵌入測試", "🗄️ 向量資料庫", "📰 生成電子報", "✉️ 寄送電子報"])

# --- TAB 1: Ingestion ---
with tab1:
    st.header("資料來源抓取")
    
    sources_path = os.path.join(project_root, "app", "config", "sources.json")
    try:
        with open(sources_path, "r", encoding="utf-8") as f:
            sources_data = json.load(f)
    except Exception as e:
        st.error(f"無法載入來源設定: {e}")
        sources_data = {}

    col_ctrl1, col_fetch_all, col_fetch_fast = st.columns([2, 1, 1])
    
    with col_ctrl1:
        if st.button("🚀 全自動快跑 (抓取全部 -> 選題 -> 生成 Prompts)", type="primary", use_container_width=True):
            async def run_full_pipeline_logic():
                with st.status("正在執行全自動流水線...", expanded=True) as master_status:
                    try:
                        # 1. Fetch
                        master_status.write("### 📡 階段 1: 資料抓取")
                        all_sources_raw = []
                        for cat, items in sources_data.items():
                            for item in items:
                                item['category'] = cat
                                all_sources_raw.append(item)
                        
                        other_sources = [s for s in all_sources_raw if "reddit" not in s['url'].lower()]
                        reddit_sources = [s for s in all_sources_raw if "reddit" in s['url'].lower()]
                        ordered_sources = other_sources + reddit_sources
                        
                        total_sources = len(ordered_sources)
                        web_fetcher = LocalPlaywrightStrategy(headless=use_headless)
                        if 'fetched_articles' not in st.session_state: st.session_state['fetched_articles'] = []
                        
                        for i, source in enumerate(ordered_sources):
                            master_status.write(f"正在抓取 [{i+1}/{total_sources}]: {source['name']}...")
                            try:
                                results = await web_fetcher.fetch(source['url'])
                                if results: st.session_state['fetched_articles'].extend(results)
                            except Exception as e: master_status.error(f"Error {source['name']}: {e}")
                        
                        # 2. Auto-Tune & Tagging
                        master_status.write("### 🧬 階段 2: 語義增強與聚類")
                        embedder = LocalEmbeddingProvider()
                        agg_agent = AggregationAgent(embedder)
                        
                        # A. Run Tagging First
                        master_status.write("- 正在生成意圖標籤 (Tagging)...")
                        llm_tagging = get_llm_for_agent('tagging')
                        st.session_state['fetched_articles'] = await agg_agent.generate_intent_tags(
                            st.session_state['fetched_articles'], 
                            llm_tagging
                        )
                        log_tokens("Intent Tagging", llm_tagging) # 補上紀錄
                        
                        # B. Auto-Tune
                        master_status.write("- 正在執行智慧閾值優化 (Auto-Tune)...")
                        agg_llm = get_llm_for_agent('aggregation')
                        
                        best_t, reasoning = await agg_agent.optimize_threshold(st.session_state['fetched_articles'], agg_llm)
                        log_tokens("Aggregation Auto-Tune", agg_llm) # 補上紀錄
                        
                        st.session_state['current_threshold'] = best_t
                        st.session_state['auto_tune_reasoning'] = reasoning
                        
                        # C. Clustering
                        master_status.write("- 正在執行物理聚類...")
                        clusters = await agg_agent.cluster_articles(
                            st.session_state['fetched_articles'], 
                            distance_threshold=best_t
                        )
                        
                        # D. Refinement
                        master_status.write("- 正在執行最終邏輯整併 (Refinement)...")
                        llm_refinement = get_llm_for_agent('cluster_refinement')
                        final_clusters = await agg_agent.refine_clusters_with_llm(
                            clusters, 
                            llm_refinement
                        )
                        log_tokens("Cluster Refinement", llm_refinement) # 補上紀錄
                        st.session_state['topic_clusters'] = final_clusters

                        # 3. Editor Selection
                        master_status.write("### 🤖 階段 3: AI 總編選題")
                        editor_llm = get_llm_for_agent('editor')
                        
                        # --- Pass Vector Store for History Checking ---
                        embedder = LocalEmbeddingProvider()
                        vector_store = QdrantAdapter(host=qdrant_host, port=qdrant_port)
                        editor = EditorAgent(editor_llm, vector_store=vector_store, embedding=embedder)
                        # ----------------------------------------------
                        
                        # 擴大篩選候選人池：改為直接選取分數最高的 Top 50
                        candidates = sorted(final_clusters, key=lambda x: x.get('score', 0), reverse=True)[:50]
                        
                        selected_topics = await editor.select_top_topics(candidates)
                        log_tokens("Editor Selection", editor_llm) # 紀錄
                        
                        st.session_state['selected_topics'] = selected_topics

                        # 4. Full Crawl & Prompts
                        master_status.write("### 🔍 階段 4: 深度抓取與生成 Prompt")
                        for idx, topic in enumerate(st.session_state['selected_topics']):
                            master_status.write(f"- 處理主題 {idx+1}: {topic['representative_title']}")
                            for art in topic['articles']:
                                if len(art.get('content', '') or art.get('summary', '')) < 5000:
                                    content = await web_fetcher.fetch_full_content(art['link'])
                                    if content: art['content'] = content
                            
                            prompt_text = await editor.generate_research_prompt(topic)
                            log_tokens("Research Prompt Generation", editor_llm) # 紀錄
                            st.session_state['selected_topics'][idx]['research_prompt'] = prompt_text
                            st.session_state['selected_topics'][idx]['prompt_generated'] = True
                        
                        st.session_state['phase2_done'] = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"全自動流水線失敗: {e}")
            asyncio.run(run_full_pipeline_logic())

    with col_fetch_all:
        if st.button("🚀 單純抓取所有來源", use_container_width=True):
            async def run_fetch_all():
                status_placeholder = st.empty()
                progress_bar = st.progress(0)
                all_sources_raw = []
                for cat, items in sources_data.items():
                    for item in items:
                        item['category'] = cat
                        all_sources_raw.append(item)
                
                other_sources = [s for s in all_sources_raw if "reddit" not in s['url'].lower()]
                reddit_sources = [s for s in all_sources_raw if "reddit" in s['url'].lower()]
                ordered_sources = other_sources + reddit_sources
                
                total_sources = len(ordered_sources)
                web_fetcher = LocalPlaywrightStrategy(headless=use_headless)
                if 'fetched_articles' not in st.session_state: st.session_state['fetched_articles'] = []
                for i, source in enumerate(ordered_sources):
                    status_placeholder.text(f"正在抓取 [{i+1}/{total_sources}]: {source['name']}...")
                    try:
                        results = await web_fetcher.fetch(source['url'])
                        if results: st.session_state['fetched_articles'].extend(results)
                    except: pass
                    progress_bar.progress((i + 1) / total_sources)
                status_placeholder.success("抓取完成。")
            asyncio.run(run_fetch_all())

    with col_fetch_fast:
        if st.button("⏩ 快速抓取 (跳過 Reddit)", use_container_width=True):
            async def run_fetch_fast():
                all_sources = [s for cat in sources_data.values() for s in cat if "reddit" not in s['url'].lower()]
                web_fetcher = LocalPlaywrightStrategy(headless=use_headless)
                if 'fetched_articles' not in st.session_state: st.session_state['fetched_articles'] = []
                for source in all_sources:
                    try:
                        results = await web_fetcher.fetch(source['url'])
                        if results: st.session_state['fetched_articles'].extend(results)
                    except: pass
                st.success("快速抓取完成。")
            asyncio.run(run_fetch_fast())

    # --- Result Pool Management ---
    if 'fetched_articles' in st.session_state and st.session_state['fetched_articles']:
        st.divider()
        st.subheader(f"📊 專案進度管理 (文章池: {len(st.session_state['fetched_articles'])} 篇)")
        
        col_mgt1, col_mgt2, col_mgt3, col_mgt4 = st.columns(4)
        workspace_path = os.path.join(project_root, "data", "workspace_cache.json")
        
        with col_mgt1:
            if st.button("✨ 執行深度純化", use_container_width=True, type="primary", help="使用 LLM 過濾雜訊文章"):
                async def run_purify():
                    # Initialize status container for real-time updates
                    status_container = st.empty()
                    # 新增：即時詳細資訊容器 (使用 st.empty 避免無限疊加)
                    live_detail_container = st.empty()
                    
                    with st.status("正在進行深度脫水與純化...", expanded=True) as status:
                        llm = get_llm_for_agent('aggregation')
                        embedder = LocalEmbeddingProvider()
                        agg_agent = AggregationAgent(embedder)
                        
                        original_count = len(st.session_state['fetched_articles'])
                        
                        import time
                        start_time = time.time()
                        
                        # For instant rate calculation
                        last_update_time = start_time
                        last_update_count = 0
                        
                        progress_bar = st.progress(0)
                        
                        def ui_progress_callback(current, total, distribution=None):
                            nonlocal last_update_time, last_update_count
                            
                            now = time.time()
                            delta_time = now - last_update_time
                            delta_count = current - last_update_count
                            
                            # Calculate instant rate (items per second)
                            if delta_time > 0 and delta_count > 0:
                                rate = delta_count / delta_time
                            else:
                                rate = 0
                                
                            # Update references for next call
                            last_update_time = now
                            last_update_count = current
                            
                            remaining = total - current
                            if rate > 0:
                                eta = remaining / rate
                            else:
                                eta = 0
                            
                            perc = current / total
                            
                            def fmt(s): return f"{int(s//60)}m{int(s%60)}s" if s >= 60 else f"{int(s)}s"
                            
                            progress_bar.progress(perc)
                            
                            status_msg = f"**進度:** {current}/{total} ({int(perc*100)}%)"
                            if rate > 0.5: # If very fast (>0.5 art/sec), likely skipping/resuming
                                status_msg += f" | **狀態:** 極速略過已處理項目... (ETA: 計算中)"
                            else:
                                status_msg += f" | **ETA:** {fmt(eta)}"
                                
                            status_container.markdown(status_msg)
                            
                            if distribution:
                                st.session_state['purification_live_stats'] = distribution
                                # 在執行過程中即時渲染圖表 (使用 .container() 在 empty 區塊內刷新)
                                # 傳入 read_only=True 避免在迴圈中渲染互動式 slider 導致 Duplicate ID 錯誤
                                with live_detail_container.container():
                                    render_purification_stats(distribution, read_only=True)

                        purified = await agg_agent.purify_articles(
                            st.session_state['fetched_articles'], 
                            llm, 
                            progress_callback=ui_progress_callback
                        )
                        log_tokens("Article Purification", llm) # 補上紀錄
                        
                        st.session_state['fetched_articles'] = purified
                        filtered_count = original_count - len(purified)
                        status.update(label=f"✅ 純化完成！保留 {len(purified)} 篇，過濾 {filtered_count} 篇。", state="complete")
                        st.rerun()
                asyncio.run(run_purify())
            
            # 非執行期間的持久顯示
            if 'purification_live_stats' in st.session_state and st.session_state['purification_live_stats']:
                render_purification_stats(st.session_state['purification_live_stats'])

        with col_mgt2:
            if st.button("💾 儲存完整進度", use_container_width=True):
                state_to_save = {
                    'fetched_articles': st.session_state.get('fetched_articles'),
                    'topic_clusters': st.session_state.get('topic_clusters'),
                    'selected_topics': st.session_state.get('selected_topics'),
                    'current_threshold': st.session_state.get('current_threshold'),
                    'auto_tune_reasoning': st.session_state.get('auto_tune_reasoning'),
                    'final_newsletter': st.session_state.get('final_newsletter'),
                    'refined_newsletter': st.session_state.get('refined_newsletter'),
                    'purification_live_stats': st.session_state.get('purification_live_stats'), # Added
                    'save_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                with open(workspace_path, "w", encoding="utf-8") as f:
                    json.dump(state_to_save, f, ensure_ascii=False, indent=2)
                st.toast(f"✅ 進度已儲存")

        with col_mgt3:
            if st.button("📤 匯出文章池", use_container_width=True):
                article_cache_path = os.path.join(project_root, "data", "articles_cache.json")
                with open(article_cache_path, "w", encoding="utf-8") as f:
                    json.dump(st.session_state['fetched_articles'], f, ensure_ascii=False, indent=2)
                st.toast("✅ 已匯出單純文章快取")

        with col_mgt4:
            if st.button("🗑️ 清空工作區", use_container_width=True):
                st.session_state.clear()
                st.rerun()
            
        with st.expander("📦 查看當前文章列表", expanded=False):
            for item in st.session_state['fetched_articles']:
                st.write(f"- [{item.get('source_type')}] {item['title']} ([連結]({item['link']}))")
    else:
        # 如果池子是空的，顯示載入按鈕
        st.divider()
        st.subheader("📥 載入現有資料")
        
        workspace_path = os.path.join(project_root, "data", "workspace_cache.json")
        article_cache_path = os.path.join(project_root, "data", "articles_cache.json")
        
        col_load1, col_load2 = st.columns(2)
        
        if os.path.exists(workspace_path):
            if col_load1.button("📥 載入完整工作進度 (含選題/報告)", use_container_width=True):
                with open(workspace_path, "r", encoding="utf-8") as f:
                    saved_state = json.load(f)
                    for key, value in saved_state.items():
                        if key != 'save_time':
                            # Special handling for purification stats (JSON keys are always strings)
                            if key == 'purification_live_stats' and isinstance(value, dict):
                                try:
                                    # Convert keys back to integers: "1" -> 1
                                    st.session_state[key] = {int(k): v for k, v in value.items()}
                                except:
                                    st.session_state[key] = value
                            else:
                                st.session_state[key] = value
                st.success(f"已還原至 {saved_state.get('save_time')} 的完整存檔。 সন")
                st.rerun()
                
        if os.path.exists(article_cache_path):
            if col_load2.button("📄 僅載入文章池快取", use_container_width=True):
                with open(article_cache_path, "r", encoding="utf-8") as f:
                    st.session_state['fetched_articles'] = json.load(f)
                st.success("已載入文章池。 সন")
                st.rerun()
        
        if not os.path.exists(workspace_path) and not os.path.exists(article_cache_path):
            st.info("目前沒有可用的快取檔案，請先執行抓取。 সন")

    # --- Step 1.5: Semantic Enhancement (Intent Tagging) ---
    if 'fetched_articles' in st.session_state and st.session_state['fetched_articles']:
        st.markdown("---")
        st.header("Step 1.5: 語義增強 (Intent Tagging)")
        
        # Check tagging status
        tagged_count = sum(1 for a in st.session_state['fetched_articles'] if 'intent_tags' in a)
        total_count = len(st.session_state['fetched_articles'])
        
        col_tag1, col_tag2 = st.columns([1, 3])
        with col_tag1:
            st.metric("已標記文章", f"{tagged_count}/{total_count}")
        
        with col_tag2:
            if st.button("🏷️ 生成意圖標籤 (強化聚類精準度)", type="primary", use_container_width=True):
                async def run_tagging():
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def tag_callback(current, total, msg):
                        progress_bar.progress(current / total)
                        status_text.text(f"{msg} ({current}/{total})")
                    
                    llm_tagging = get_llm_for_agent('tagging')
                    embedder = LocalEmbeddingProvider() # Just for init, not used in tagging
                    agg_agent = AggregationAgent(embedder)
                    
                    tagged_articles = await agg_agent.generate_intent_tags(
                        st.session_state['fetched_articles'], 
                        llm_tagging,
                        progress_callback=tag_callback
                    )
                    log_tokens("Intent Tagging", llm_tagging) # 補上紀錄
                    st.session_state['fetched_articles'] = tagged_articles
                    st.success("✅ 意圖標籤生成完成！現在聚類效果將大幅提升。 সন")
                    st.rerun()
                asyncio.run(run_tagging())
        
        if tagged_count > 0:
            with st.expander("👀 查看部分標籤範例", expanded=False):
                for a in st.session_state['fetched_articles'][:5]:
                    if 'intent_tags' in a:
                        st.markdown(f"- **{a['title']}**: `{a['intent_tags']}`")

    # --- Step 2: Aggregation ---
    if 'fetched_articles' in st.session_state and st.session_state['fetched_articles']:
        st.markdown("---")
        st.header("Step 2: 主題聚類 (Physical Clustering)")
        
        col_agg1, col_agg2, col_agg3 = st.columns([1, 1, 1])
        if 'current_threshold' not in st.session_state: st.session_state['current_threshold'] = 0.65
        threshold_val = col_agg1.slider("聚類閾值 (Distance Threshold)", 0.1, 2.5, st.session_state['current_threshold'])
        
        # A. Auto-Tune (Only picks threshold)
        if col_agg2.button("🔍 智慧優化 (Auto-Tune)", use_container_width=True, help="讓 AI 建議最適合當前資料的閾值"):
            async def run_auto_tune():
                with st.status("正在進行語義掃描並建議最佳閾值...", expanded=True) as status:
                    embedder = LocalEmbeddingProvider()
                    agg_agent = AggregationAgent(embedder)
                    llm = get_llm_for_agent('aggregation')
                    
                    best_t, reasoning = await agg_agent.optimize_threshold(st.session_state['fetched_articles'], llm)
                    log_tokens("Aggregation Auto-Tune", llm)
                    
                    st.session_state['current_threshold'] = best_t
                    st.session_state['auto_tune_reasoning'] = reasoning
                    st.success(f"AI 建議閾值: {best_t}")
                    st.rerun()
            asyncio.run(run_auto_tune())

        # B. Perform Clustering
        if col_agg3.button("🚀 執行物理聚合", use_container_width=True, type="primary"):
            async def run_agg():
                embedder = LocalEmbeddingProvider()
                agg_agent = AggregationAgent(embedder)
                
                with st.spinner("正在執行物理聚類..."):
                    clusters = await agg_agent.cluster_articles(
                        st.session_state['fetched_articles'], 
                        distance_threshold=threshold_val
                    )
                st.session_state['topic_clusters'] = clusters
                st.success(f"識別出 {len(clusters)} 個初步主題！ সন")
            asyncio.run(run_agg())

        if st.session_state.get('auto_tune_reasoning'):
            with st.expander("💡 查看 AI 閾值分析理由", expanded=False):
                st.markdown(st.session_state['auto_tune_reasoning'])

    # --- Step 2.5: Cluster Refinement ---
    if st.session_state.get('topic_clusters'):
        st.markdown("---")
        st.header("Step 2.5: 聚類邏輯整併 (Merge & Split)")
        
        col_ref1, col_ref2 = st.columns([3, 1])
        with col_ref1:
            st.info(f"當前共有 {len(st.session_state['topic_clusters'])} 個初步主題。點擊右側按鈕進行邏輯整併。 সন")
        
        with col_ref2:
            if st.button("✨ 執行邏輯整併", use_container_width=True, type="primary"):
                async def run_refinement():
                    with st.spinner("總編正在進行主題整併..."):
                        llm_refinement = get_llm_for_agent('cluster_refinement')
                        agg_agent = AggregationAgent(LocalEmbeddingProvider())
                        
                        refined_clusters = await agg_agent.refine_clusters_with_llm(
                            st.session_state['topic_clusters'], 
                            llm_refinement
                        )
                        log_tokens("Cluster Refinement", llm_refinement) # 補上紀錄
                        st.session_state['topic_clusters'] = refined_clusters
                        st.success("✅ 主題整併完成！ সন")
                        st.rerun()
                asyncio.run(run_refinement())

        with st.expander(f"📦 查看所有候選主題聚類 ({len(st.session_state['topic_clusters'])} 個)", expanded=False):
            for i, cluster in enumerate(st.session_state['topic_clusters']):
                label = f"Topic {i+1}: {cluster['representative_title']} (🔥 Score: {cluster['score']})"
                with st.expander(label):
                    # 顯示評分明細
                    if 'score_details' in cluster:
                        det = cluster['score_details']
                        if 'avg_llm_score' in det:
                            st.caption(f"📊 **評分明細:** 平均分: {det['avg_llm_score']} | 最高分: {det['max_llm_score']} | 規模加成: {det['size_bonus']}")
                            if det.get('is_academic_boost'):
                                st.caption("🎓 **學術加成:** Yes (+2.0)")
                        else:
                            auth = det.get('authority', 0)
                            hype = det.get('hype_upvotes', 0)
                            st.caption(f"📊 **評分明細 (舊版):** 權威: {auth} | 熱度: {hype}")
                    
                    st.write(f"**規模:** {cluster['size']} 篇文章")
                    for art in cluster['articles']:
                        st.markdown(f"- [{art['title']}]({art['link']}) ({art.get('source_type')})")

    # --- Step 3: Editor Selection ---
    if 'topic_clusters' in st.session_state and st.session_state['topic_clusters']:
        st.markdown("---")
        st.header("Step 3: AI 總編選題")
        if st.session_state.get('selected_topics') is not None:
            with st.expander("✅ 選中主題細節", expanded=True):
                for i, t in enumerate(st.session_state['selected_topics']):
                    # 優先顯示 Editor 撰寫的主題名
                    display_name = t.get('display_title', t['representative_title'])
                    st.markdown(f"#### {i+1}. {display_name}")
                    st.info(f"**理由:** {t.get('editor_reason', 'N/A')}")
                    with st.expander("查看來源文章"):
                        for art in t['articles']: st.markdown(f"- [{art['title']}]({art['link']})")
            if st.button("🔄 重新選題"):
                st.session_state['selected_topics'] = None
                st.rerun()
        else:
            if st.button("🤖 讓 AI 挑選 Top 5", type="primary", use_container_width=True):
                async def run_editor():
                    with st.status("AI 總編正在審閱候選主題...", expanded=True) as status:
                        editor_llm = get_llm_for_agent('editor')
                        
                        # --- Pass Vector Store for History Checking ---
                        embedder = LocalEmbeddingProvider()
                        vector_store = QdrantAdapter(host=qdrant_host, port=qdrant_port)
                        editor = EditorAgent(editor_llm, vector_store=vector_store, embedding=embedder)
                        # ----------------------------------------------
                        
                        clusters = st.session_state['topic_clusters']
                        
                        # 1. 準備候選池
                        status.write("📊 正在評估內容深度與多樣性...")
                        # 擴大篩選候選人池：改為直接選取分數最高的 Top 50
                        candidates = sorted(clusters, key=lambda x: x.get('score', 0), reverse=True)[:50]
                        status.write(f"📝 已鎖定 {len(candidates)} 個高分候選主題，正在生成摘要報告...")
                        
                        # 2. 執行選題 (這是最花時間的一步)
                        status.write("🧠 **正在請求總編進行決策...** (請稍候，正在分析跨來源關聯性)")
                        st.session_state['selected_topics'] = await editor.select_top_topics(candidates)
                        
                        # 3. 完成
                        log_tokens("Editor Selection", editor_llm)
                        count = len(st.session_state['selected_topics'])
                        status.update(label=f"✅ 選題完成！總編挑選了 {count} 個主題。", state="complete")
                        st.rerun()
                asyncio.run(run_editor())

    # --- Phase 2: Research Navigation ---
    if st.session_state.get('selected_topics'):
        st.markdown("---")
        st.header("Phase 2: 深度研究與導航")
        
        col_p2_1, col_p2_2 = st.columns([3, 1])
        with col_p2_1:
            st.info("請勾選下方想要進行『深度研究』的主題，然後點擊右側按鈕開始批量處理。")
        with col_p2_2:
            if st.button("🚀 批量處理選中主題", use_container_width=True, type="primary"):
                async def process_batch_p2():
                    # 篩選出有勾選的主題索引
                    selected_indices = [idx for idx, _ in enumerate(st.session_state['selected_topics']) 
                                        if st.session_state.get(f"select_topic_{idx}", False)]
                    
                    if not selected_indices:
                        st.warning("請先勾選至少一個主題！")
                        return

                    with st.status("深度研究中...", expanded=True) as status:
                        web_fetcher = LocalPlaywrightStrategy(headless=use_headless)
                        llm = get_llm_for_agent('editor')
                        editor = EditorAgent(llm)
                        
                        for idx in selected_indices:
                            topic = st.session_state['selected_topics'][idx]
                            status.write(f"🔍 **處理中: {topic['representative_title']}**")
                            for art in topic['articles']:
                                if len(art.get('content', '') or art.get('summary', '')) < 5000:
                                    content = await web_fetcher.fetch_full_content(art['link'])
                                    if content: art['content'] = content
                            st.session_state['selected_topics'][idx]['research_prompt'] = await editor.generate_research_prompt(topic)
                            log_tokens("Research Prompt Generation", llm) # 紀錄
                            st.session_state['selected_topics'][idx]['prompt_generated'] = True
                        st.session_state['phase2_done'] = True
                        st.rerun()
                asyncio.run(process_batch_p2())

        for i, topic in enumerate(st.session_state['selected_topics']):
            done = "✅" if topic.get('prompt_generated') else "⬜"
            
            # 使用 columns讓勾選框與 expander 並排
            c1, c2 = st.columns([1, 20])
            # 預設勾選尚未產生的項目
            is_checked = c1.checkbox("選取", value=not topic.get('prompt_generated'), key=f"select_topic_{i}", label_visibility="collapsed")
            
            with c2.expander(f"{done} Topic {i+1}: {topic['representative_title']}", expanded=topic.get('prompt_generated', False)):
                prompt = topic.get('research_prompt', '')
                if prompt: st.code(prompt)
                report_key = f"report_{i}_{topic.get('cluster_id', i)}"
                st.text_area("貼上研究報告:", key=report_key, height=200, value=topic.get('research_report', ''),
                             on_change=lambda idx=i, k=report_key: st.session_state['selected_topics'][idx].update({"research_report": st.session_state[k]}))

# --- TAB 5: Newsletter Synthesis ---
with tab5:
    st.header("Phase 3: 電子報生成")
    if 'selected_topics' not in st.session_state or st.session_state['selected_topics'] is None:
        st.warning("請先完成主題選擇。 সন")
    else:
        if st.button("✍️ 一鍵生成電子報文章", type="primary", use_container_width=True):
            async def run_synthesis_logic():
                with st.status("並行寫作中...", expanded=True) as status:
                    llm = get_llm_for_agent('newsletter')
                    
                    agent = NewsletterAgent(llm, None, None)
                    async def write_topic(idx, topic):
                        article_md = await agent.synthesize_topic_article(topic)
                        log_tokens(f"Synthesis: Topic {idx+1}", llm) # 紀錄
                        st.session_state['selected_topics'][idx]['final_article'] = article_md
                        return article_md
                    tasks = [write_topic(i, t) for i, t in enumerate(st.session_state['selected_topics'])]
                    all_articles = await asyncio.gather(*tasks)
                    # Use a unique separator to prevent splitting issues in ChiefEditor
                    st.session_state['final_newsletter'] = f"# Tech Frontier 科技前沿電子報\n\n" + "\n\n<<<TOPIC_SEPARATOR>>>\n\n".join(all_articles)
                    st.rerun()
            asyncio.run(run_synthesis_logic())

        if 'final_newsletter' in st.session_state:
            st.divider()
            st.subheader("📰 電子報初稿預覽")
            
            # 在預覽上方也加一個存檔按鈕，方便操作
            if st.button("💾 儲存當前進度 (包含此初稿)", key="save_phase3"):
                workspace_path = os.path.join(project_root, "data", "workspace_cache.json")
                state_to_save = {
                    'fetched_articles': st.session_state.get('fetched_articles'),
                    'topic_clusters': st.session_state.get('topic_clusters'),
                    'selected_topics': st.session_state.get('selected_topics'),
                    'current_threshold': st.session_state.get('current_threshold'),
                    'auto_tune_reasoning': st.session_state.get('auto_tune_reasoning'),
                    'final_newsletter': st.session_state.get('final_newsletter'),
                    'refined_newsletter': st.session_state.get('refined_newsletter'),
                    'save_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                with open(workspace_path, "w", encoding="utf-8") as f:
                    json.dump(state_to_save, f, ensure_ascii=False, indent=2)
                st.toast(f"✅ 初稿已存檔 ({state_to_save['save_time']})")

            st.markdown(st.session_state['final_newsletter'])
            
            # 新增：總編優化區塊
            st.markdown("---")
            st.subheader("✨ 總編終審 (Chief Editor Refinement)")
            if st.button("🚀 執行總編終審優化", type="primary", use_container_width=True):
                async def run_refinement():
                    # Progress container
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    with st.status("總編正在審閱並重新編排中...", expanded=True) as status:
                        llm = get_llm_for_agent('chief_editor')
                        
                        editor = ChiefEditorAgent(llm)
                        
                        # Define callback
                        def refinement_callback(current, total, msg):
                            perc = min(current / total, 1.0) if total > 0 else 0
                            progress_bar.progress(perc)
                            status_text.markdown(f"**進度:** {int(perc*100)}% | **狀態:** {msg}")
                            # Also update the expandable status
                            status.write(msg)

                        refined_md = await editor.refine_newsletter(
                            st.session_state['final_newsletter'], 
                            issue_number=st.session_state.get('current_issue_number', 'N/A'),
                            progress_callback=refinement_callback
                        )
                        log_tokens("Final Refinement", llm) # 紀錄 Token
                        
                        if not refined_md:
                            status.update(label="❌ 總編沒說話... (回應為空)", state="error")
                            st.error("總編（模型）回傳了空內容。這可能是因為模型正在長時間思考導致超時，或思考內容被過濾後無剩餘文字。請嘗試再次執行或更換模型。 সন")
                        else:
                            st.session_state['refined_newsletter'] = refined_md
                            progress_bar.progress(1.0)
                            status_text.success("優化完成！ সন")
                            status.update(label="✅ 終審優化完成！", state="complete")
                            st.rerun()
                asyncio.run(run_refinement())

        if st.session_state.get('refined_newsletter'):
            st.divider()
            st.subheader("💎 最終拋光版本")
            
            # --- NEW: Issue Number Management ---
            st.markdown("### 🏷️ 期刊號與存檔設定")
            
            # Calculate default issue number
            def get_next_issue_number():
                # Format: YYYY-MM-001
                now = datetime.now()
                year_month = now.strftime("%Y-%m")
                
                # Check cache for the last sequence number
                history_path = os.path.join(project_root, "data", "issue_history.json")
                if os.path.exists(history_path):
                    try:
                        with open(history_path, "r") as f:
                            history = json.load(f)
                            last_seq = history.get("last_seq", 0)
                    except: last_seq = 0
                else:
                    last_seq = 0
                
                next_seq = last_seq + 1
                return f"{year_month}-{next_seq:03d}"

            if 'current_issue_number' not in st.session_state:
                st.session_state['current_issue_number'] = get_next_issue_number()

            col_issue1, col_issue2 = st.columns([2, 1])
            st.session_state['current_issue_number'] = col_issue1.text_input("本期期刊號 (可手動修改)", value=st.session_state['current_issue_number'])
            
            if col_issue2.button("📦 完稿並存入向量庫", use_container_width=True, type="primary", help="將內容索引至 Qdrant，避免未來重複並建立延伸閱讀關聯"):
                async def finalize_and_index():
                    with st.spinner("正在將週報內容索引至向量資料庫..."):
                        try:
                            embedder = LocalEmbeddingProvider()
                            vector_store = QdrantAdapter(host=qdrant_host, port=qdrant_port)
                            
                            # 1. Ensure collection exists (using 1536 for common models or check embedder)
                            # Actually we need to get a sample vector to know the size
                            sample_vec = await embedder.embed_query("test")
                            collection_name = "finalized_newsletters"
                            await vector_store.create_collection(collection_name, len(sample_vec))
                            
                            # 2. Chunk by topic
                            content = st.session_state['refined_newsletter']
                            # Split by ## headers (standard for our articles)
                            topic_chunks = re.split(r'\n(?=## )', content)
                            
                            points = []
                            for chunk in topic_chunks:
                                if len(chunk.strip()) < 100: continue
                                
                                # Extract title from chunk
                                first_line = chunk.strip().split('\n')[0]
                                title = first_line.replace('##', '').strip()
                                
                                vector = await embedder.embed_query(chunk)
                                point_id = str(uuid.uuid4())
                                points.append({
                                    "id": point_id,
                                    "vector": vector,
                                    "payload": {
                                        "issue_number": st.session_state['current_issue_number'],
                                        "date": datetime.now().strftime("%Y-%m-%d"),
                                        "title": title,
                                        "content": chunk,
                                        "type": "past_newsletter_topic"
                                    }
                                })
                            
                            # 3. Upsert
                            from qdrant_client.http import models as qmodels
                            q_points = [qmodels.PointStruct(id=p['id'], vector=p['vector'], payload=p['payload']) for p in points]
                            await vector_store.upsert(collection_name, q_points)
                            
                            # 4. Update history
                            history_path = os.path.join(project_root, "data", "issue_history.json")
                            curr_seq = int(st.session_state['current_issue_number'].split('-')[-1])
                            with open(history_path, "w") as f:
                                json.dump({"last_seq": curr_seq}, f)
                                
                            st.success(f"✅ 第 {st.session_state['current_issue_number']} 期已成功存檔至向量資料庫！")
                        except Exception as e:
                            st.error(f"存檔失敗: {e}")
                
                asyncio.run(finalize_and_index())

            st.markdown("---")
            st.markdown(st.session_state['refined_newsletter'])
            
            # Fix: Encode content to bytes to avoid Streamlit MediaFileStorageError
            final_md_bytes = st.session_state['refined_newsletter'].encode('utf-8')
            
            col_dl1, col_load2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    label="📥 下載最終版 Markdown",
                    data=final_md_bytes,
                    file_name=f"newsletter_FINAL_{datetime.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            
            with col_load2:
                # 生成 HTML 版本
                try:
                    import markdown
                    html_content = markdown.markdown(st.session_state['refined_newsletter'], extensions=['tables', 'fenced_code'])
                    # 加上簡單的 Email 樣式
                    email_html = f"""
                    <html>
                    <head>
                        <style>
                            body {{ font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
                            h1 {{ color: #1b8f7a; border-bottom: 2px solid #1b8f7a; padding-bottom: 10px; }}
                            h2 {{ color: #1b8f7a; margin-top: 30px; }}
                            a {{ color: #1b8f7a; text-decoration: none; }}
                            a:hover {{ text-decoration: underline; }}
                            code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
                            pre {{ background: #f4f4f4; padding: 15px; overflow-x: auto; border-radius: 5px; }}
                            hr {{ border: 0; border-top: 1px solid #eee; margin: 40px 0; }}
                        </style>
                    </head>
                    <body>
                        {html_content}
                    </body>
                    </html>
                    """
                    st.download_button(
                        label="📧 下載 Email HTML 版本",
                        data=email_html.encode('utf-8'),
                        file_name=f"newsletter_FINAL_{datetime.now().strftime('%Y%m%d')}.html",
                        mime="text/html",
                        use_container_width=True
                    )
                except ImportError:
                    st.error("請先安裝 markdown 套件以匯出 HTML 版本。")

            if st.button("🗑️ 清空生成記錄"):
                if 'final_newsletter' in st.session_state: del st.session_state['final_newsletter']
                if 'refined_newsletter' in st.session_state: del st.session_state['refined_newsletter']
                st.rerun()

# --- TAB 6: Email Delivery ---
with tab6:
    st.header("✉️ 電子報發送系統")
    
    if 'refined_newsletter' not in st.session_state:
        st.warning("請先在『生成電子報』頁面完成總編終審，產出最終版內容後再進行發送。")
    else:
        st.info(f"準備發送期刊號: **{st.session_state.get('current_issue_number', 'N/A')}**")
        
        # 1. Subscriber Stats
        db = SubscriberDatabase()
        
        # UI: Add button to explicitly load stats, preventing hang on startup
        if st.button("📊 載入/更新訂閱者數據", use_container_width=True):
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                curr_issue = st.session_state.get('current_issue_number', 'N/A')
                st.session_state['subscriber_stats'] = loop.run_until_complete(db.get_subscriber_stats(current_issue=curr_issue))
                st.success("數據載入完成。")
                st.rerun()
            except Exception as e:
                st.error(f"無法讀取訂閱者資料: {e}")
        
        if 'subscriber_stats' in st.session_state:
            stats = st.session_state['subscriber_stats']
            st.subheader("👥 訂閱者狀態")
            col_stat1, col_stat2, col_stat3, col_stat4, col_stat5 = st.columns(5)
            col_stat1.metric("總驗證人數", f"{stats.get('total_verified', 0)} 人")
            col_stat2.metric("本期已寄送", f"{stats.get('already_sent', 0)} 人")
            col_stat3.metric("技術開發者", f"{stats.get('developer', 0)} 人")
            col_stat4.metric("商業決策者", f"{stats.get('business', 0)} 人")
            col_stat5.metric("科技愛好者", f"{stats.get('hobbyist', 0)} 人")

        st.divider()
        
        # 2. Email Preview & Config
        st.subheader("📧 發送設定")
        email_subject = st.text_input("郵件主旨", value=f"【鍛碼匠技術週報】Issue: {st.session_state.get('current_issue_number', 'N/A')}")
        
        # Generate full HTML for preview and sending
        import markdown
        html_body = markdown.markdown(st.session_state['refined_newsletter'], extensions=['tables', 'fenced_code'])
        full_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
                h1 {{ color: #1b8f7a; border-bottom: 2px solid #1b8f7a; padding-bottom: 10px; }}
                h2 {{ color: #1b8f7a; margin-top: 30px; }}
                a {{ color: #1b8f7a; text-decoration: none; }}
                code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
                hr {{ border: 0; border-top: 1px solid #eee; margin: 40px 0; }}
            </style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """

        with st.expander("👀 預覽發送內容 (HTML)"):
            st.components.v1.html(full_html, height=500, scrolling=True)

        # 3. Send Logic
        st.warning("⚠️ 點擊下方按鈕後，系統將正式對所有『已驗證』的會員發送郵件。請務必確認內容正確。")
        
        if st.button("🚀 正式群發電子報", type="primary", use_container_width=True):
            async def run_delivery():
                delivery_tool = EmailDeliveryTool()
                db = SubscriberDatabase()
                
                with st.status("正在準備發送清單...", expanded=True) as status:
                    # Fetch recipients (Excluding those who already received this issue)
                    try:
                        curr_issue = st.session_state.get('current_issue_number', 'N/A')
                        subscribers = await db.get_verified_subscribers(exclude_issue=curr_issue)
                        emails = [s['email'] for s in subscribers]
                        total = len(emails)
                        
                        if total == 0:
                            status.update(label=f"ℹ️ 本期 ({curr_issue}) 已無待發送名單 (所有人皆已寄送或無新訂閱者)", state="complete")
                            return

                        status.write(f"✅ 找到 {total} 位尚未收到本期的訂閱者。開始透過 Brevo SMTP 發送...")
                        
                        # Perform delivery
                        result = await delivery_tool.send_newsletter(emails, email_subject, full_html)
                        
                        if result["success"]:
                            data = result["data"]
                            success_count = data["success_count"]
                            failed_count = len(data["failed_emails"])
                            
                            # --- NEW: Record successful sends in DB ---
                            if success_count > 0:
                                # Get list of successful emails
                                failed_set = {f['email'] for f in data["failed_emails"]}
                                successful_emails = [e for e in emails if e not in failed_set]
                                await db.record_sent_emails(successful_emails, curr_issue)
                                # Clear cache to refresh UI
                                if 'subscriber_stats' in st.session_state: del st.session_state['subscriber_stats']
                                status.write(f"📝 已將 {success_count} 筆發送紀錄更新至資料庫。")
                            # ------------------------------------------

                            status.update(label=f"🎉 發送完成！成功: {success_count}, 失敗: {failed_count}", state="complete")
                        else:
                            status.update(label=f"❌ 發送過程出錯: {result['error']}", state="error")
                    except Exception as e:
                        status.update(label=f"❌ 處理失敗: {e}", state="error")
            
            asyncio.run(run_delivery())

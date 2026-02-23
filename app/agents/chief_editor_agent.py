import json
from typing import List, Dict, Any, Optional
from app.core.interfaces import LLMProvider

class ChiefEditorAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def arrange_newsletter_flow(self, topic_blocks: List[str]) -> List[str]:
        """
        The Arranger: Reorders topics to create a cohesive narrative flow BEFORE writing.
        """
        if len(topic_blocks) < 2: return topic_blocks
        
        # 1. Extract Summaries for Decision Making
        summaries = []
        for i, block in enumerate(topic_blocks):
            # Try to grab the title line
            lines = block.strip().split('\n')
            title = lines[0] if lines else f"Topic {i+1}"
            content_preview = block[:500] # First 500 chars
            summaries.append(f"ID {i}: {title}\nContent Preview: {content_preview}\n")
            
        context = "\n---\n".join(summaries)
        
        # 2. Ask LLM to Reorder
        system_prompt = "You are an Editorial Director. Your job is to arrange articles to tell a story."
        user_prompt = f"""
        Here are the draft topics for our newsletter.
        
        {context}
        
        **Task:**
        Reorder these topics (IDs) to create the best narrative flow.
        - Start with the most impactful/foundational topic.
        - Group related topics (e.g., Hardware -> Model -> Application).
        - End with a forward-looking or thought-provoking topic.
        
        **Output STRICT JSON:**
        {{
            "order": [2, 0, 1, 3], // The new sequence of IDs
            "reasoning": "Started with hardware basics (ID 2), then moved to..."
        }}
        """
        
        try:
            response = await self.llm.generate(prompt=user_prompt, system_prompt=system_prompt)
            import json
            import re
            
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                new_order = data.get('order', [])
                
                # Validate order: must contain all original indices exactly once
                if sorted(new_order) == list(range(len(topic_blocks))):
                    print(f"DEBUG: Reordered topics: {new_order}")
                    return [topic_blocks[i] for i in new_order]
                else:
                    print("DEBUG: Invalid reorder received. Keeping original.")
            
        except Exception as e:
            print(f"DEBUG: Arrangement failed: {e}")
            
        return topic_blocks

    async def generate_editor_intro(self, topic_blocks: List[str]) -> str:
        """
        Generates a warm, humorous, and enthusiastic opening for the newsletter.
        """
        titles = []
        for block in topic_blocks:
            lines = block.strip().split('\n')
            # Extract first title-like thing
            for line in lines:
                if line.strip().startswith('#') or (len(line.strip()) > 0 and len(line.strip()) < 100):
                    titles.append(line.replace('#', '').strip())
                    break
        
        titles_str = "\n- ".join(titles[:5])
        
        system_prompt = (
            "你是一位充滿熱情、幽默且專業的『鍛碼匠』總編輯。你的文字非常有溫度，像是老朋友在早餐咖啡時間分享這週最酷的發現。"
            "風格：熱情興奮、有點極客幽默感 (Geek Humor)、專業但絕不說教。"
        )
        
        user_prompt = f"""
        # 任務：撰寫本週技術週報的總編導讀 (150-200字)
        
        這週我們挑選了這幾個主題：
        - {titles_str}
        
        **要求**：
        1. **開場**：用一個親切的問候開場，帶出一點本週的氛圍。
        2. **勾引**：用極度熱情且幽默的語氣，總結本週技術圈發生了什麼「大事」或「好玩的事」。
        3. **期待感**：讓讀者覺得「天啊，這週的內容也太精采了」，引導他們往下看。
        4. **禁止**：禁止使用「機器人式」的開頭（例如：歡迎來到本週週報）。
        
        請用繁體中文撰寫。
        """
        return await self.llm.generate(prompt=user_prompt, system_prompt=system_prompt)

    async def refine_newsletter(self, full_content: str, issue_number: str = "N/A", progress_callback=None) -> str:
        """
        Segmented Refinement Pass with Global Flow Optimization.
        """
        import re
        if '<<<TOPIC_SEPARATOR>>>' in full_content:
            topic_blocks = full_content.split('<<<TOPIC_SEPARATOR>>>')
        else:
            topic_blocks = re.split(r'\n---\n|# 主題 \d+', full_content)
            
        topic_blocks = [b.strip() for b in topic_blocks if len(b.strip()) > 200]
        
        # --- NEW: Optimize Flow ---
        msg = "正在進行全局敘事編排 (Reordering Topics)..."
        if progress_callback: progress_callback(0, len(topic_blocks)+2, msg)
        topic_blocks = await self.arrange_newsletter_flow(topic_blocks)
        
        # --- NEW: Generate Intro ---
        msg = "總編正在撰寫本週導讀..."
        if progress_callback: progress_callback(1, len(topic_blocks)+2, msg)
        intro_text = await self.generate_editor_intro(topic_blocks)
        
        refined_topics = []
        total_steps = len(topic_blocks) + len(topic_blocks) - 1 + 2 
        current_step = 2
        
        system_prompt = (
            "你是一位頂尖的科技雜誌總編輯，具備『鍛碼匠』精神：手動鍛造、專業且親民、拒絕八股、追求 Viral 級別的 Freestyle 寫作。"
            "你的目標是寫出讓人讀完覺得「這週太值得了」的高品質內容。\n\n"
            "風格準則：\n"
            "1. **強制大標題**：每篇文章開頭**必須**使用 `## [標題]`。這非常重要，因為這是區分主題的關鍵。標題要吸睛、具備雜誌感。\n"
            "2. **拒絕重複與模板**：\n"
            "   - **禁止**每篇都用『一秒裝懂金句』。整份週報中，頂多只能出現一次這類區塊，或者乾脆不用。\n"
            "   - 文章結構要 Freestyle：有的直接切入、有的用對話開場、有的用數據震撼。拒絕所有機器人式的固定格式。\n"
            "3. **三明治包裝法**：先講中文生活比喻，括號標註技術術語，最後給出體感結果。例：『短期記憶 (activations) 會像滾雪球一樣膨脹...』\n"
            "4. **連結與書籤**：外部網址必用 `<a href=\"URL\" target=\"_blank\">描述文字</a>`；術語書籤必用 `[術語](#term-術語)`。\n"
            "5. **⚠️ 嚴格禁止**：絕對禁止在文末產生『術語整理』、『劃重點』或定義清單。\n"
        )

        for i, block in enumerate(topic_blocks):
            msg = f"正在鍛造第 {i+1}/{len(topic_blocks)} 篇主題文章..."
            if progress_callback: progress_callback(current_step, total_steps, msg)
            
            user_prompt = f"""
            # 任務：將以下素材鍛造成一篇『具備雜誌質感』的科技故事 (400-600字)
            
            **核心指令 (絕對優先)**：
            - **大標題**：開頭第一行必須且只能是 `## [你的創意標題]`。不要加引號、不要加額外描述。
            
            **寫作要求**：
            - **連結開啟新分頁**：外部網址必須使用 `<a href="URL" target="_blank">描述文字</a>`。
            - **書籤標註**：關鍵術語使用 `[術語](#term-術語)`。
            - **拒絕模板**：不要使用固定的框架。本篇請直接用純文字敘事，不要使用 blockquote 或任何『金句』區塊。
            
            **素材**：
            {block}
            """
            refined = await self.llm.generate(prompt=user_prompt, system_prompt=system_prompt)
            # 強制過濾潛在的術語整理區塊，避免模型幻覺
            refined = re.split(r'### 術語整理|術語整理|劃重點|### 劃重點|### 術語', refined)[0].strip()
            
            # 安全檢查：如果模型漏寫了 ## 標題，嘗試補回（從素材中抓第一行）
            if not refined.startswith('##'):
                original_title = block.split('\n')[0].replace('#', '').strip()
                refined = f"## {original_title}\n\n{refined}"
                
            refined_topics.append(refined)
            current_step += 1

        # Generate Transitions (Flow Agent)
        header_issue = f"<span style='font-size: 14px; color: #888; font-weight: normal; vertical-align: middle; margin-left: 12px;'>Issue: {issue_number}</span>"
        final_sections = [f"# 鍛碼匠技術週報 {header_issue}\n\n{intro_text}\n\n---"]
        
        final_sections.append(refined_topics[0])
        for i in range(1, len(refined_topics)):
            msg = f"正在生成第 {i} 與 {i+1} 篇之間的轉場..."
            if progress_callback: progress_callback(current_step, total_steps, msg)
            
            flow_prompt = f"""
            你現在是總編。請寫一段 50-80 字的**轉場文字**。不要使用標題。語氣要自然、興奮且 Freestyle。
            """
            transition = await self.llm.generate(prompt=flow_prompt, system_prompt="You are the Newsletter Host.")
            final_sections.append(f"\n\n{transition}\n\n")
            final_sections.append(refined_topics[i])
            current_step += 1

        # Append Glossary & References
        msg = "正在整理生字表與參考文獻..."
        if progress_callback: progress_callback(current_step, total_steps, msg)
        
        refined_full_content = "\n\n".join(final_sections)
        
        appendices_prompt = f"""
        You are the Archive Master.
        
        Task 1: Generate "💡 鍛碼匠劃重點"
        - Scan the "Final Polished Content" below for ALL terms marked with `[Term](#term-ID)`.
        - Define EVERY SINGLE ONE. 
        - **Style**: Humorously roast the complexity while being informative.
        - Format: `<a name="term-術語"></a>**術語**: [幽默吐槽解釋]`
        
        Task 2: Generate "🔗 延伸閱讀與來源 (References)"
        - Extract ALL URLs.
        - Format: `1. [繁體中文標題] - <a href="URL" target="_blank">URL</a>`
        
        Final Polished Content:
        {refined_full_content}
        """
        appendices = await self.llm.generate(prompt=appendices_prompt, system_prompt="You are the Archive Master.")
        
        footer = (
            "\n\n---\n\n"
            "<div style='text-align: center; color: #888; font-size: 14px; line-height: 1.8;'>\n"
            "  <p>網站、數位應用開發選擇 <strong>鍛碼匠</strong> <a href='https://fordige.com' target='_blank' style='color: #1b8f7a; text-decoration: none;'>fordige.com</a></p>\n"
            "  <p><strong>鍛碼匠數位創意有限公司</strong></p>\n"
            "  <p>統一編號：60476010</p>\n"
            "</div>"
        )
        
        if progress_callback: progress_callback(total_steps, total_steps, "終審完成！")
        return refined_full_content + "\n\n---\n\n" + appendices + footer

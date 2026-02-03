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

    async def refine_newsletter(self, full_content: str, progress_callback=None) -> str:
        """
        Segmented Refinement Pass with Global Flow Optimization.
        """
        # Split input into topics using the unique separator
        import re
        if '<<<TOPIC_SEPARATOR>>>' in full_content:
            topic_blocks = full_content.split('<<<TOPIC_SEPARATOR>>>')
        else:
            # Fallback for old cache compatibility
            topic_blocks = re.split(r'\n---\n|# 主題 \d+', full_content)
            
        topic_blocks = [b.strip() for b in topic_blocks if len(b.strip()) > 200]
        
        # --- NEW: Optimize Flow ---
        msg = "正在進行全局敘事編排 (Reordering Topics)..."
        if progress_callback: progress_callback(0, len(topic_blocks)+1, msg)
        topic_blocks = await self.arrange_newsletter_flow(topic_blocks)
        
        refined_topics = []
        total_steps = len(topic_blocks) + len(topic_blocks) - 1 + 1 # Topics + Transitions + Appendix
        current_step = 0
        
        system_prompt = (
            "你是一位『科技說書人』(Tech Storyteller)。你的目標是將艱澀的前沿技術，翻譯成一般人也能聽懂、甚至覺得『超酷』的生活故事。"
            "風格要求：\n"
            "1. **生活化**：拒絕堆砌術語。如果必須用術語，請立刻用一個生活比喻來解釋 (例如：『KV Cache 就像大腦的暫存區...』)。\n"
            "2. **好奇心驅動**：用『為什麼？』、『你相信嗎？』來引導讀者。文章要像在跟朋友喝咖啡聊八卦一樣輕鬆有趣。\n"
            "3. **應用導向**：讀者不在乎數學公式，他們在乎『這能拿來幹嘛？』、『這會怎麼改變我的生活？』。\n"
            "4. **語言**：繁體中文 (Traditional Chinese)。語氣要熱情、幽默、有溫度。\n"
        )

        for i, block in enumerate(topic_blocks):
            msg = f"正在轉譯第 {i+1}/{len(topic_blocks)} 篇主題為生活化故事..."
            print(f"DEBUG: {msg}")
            if progress_callback: progress_callback(current_step, total_steps, msg)
            
            user_prompt = f"""
            # 任務：將以下技術素材改寫為一篇『引人入勝的科普故事』(400-600字)
            
            請將【Hook -> Story -> Cool Factor -> Takeaway】的框架**內化**到文章中，**不要**直接使用這些詞作為標題。文章應該像一篇流暢的科技專欄或極客小說。
            
            **寫作指南**：
            1. **標題**：使用 `## [吸睛的主標題]`。
            2. **開場 (Hook)**：第一段直接用一個反直覺的現象、迷思或生活場景開場，抓住讀者眼球。
            3. **中段 (Story & Cool)**：用流暢的段落講述技術原理與應用。可以使用 `### [描述性小標題]` (如 "大腦的筆記本"、"速度的代價") 來分段，但不要用 "故事"、"應用" 這種生硬標題。
            4. **結尾 (Takeaway)**：最後一段給出一個有力的觀點或對未來的展望。
            5. **引用**：文中必須自然地包含來源連結。
            
            **目標感覺**：
            讀起來要像是在看《WIRED》或《The Verge》的深度專欄，而不是教科書或條列式報告。流暢、自然、一口氣讀完。
            
            **原始素材 (Raw Material)**：
            {block}
            """
            refined = await self.llm.generate(prompt=user_prompt, system_prompt=system_prompt)
            refined_topics.append(refined)
            current_step += 1

        # Generate Transitions (Flow Agent)
        final_sections = [refined_topics[0]]
        for i in range(1, len(refined_topics)):
            msg = f"正在生成第 {i} 與 {i+1} 篇之間的轉場..."
            print(f"DEBUG: {msg}")
            if progress_callback: progress_callback(current_step, total_steps, msg)
            
            flow_prompt = f"""
            你現在是『科技說書人』。請寫一段 50-80 字的**轉場文字 (Bridge)**。
            
            前一個故事結束於：
            "{refined_topics[i-1][-200:]}..." 
            
            下一個故事將要講：
            "{refined_topics[i][:200]}..."
            
            **任務**：
            找出這兩者之間微妙的關聯。用一種「這讓你聯想到了什麼？」或「但事情沒這麼簡單...」的口吻，把讀者自然地帶入下一個故事。
            **不要**使用任何標題 (如 "說書人中場休息")，直接寫出那段流暢的轉場文字，讓它看起來像是文章的一部分。
            """
            transition = await self.llm.generate(prompt=flow_prompt, system_prompt="You are the Newsletter Host.")
            final_sections.append(f"\n\n{transition}\n\n") # 移除 Blockquote 符號，使其更融入正文
            final_sections.append(refined_topics[i])
            current_step += 1

        # Append Glossary & References (Extracted from all blocks)
        msg = "正在整理生字表與參考文獻..."
        if progress_callback: progress_callback(current_step, total_steps, msg)
        
        refined_full_content = "\n\n".join(final_sections)
        
        appendices_prompt = f"""
        You are the Archive Master.
        
        Task 1: Generate "💡 科技豆知識 (Tech Trivia)"
        - Select 5-8 technical terms from the text that might confuse a layperson.
        - Explain them in 1 sentence using a **fun metaphor**. 
        - STRICTLY use Traditional Chinese (繁體中文).
        - Format: **Term**: Metaphor/Explanation
        
        Task 2: Generate "🔗 延伸閱讀與來源 (References)"
        - Extract ALL URLs/Links from BOTH the "Original Draft" and "Final Polished Content".
        - For each URL, generate a **descriptive Traditional Chinese title** based on the content context.
        - Format: `1. [繁體中文標題] - URL`
        
        Final Polished Content:
        {refined_full_content}
        
        Original Draft (for checking missing links):
        {full_content}
        """
        appendices = await self.llm.generate(prompt=appendices_prompt, system_prompt="You are the Archive Master.")
        
        if progress_callback: progress_callback(total_steps, total_steps, "終審完成！")
        
        return refined_full_content + "\n\n---\n\n" + appendices

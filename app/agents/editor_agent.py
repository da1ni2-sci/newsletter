import json
import re
from typing import List, Dict, Any
from app.core.interfaces import LLMProvider

class EditorAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def select_top_topics(self, clusters: List[Dict[str, Any]], num_select: int = 5) -> List[Dict[str, Any]]:
        """
        Uses LLM to evaluate top clusters and select the best ones.
        """
        # 1. Prepare candidates (Top 50 from UI)
        candidates = clusters 
        
        context_str = ""
        for i, cluster in enumerate(candidates):
            title = cluster['representative_title']
            size = cluster['size']
            
            # Analyze sources for diversity
            sources = set()
            for art in cluster['articles']:
                src = art.get('source_type', 'unknown')
                sources.add(src)
            source_tags = ", ".join(list(sources))
            
            member_summaries = [f"- [{art.get('source_type', 'web')}] {art['title']}" for art in cluster['articles'][:4]] # Show slightly more
            
            context_str += f"ID {i}: {title} (Size: {size} | Sources: {source_tags})\n"
            context_str += "\n".join(member_summaries) + "\n---\n"

        # 2. Build Prompt
        system_prompt = (
            "You are the Editor-in-Chief. You MUST respond in VALID JSON format. "
            "Your goal is to select the 5 most fascinating tech stories from the candidates below. "
        )
        
        user_prompt = f"""
Select exactly {num_select} topics from the list below. 

**CRITICAL SELECTION CRITERIA (The "Synthesis Value"):**
1. **Diversity is King**: PRIORITIZE clusters that combine materials from DIFFERENT sources (e.g., Reddit discussions + Arxiv papers + Tech Blogs).
2. **Cross-Pollination**: Look for topics where these diverse sources CONFIRM, CONTRADICT, or COMPLEMENT each other. This creates a richer, more engaging narrative.
3. **Avoid Monoculture**: A cluster with 10 articles all from the same blog is boring. A cluster with 3 articles from 3 different domains (Engineering vs. Academic vs. Social) is GOLD.
4. **Coherence**: Ensure the diverse articles actually talk about the same core innovation or event.

Candidates:
{context_str}

Output Format (STRICT JSON):
{{
    "selections": [
        {{ 
            "id": 0, 
            "reason": "Explain WHY this was selected. Mention the diversity of sources (e.g. 'Combines Reddit debate with Arxiv proof').",
            "editor_title": "A specific, punchy title for this narrative"
        }}
    ]
}}

**Return ONLY JSON.**
"""
        # 3. Call LLM
        response = await self.llm.generate(prompt=user_prompt, system_prompt=system_prompt)
        
        # 4. Parse Response
        try:
            clean_json = self._extract_json(response)
            data = json.loads(clean_json)
            
            selections = []
            if isinstance(data, list): selections = data
            elif isinstance(data, dict): selections = data.get('selections', [])
            
            selected_clusters = []
            for item in selections:
                idx = item.get('id')
                if idx is not None and 0 <= int(idx) < len(candidates):
                    cluster = candidates[int(idx)]
                    cluster['editor_reason'] = item.get('reason') or "AI 根據內容深度與影響力選出。"
                    # 新增：優先使用總編撰寫的主題標題
                    cluster['display_title'] = item.get('editor_title') or cluster['representative_title']
                    selected_clusters.append(cluster)
            
            # If parsing failed to get enough items, use fallback
            if len(selected_clusters) < num_select:
                raise ValueError("Insufficient selections")
                
            return selected_clusters

        except Exception as e:
            print(f"DEBUG: EditorAgent selection failed: {e}. Fallback to Top N.")
            # FALLBACK LOGIC: Ensure reasons are added!
            selected = candidates[:num_select]
            for i, c in enumerate(selected):
                if 'editor_reason' not in c or not c['editor_reason']:
                    c['editor_reason'] = f"此主題得分 ({c['score']}) 極高，包含 {c['size']} 篇深度素材，具備高度報導價值。"
            return selected

    def _extract_json(self, text: str) -> str:
        """Extracts JSON block from text."""
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match: return match.group(1).strip()
        match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if match: return match.group(1).strip()
        return text.strip()

    async def generate_research_prompt(self, topic: Dict[str, Any]) -> str:
        title = topic['representative_title']
        context_parts = []
        for art in topic['articles']:
            text = art.get('content') or art.get('summary', '')
            context_parts.append(f"Source ({art.get('source_type')}): {text[:2000]}")
            
        existing_knowledge = "\n\n".join(context_parts)
        
        system_prompt = "You are a Senior Technical Researcher. Generate a Google Gemini Deep Research Prompt."
        
        user_prompt = f"""
**Topic:** {title}
**Context:** {existing_knowledge}

Generate a single, aggressive, deep-dive prompt for Google Gemini to find MISSING technical details, comparisons, and community sentiments. 
Return ONLY the prompt.
"""
        return await self.llm.generate(prompt=user_prompt, system_prompt=system_prompt)
from typing import List, Dict, Any, Optional
from app.core.interfaces import LLMProvider, VectorStoreProvider, EmbeddingProvider

class NewsletterAgent:
    def __init__(
        self,
        llm: LLMProvider,
        vector_store: VectorStoreProvider,
        embedding: EmbeddingProvider,
        collection_name: str = "news_articles"
    ):
        self.llm = llm
        self.vector_store = vector_store
        self.embedding = embedding
        self.collection_name = collection_name

    async def generate_newsletter(self, topic: str, num_articles: int = 5) -> str:
        # 1. Retrieve relevant articles from Vector Store
        query_vector = await self.embedding.embed_query(topic)
        search_results = await self.vector_store.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=num_articles
        )

        if not search_results:
            return f"No articles found about '{topic}' in the database."

        # 2. Format context for LLM
        context_parts = []
        for i, hit in enumerate(search_results):
            payload = hit['payload']
            metadata = []
            if payload.get('author'): metadata.append(f"Author: {payload['author']}")
            if payload.get('upvotes'): metadata.append(f"Upvotes: {payload['upvotes']}")
            if payload.get('github_stars'): metadata.append(f"GitHub Stars: {payload['github_stars']}")
            
            metadata_str = " | ".join(metadata)
            
            context_parts.append(
                f"--- Article {i+1} ---\n"
                f"Title: {payload.get('title')}\n"
                f"Metadata: {metadata_str}\n"
                f"Summary: {payload.get('summary')}\n"
                f"Link: {payload.get('link')}\n"
            )
        
        context_text = "\n".join(context_parts)

        # 3. Create Prompt
        system_prompt = (
            "你是一位專業的科技電子報編輯。你的目標是為讀者篩選並總結最重要的此主題新聞。"
            "請使用繁體中文 (Traditional Chinese) 撰寫，風格專業、引人入勝且簡潔。"
        )
        
        user_prompt = (
            f"根據以下關於 '{topic}' 的新聞文章，請撰寫一份電子報草稿。"
            "對於每篇文章，請提供一個吸引人的標題、簡短摘要（2-3 句話）以及原文連結。"
            "最後，請針對整體主題撰寫一段 '為什麼這很重要 (Why this matters)' 的結語。\n\n"
            "參考內容 (CONTEXT):\n"
            f"{context_text}\n\n"
            "電子報輸出 (Markdown 格式):"
        )

        # 4. Generate with LLM
        response = await self.llm.generate(prompt=user_prompt, system_prompt=system_prompt)
        return response

    async def synthesize_topic_article(self, topic: Dict[str, Any]) -> str:
        """
        Synthesizes raw cluster content into a high-quality article using Adversarial Editing.
        Cycle: Draft -> Critique -> Final.
        """
        title = topic.get('display_title') or topic['representative_title']
        research_report = topic.get('research_report', 'No additional research provided.')
        
        # 1. Prepare Materials
        raw_materials = []
        for art in topic['articles']:
            content = art.get('content') or art.get('summary', '')
            # Add source type hint to help LLM understand context (e.g. Reddit vs Arxiv)
            src_type = art.get('source_type', 'Web')
            raw_materials.append(f"Source ({src_type}): {art.get('title')}\nContent: {content[:8000]}\nURL: {art.get('link')}")
        materials_text = "\n\n---\n\n".join(raw_materials)

        # 2. Phase A: Initial Draft (The Enthusiast)
        system_prompt = (
            "You are a 'Tech Hunter' - an enthusiastic technology journalist who loves discovering breakthroughs. "
            "Your writing style is vibrant, opinionated, and connects the dots. "
            "You HATE boring, dry technical manuals. You LOVE narratives that show human impact."
        )
        
        user_prompt = f"""
        Topic: {title}
        
        Materials:
        {materials_text}
        
        Research:
        {research_report}

        **Task:** 
        Cook these raw ingredients into a fascinating story. 
        - **Don't just list facts.** Find the *conflict*, the *surprise*, or the *game-changer* aspect.
        - **Mix the flavors:** If you have a Reddit comment and a Paper, show how the community is reacting to the science.
        - **Tone:** Excited but grounded in fact. Use active verbs.
        
        **Constraint:**
        - You MUST cite your sources within the text (e.g., "As discussed in [Source Name]...") 
        - Include a "References" section at the end with all URLs.
        
        Write the draft in Traditional Chinese (繁體中文).
        """
        
        draft = await self.llm.generate(prompt=user_prompt, system_prompt=system_prompt)

        # 3. Phase B: Critique (The Boredom Police)
        critique_prompt = f"""
        You are a ruthless Editor who hates boring content. Review the following draft:
        
        {draft}

        **Critique Checklist:**
        1. **The 'Yawn' Test:** Is the opening boring? Does it read like a Wikipedia entry? (If yes, scream about it).
        2. **The 'So What?' Test:** Did it explain WHY this matters to a normal human, or just list specs?
        3. **Connection:** Did it successfully weave together the different sources, or does it feel like separate summaries pasted together?
        4. **Citations:** Are the links preserved? (This is non-negotiable).
        
        Provide bullet points on how to make it more EXCITING and COHESIVE.
        """
        critique = await self.llm.generate(prompt=critique_prompt, system_prompt="You are a Critical Reader.")

        # 4. Phase C: Final Refinement (The Polisher)
        final_prompt = f"""
        Original Materials: {materials_text}
        Initial Draft: {draft}
        Critique to address: {critique}

        **Goal:** rewrite the article to be **vibrant, insightful, and flowing**. 
        - Address the critique to remove "boring" parts.
        - Amplify the "Cool Factor".
        - Ensure the narrative flows logically from problem -> solution -> impact.
        - **CRITICAL:** Keep all citations and the References section.
        
        Output in clean Markdown (Traditional Chinese).
        """
        final_article = await self.llm.generate(prompt=final_prompt, system_prompt=system_prompt)
        return final_article

from typing import List, Dict, Any, Optional
from app.core.interfaces import LLMProvider, VectorStoreProvider, EmbeddingProvider
# Import the new Research Tools
from app.tools.research_tools import ResearchAgent, WebSearchTool

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
        # Initialize Research Agent
        self.research_agent = ResearchAgent(llm)
        self.web_tool = WebSearchTool() # Placeholder for actual search implementation

    async def _perform_deep_research(self, topic: Dict[str, Any]) -> str:
        """
        Orchestrates the multi-step deep retrieval process.
        1. Formulate Queries
        2. (Mock) Execute Search - In production, this needs a real Search API key (SerpAPI/Google).
        3. Fetch Content
        4. Summarize
        """
        title = topic.get('display_title') or topic['representative_title']
        summary = topic.get('summary', '')
        
        # 1. Formulate Queries
        queries = await self.research_agent.formulate_queries(title, summary)
        print(f"DEBUG: Generated queries for '{title}': {queries}")
        
        # 2. Execute Search (Real SerpAPI + Playwright)
        print(f"DEBUG: Executing Search for queries: {queries}")
        results = []
        # Limit to first query to save time/tokens if needed, or loop all. 
        # Let's do all queries but limit results per query.
        for q in queries:
            search_hits = await self.web_tool.search_google(q)
            # Take top 1 result per query to keep it fast
            for hit in search_hits[:1]:
                content = await self.web_tool.fetch_page_content(hit['url'])
                if content:
                    hit['content'] = content
                    results.append(hit)
        
        # 3. Summarize Results
        if results:
            research_notes = await self.research_agent.summarize_search_results(results)
        else:
            research_notes = f"Deep Research attempted queries: {queries}, but found no accessible content."
        
        return research_notes

    async def synthesize_topic_article(self, topic: Dict[str, Any]) -> str:
        """
        Synthesizes raw cluster content into a high-quality article using Adversarial Editing.
        Cycle: Research (if missing) -> Draft -> Critique -> Final.
        """
        title = topic.get('display_title') or topic['representative_title']
        
        # --- NEW: Check if Research Report already exists (Manual or from Phase 2) ---
        research_report = topic.get('research_report', '').strip()
        
        if not research_report or "Deep Research Active" in research_report:
            print(f"--- Starting Deep Retrieval for {title} ---")
            deep_research_report = await self._perform_deep_research(topic)
            topic['research_report'] = deep_research_report
            research_report = deep_research_report
        else:
            print(f"--- Using existing Research Report for {title} ---")
        # ---------------------------------------------------------------------------

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

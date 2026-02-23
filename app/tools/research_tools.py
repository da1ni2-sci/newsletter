import json
import asyncio
import httpx
from typing import List, Dict, Any
from app.ingestion.local_playwright_strategy import LocalPlaywrightStrategy

# This should ideally be in env vars, but we inject it here as requested
SERP_API_KEY = "4ac16197f327297233d52b90e6f439bdb5a9748d930bdd13d690161500b67558"

class WebSearchTool:
    """
    Real implementation using SerpAPI for search and LocalPlaywrightStrategy for scraping.
    """
    def __init__(self, max_results: int = 3):
        self.max_results = max_results
        self.scraper = LocalPlaywrightStrategy(headless=True)

    async def search_google(self, query: str) -> List[Dict[str, str]]:
        """
        Performs a real Google search via SerpAPI.
        """
        print(f"DEBUG: Searching Google via SerpAPI for: {query}")
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": SERP_API_KEY,
            "num": self.max_results,
            "engine": "google"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=20.0)
                response.raise_for_status()
                data = response.json()
                
                organic_results = data.get("organic_results", [])
                results = []
                for result in organic_results:
                    results.append({
                        "title": result.get("title"),
                        "url": result.get("link"),
                        "snippet": result.get("snippet", "")
                    })
                return results
            except Exception as e:
                print(f"ERROR: SerpAPI search failed: {e}")
                return []

    async def fetch_page_content(self, url: str) -> str:
        """
        Fetches the content of a URL using the existing LocalPlaywrightStrategy.
        """
        print(f"DEBUG: Fetching content for: {url}")
        try:
            content = await self.scraper.fetch_full_content(url)
            return content
        except Exception as e:
            print(f"ERROR: Content fetch failed for {url}: {e}")
            return ""

class ResearchAgent:
    """
    Agent responsible for 'Deep Retrieval'.
    It analyzes a topic, formulates search queries, and summarizes findings.
    """
    def __init__(self, llm_provider):
        self.llm = llm_provider

    async def formulate_queries(self, topic_title: str, topic_summary: str) -> List[str]:
        prompt = f"""
        Given the tech topic: "{topic_title}"
        Summary: "{topic_summary}"
        
        Generate 3 specific Google search queries to find:
        1. Recent technical breakdowns or papers (site:arxiv.org OR site:github.com).
        2. Community discussions (site:reddit.com OR site:news.ycombinator.com).
        3. Official blog posts or technical documentation.
        
        Return ONLY a JSON list of strings. Example: ["query1", "query2"]
        """
        response = await self.llm.generate(prompt=prompt)
        try:
            # Simple cleanup to ensure JSON parsing
            clean_json = response.strip().replace("```json", "").replace("```", "")
            if "[" not in clean_json: 
                # Fallback if LLM just chats
                return [f"{topic_title} technical details", f"{topic_title} reddit discussion"]
            return json.loads(clean_json)
        except:
            return [f"{topic_title} technical analysis", f"{topic_title} performance benchmarks"]

    async def summarize_search_results(self, search_results: List[Dict[str, str]]) -> str:
        if not search_results:
            return "No additional research found."
            
        content_block = "\n\n".join([f"Source: {r['url']}\nSnippet: {r.get('snippet','')}\nContent Preview: {r['content'][:3000]}" for r in search_results])
        
        prompt = f"""
        You are a Technical Researcher. Analyze the following scraped data to extract HARD technical details that might be missing from the original news.
        
        Focus on: 
        - Architecture diagrams or descriptions.
        - Benchmark numbers.
        - Implementation details.
        - User sentiment/controversy.
        
        Data:
        {content_block}
        
        Output a structured research note (Markdown) that the writer can use.
        If the content is irrelevant or blocked, say so.
        """
        return await self.llm.generate(prompt=prompt)

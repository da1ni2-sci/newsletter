import feedparser
from typing import List, Dict, Any
from app.core.interfaces import IngestionStrategy
import httpx
from bs4 import BeautifulSoup

class RSSStrategy(IngestionStrategy):
    """Strategy to fetch and parse RSS feeds"""
    
    async def fetch(self, source_url: str) -> List[Dict[str, Any]]:
        # RSS feed parsing is usually synchronous, but we can wrap it
        # or use httpx to fetch and then parse.
        async with httpx.AsyncClient() as client:
            response = await client.get(source_url)
            feed = feedparser.parse(response.text)
            
            results = []
            for entry in feed.entries:
                results.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": self._clean_html(entry.get("summary", "")),
                    "published": entry.get("published", ""),
                    "source_type": "RSS"
                })
            return results

    def _clean_html(self, html_content: str) -> str:
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator=" ", strip=True)

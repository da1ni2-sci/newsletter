from typing import List, Dict, Any
from app.core.interfaces import IngestionStrategy
from firecrawl import FirecrawlApp
import os
import time
import json

class FirecrawlStrategy(IngestionStrategy):
    """Strategy to fetch content using Firecrawl API (good for generic websites)"""
    
    def __init__(self, api_key: str = None, api_url: str = None):
        self.api_key = api_key or "fc-dummy-key" # Self-hosted doesn't strict check keys usually
        # Pass api_url if provided, otherwise FirecrawlApp uses default
        self.app = FirecrawlApp(api_key=self.api_key, api_url=api_url)

    async def fetch(self, source_url: str) -> List[Dict[str, Any]]:
        print(f"DEBUG: Fetching {source_url} using Firecrawl scrape...")
        
        try:
            # 使用 scrape 方法，並加上捲動動作
            # 注意: 根據 Firecrawl 版本，params 結構可能不同。
            # 這裡我們嘗試最標準的傳參方式。
            
            actions = [
                {"type": "wait", "milliseconds": 2000},
                {"type": "scroll", "direction": "down", "distance": 1000},
                {"type": "wait", "milliseconds": 2000}
            ]
            
            # 使用 params 封裝參數 (v1 風格) 或是直接傳參 (v0 風格)，視 SDK 版本而定。
            # 根據之前的錯誤訊息，SDK 似乎支援直接參數 formats=...
            
            print("DEBUG: Sending request to Firecrawl API...")
            response = self.app.scrape(
                source_url, 
                formats=['markdown', 'html'], 
                actions=actions
            )
            print("DEBUG: Request returned.")

            # 處理回應資料
            data = {}
            if hasattr(response, 'model_dump'):
                 data = response.model_dump()
            elif hasattr(response, '__dict__'):
                 data = response.__dict__
            elif isinstance(response, dict):
                 data = response
            else:
                 # Fallback
                 data = {
                     'markdown': getattr(response, 'markdown', ''),
                     'metadata': getattr(response, 'metadata', {})
                 }
            
            # Debug: 打印部分回應以檢查
            # print(f"DEBUG Response keys: {data.keys()}")

            metadata = data.get('metadata', {})
            # Ensure metadata is dict
            if hasattr(metadata, 'model_dump'):
                metadata = metadata.model_dump()
            elif hasattr(metadata, '__dict__'):
                metadata = metadata.__dict__
            
            title = metadata.get('title', 'No Title')
            description = metadata.get('description', '')
            markdown_content = data.get('markdown', '')
            
            print(f"DEBUG: Scraped Title: {title}")
            print(f"DEBUG: Content Length: {len(markdown_content)}")

            # 如果內容太短，可能是失敗了
            if len(markdown_content) < 500:
                print("WARNING: Content seems too short. Possible scrape failure or blocked.")
            
            if not description:
                description = markdown_content[:500] + "..."
            
            return [{
                "title": title,
                "link": source_url,
                "summary": description,
                "content": markdown_content,
                "published": metadata.get('date', 'Unknown'),
                "source_type": "Web (Firecrawl)"
            }]
            
        except Exception as e:
            print(f"ERROR: Firecrawl scrape failed: {str(e)}")
            # 我們這裡不只要 print，最好能拋出異常讓 UI 顯示，或者回傳錯誤訊息
            # 但為了不破壞介面定義，我們先 print 到 console
            import traceback
            traceback.print_exc()
            return []

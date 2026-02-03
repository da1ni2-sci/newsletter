import sys
import os
import json
import asyncio
from typing import Dict, List, Any
from datetime import datetime

# Add project root to sys.path to allow imports from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ingestion.firecrawl_strategy import FirecrawlStrategy

# ANSI colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def load_sources(config_path: str) -> Dict[str, List[Dict[str, str]]]:
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

async def test_source(strategy: FirecrawlStrategy, category: str, source: Dict[str, str]) -> Dict[str, Any]:
    url = source['url']
    name = source['name']
    print(f"Testing {category} - {name} ({url})...", end='', flush=True)
    
    start_time = datetime.now()
    try:
        # fetch is async but FirecrawlStrategy currently uses sync call inside? 
        # Let's check FirecrawlStrategy implementation.
        # It's defined as async def fetch, so we await it.
        results = await strategy.fetch(url)
        duration = (datetime.now() - start_time).total_seconds()
        
        if results:
            content_len = len(results[0].get('content', ''))
            print(f" {GREEN}SUCCESS{RESET} ({duration:.2f}s) - Content Length: {content_len} chars")
            return {
                "name": name,
                "url": url,
                "status": "SUCCESS",
                "duration": duration,
                "content_preview": results[0].get('summary', '')[:100]
            }
        else:
            print(f" {YELLOW}EMPTY{RESET} ({duration:.2f}s)")
            return {
                "name": name,
                "url": url,
                "status": "EMPTY",
                "duration": duration,
                "error": "No data returned"
            }
            
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        print(f" {RED}FAILED{RESET} ({duration:.2f}s) - {str(e)}")
        return {
            "name": name,
            "url": url,
            "status": "FAILED",
            "duration": duration,
            "error": str(e)
        }

async def main():
    # Configuration
    config_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'config', 'sources.json')
    api_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:3002")
    
    print(f"Loading sources from: {config_path}")
    print(f"Using Firecrawl API at: {api_url}")
    
    if not os.path.exists(config_path):
        print(f"{RED}Error: Config file not found!{RESET}")
        return

    sources_map = load_sources(config_path)
    
    # Initialize Strategy
    # Note: FirecrawlStrategy implementation in previous turn didn't explicitly use api_url in __init__ if I recall correctly?
    # Let me double check the file content I read.
    # It has: def __init__(self, api_key: str = None, api_url: str = None):
    # and self.app = FirecrawlApp(api_key=self.api_key, api_url=api_url)
    # So it is supported.
    strategy = FirecrawlStrategy(api_url=api_url)
    
    results_summary = []
    
    for category, sources in sources_map.items():
        print(f"\n--- Category: {category} ---")
        for source in sources:
            result = await test_source(strategy, category, source)
            results_summary.append(result)
            
    # Print Final Report
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    success_count = sum(1 for r in results_summary if r['status'] == 'SUCCESS')
    total_count = len(results_summary)
    
    print(f"Total Sources: {total_count}")
    print(f"Successful:    {success_count}")
    print(f"Failed/Empty:  {total_count - success_count}")
    print("-" * 50)
    
    for r in results_summary:
        status_color = GREEN if r['status'] == 'SUCCESS' else RED
        print(f"[{status_color}{r['status']}{RESET}] {r['name']:<30} {r['url']}")

if __name__ == "__main__":
    asyncio.run(main())

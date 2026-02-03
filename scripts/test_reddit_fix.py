import asyncio
import sys
import os

# Add the project root to sys.path to import app modules
sys.path.append(os.getcwd())

from app.ingestion.local_playwright_strategy import LocalPlaywrightStrategy

async def test_reddit():
    strategy = LocalPlaywrightStrategy(headless=True)
    url = "https://www.reddit.com/r/LocalLLaMA/"
    print(f"Testing Reddit fetch for: {url}")
    results = await strategy.fetch(url)
    
    print(f"\n--- Results ---")
    print(f"Total items found: {len(results)}")
    for i, item in enumerate(results[:5]):
        print(f"{i+1}. {item['title']} ({item.get('upvotes')} upvotes)")
        print(f"   Link: {item['link']}")
        print(f"   Summary: {item['summary'][:100]}...")

if __name__ == "__main__":
    asyncio.run(test_reddit())


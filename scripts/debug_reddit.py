import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import re

async def stealth_async(page):
    await Stealth().apply_stealth_async(page)

async def debug_reddit(url):
    print(f"--- 開始 Reddit 深度偵錯: {url} ---")
    
    stealth_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=stealth_args)
        # 嘗試模擬更真實的桌面環境
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        await stealth_async(page)
        
        try:
            print("1. 正在導航至網頁 (等待 networkidle)...")
            response = await page.goto(url, wait_until="networkidle", timeout=60000)
            
            print(f"2. HTTP 狀態碼: {response.status if response else '無回應'}")
            print(f"3. 頁面標題: '{await page.title()}'")
            
            # 額外等待 JS 渲染
            print("4. 等待 5 秒讓動態內容載入...")
            await asyncio.sleep(5)
            
            content = await page.content()
            
            # 檢查關鍵標籤
            articles = await page.query_selector_all('article')
            shreddit_posts = await page.query_selector_all('shreddit-post')
            links = await page.query_selector_all('a[slot="full-post-link"]')
            
            print(f"5. 結構檢測結果:")
            print(f"   - <article> 數量: {len(articles)}")
            print(f"   - <shreddit-post> 數量: {len(shreddit_posts)}")
            print(f"   - <a slot='full-post-link'> 數量: {len(links)}")
            
            if len(articles) == 0:
                print("❌ 警告：未偵測到任何文章標籤。")
                print("正在儲存原始 HTML 以供分析: debug_reddit_raw.html")
                with open("debug_reddit_raw.html", "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                print("✅ 成功偵測到內容！")
                for i, art in enumerate(articles[:3]):
                    title = await art.get_attribute('aria-label')
                    print(f"   - 範例文章 {i+1}: {title}")

        except Exception as e:
            print(f"❌ 發生錯誤: {str(e)}")
        finally:
            await browser.close()

if __name__ == "__main__":
    target = "https://www.reddit.com/r/LocalLLaMA/"
    asyncio.run(debug_reddit(target))

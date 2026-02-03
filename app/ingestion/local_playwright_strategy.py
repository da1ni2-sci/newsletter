from typing import List, Dict, Any
import re
from app.core.interfaces import IngestionStrategy
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import html2text
import asyncio
import httpx
from bs4 import BeautifulSoup
from app.ingestion.parsers import (
    parse_huggingface_papers, 
    parse_arxiv_list, 
    parse_github_trending, 
    parse_arxiv_abstract, 
    parse_github_readme, 
    parse_huggingface_models, 
    parse_hf_model_card,
    parse_reddit_list,
    parse_reddit_post_content,
    parse_hacker_news_list,
    parse_anthropic_blog,
    parse_openai_blog,
    parse_deepmind_blog,
    parse_meta_ai_blog,
    parse_amazon_science_blog
)

async def stealth_async(page):
    await Stealth().apply_stealth_async(page)

class LocalPlaywrightStrategy(IngestionStrategy):
    """Strategy to fetch content using local Playwright directly (Bypassing Firecrawl API)"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.converter = html2text.HTML2Text()
        self.converter.ignore_links = True
        self.converter.ignore_images = True
        self.converter.body_width = 0

    def _get_stealth_args(self):
        return [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certificate-errors",
            "--ignore-certificate-errors-spki-list",
            "--disable-accelerated-2d-canvas",
            "--disable-gpu",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]

    async def _create_stealth_context(self, browser):
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
            locale="en-US"
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        await context.set_extra_http_headers({
            "Referer": "https://www.google.com/",
            "Accept-Language": "en-US,en;q=0.9"
        })
        return context

    async def _fetch_abstract(self, client: httpx.AsyncClient, item: Dict[str, Any]):
        try:
            url = item['link']
            response = await client.get(url, timeout=15.0, follow_redirects=True)
            if response.status_code == 200:
                abstract = parse_arxiv_abstract(response.text)
                if abstract:
                    item['summary'] = f"{item['summary']}\n\nAbstract:\n{abstract}"
        except: pass

    async def _fetch_readme(self, client: httpx.AsyncClient, item: Dict[str, Any]):
        try:
            url = item['link']
            response = await client.get(url, timeout=15.0, follow_redirects=True)
            if response.status_code == 200:
                readme = parse_github_readme(response.text)
                if readme:
                    item['summary'] = f"{item['summary']}\n\nREADME Preview:\n{readme[:2000]}..."
        except: pass

    async def _fetch_model_card(self, client: httpx.AsyncClient, item: Dict[str, Any]):
        try:
            url = item['link']
            response = await client.get(url, timeout=15.0, follow_redirects=True)
            if response.status_code == 200:
                content = parse_hf_model_card(response.text)
                if content:
                    item['summary'] = f"{item['summary']}\n\nModel Card Preview:\n{content[:2000]}..."
        except: pass

    async def _fetch_reddit_content_playwright(self, context, item: Dict[str, Any], semaphore: asyncio.Semaphore):
        async with semaphore:
            page = await context.new_page()
            try:
                url = item['link']
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                content_html = await page.content()
                content = parse_reddit_post_content(content_html)
                if content:
                    item['summary'] = f"{item['summary']}\n\nPost Content:\n{content[:2000]}..."
            except: pass
            finally: await page.close()

    async def _enrich_arxiv_abstracts(self, items: List[Dict[str, Any]]):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        async with httpx.AsyncClient(headers=headers, verify=False) as client:
            tasks = [self._fetch_abstract(client, item) for item in items]
            await asyncio.gather(*tasks)

    async def _enrich_github_readmes(self, items: List[Dict[str, Any]]):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        async with httpx.AsyncClient(headers=headers, verify=False) as client:
            tasks = [self._fetch_readme(client, item) for item in items]
            await asyncio.gather(*tasks)

    async def _enrich_hf_model_cards(self, items: List[Dict[str, Any]]):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        async with httpx.AsyncClient(headers=headers, verify=False) as client:
            tasks = [self._fetch_model_card(client, item) for item in items]
            await asyncio.gather(*tasks)

    async def _enrich_reddit_posts(self, items: List[Dict[str, Any]], browser_context):
        semaphore = asyncio.Semaphore(3)
        tasks = [self._fetch_reddit_content_playwright(browser_context, item, semaphore) for item in items]
        await asyncio.gather(*tasks)

    async def _fetch_content_playwright(self, context, item: Dict[str, Any], semaphore: asyncio.Semaphore):
        async with semaphore:
            page = await context.new_page()
            await stealth_async(page)
            try:
                url = item['link']
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)
                content_html = await page.content()
                content = self.converter.handle(content_html)
                if content:
                    item['summary'] = f"{item['summary']}\n\nArticle Preview:\n{content[:3000]}..."
                    item['metadata'] = item.get('metadata', {})
                    item['metadata']['has_fingerprint'] = True
            except: pass
            finally: await page.close()

    async def _enrich_article_content(self, items: List[Dict[str, Any]], browser_context):
        protected_items = [i for i in items if "openai.com" in i.get('link', '') or "ai.meta.com" in i.get('link', '')]
        easy_items = [i for i in items if i not in protected_items]
        
        tasks = []
        if easy_items:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            async def run_httpx():
                async with httpx.AsyncClient(headers=headers, verify=False, timeout=15.0) as client:
                    for item in easy_items:
                        try:
                            res = await client.get(item['link'], follow_redirects=True)
                            if res.status_code == 200:
                                item['summary'] = f"{item['summary']}\n\nPreview: {self.converter.handle(res.text)[:2000]}..."
                        except: pass
            tasks.append(run_httpx())
            
        if protected_items and browser_context:
            semaphore = asyncio.Semaphore(2)
            for item in protected_items:
                tasks.append(self._fetch_content_playwright(browser_context, item, semaphore))
        
        if tasks: await asyncio.gather(*tasks)

    async def fetch_full_content(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, args=self._get_stealth_args())
            context = await self._create_stealth_context(browser)
            page = await context.new_page()
            await stealth_async(page)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                content = self.converter.handle(await page.content())
                return content[:30000]
            except: return ""
            finally: await browser.close()

    async def fetch(self, source_url: str) -> List[Dict[str, Any]]:
        print(f"DEBUG: Starting Local Playwright fetch for {source_url}")
        
        if "news.ycombinator.com" in source_url:
            from datetime import datetime, timedelta
            all_hn_results = []
            today = datetime.now()
            print(f"DEBUG: --- Initiating 7-day FULL fetch for Hacker News ---")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=self._get_stealth_args())
                context = await self._create_stealth_context(browser)
                page = await context.new_page()
                await stealth_async(page)
                
                for i in range(7):
                    target_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                    day_url = f"https://news.ycombinator.com/front?day={target_date}"
                    
                    print(f"DEBUG: [HN Progress {i+1}/7] Fetching {target_date}...")
                    try:
                        await page.goto(day_url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(1500)
                        
                        current_html = await page.content()
                        day_results = parse_hacker_news_list(current_html)
                        
                        for item in day_results:
                            item['metadata'] = item.get('metadata', {})
                            item['metadata']['hn_date'] = target_date
                        
                        # 逐日進行內容富化，這樣可以分散負擔並即時看到進度
                        if day_results:
                            print(f"DEBUG:   -> Found {len(day_results)} items. Enriching snippets...")
                            await self._enrich_article_content(day_results, context)
                            all_hn_results.extend(day_results)
                            
                        print(f"DEBUG: [HN Progress {i+1}/7] Completed {target_date}. Total gathered: {len(all_hn_results)}")
                    except Exception as e:
                        print(f"ERROR: Failed HN fetch for {target_date}: {e}")
                
                await browser.close()
                print(f"DEBUG: --- HN 7-day fetch complete. Total: {len(all_hn_results)} items. ---")
                return all_hn_results

        # --- 其他來源的標準流程 ---
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=self._get_stealth_args())
            context = await self._create_stealth_context(browser)
            page = await context.new_page()
            await stealth_async(page)
            try:
                await page.goto(source_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)
                content_html = await page.content()
                
                results = []
                if "huggingface.co/papers" in source_url:
                    results = parse_huggingface_papers(content_html)
                elif "arxiv.org/list" in source_url:
                    results = parse_arxiv_list(content_html)
                    await self._enrich_arxiv_abstracts(results)
                elif "github.com/trending" in source_url:
                    results = parse_github_trending(content_html)
                    await self._enrich_github_readmes(results)
                elif "huggingface.co/models" in source_url:
                    results = parse_huggingface_models(content_html)
                    await self._enrich_hf_model_cards(results)
                elif "reddit.com" in source_url:
                    unique_posts = {}
                    for _ in range(12):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(2000)
                        for post in parse_reddit_list(await page.content()):
                            if post['link'] not in unique_posts: unique_posts[post['link']] = post
                    results = [p for p in unique_posts.values() if int(p.get('upvotes', 0)) >= 50]
                    await self._enrich_reddit_posts(results, context)
                elif "news.ycombinator.com" in source_url:
                    results = parse_hacker_news_list(content_html)
                    await self._enrich_article_content(results, context)
                else:
                    for blog in ["anthropic.com", "openai.com", "deepmind.google", "ai.meta.com", "amazon.science"]:
                        if blog in source_url:
                            if blog == "anthropic.com": results = parse_anthropic_blog(content_html)
                            elif blog == "openai.com": results = parse_openai_blog(content_html)
                            elif blog == "deepmind.google": results = parse_deepmind_blog(content_html)
                            elif blog == "ai.meta.com": results = parse_meta_ai_blog(content_html)
                            elif blog == "amazon.science": results = parse_amazon_science_blog(content_html)
                            await self._enrich_article_content(results, context)
                            break
                    if not results:
                        results = [{"title": await page.title(), "link": source_url, "summary": self.converter.handle(content_html)[:2000], "source_type": "Web (Generic)"}]
                return results
            finally: await browser.close()
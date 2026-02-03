import json
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup

def parse_arxiv_list(html_content: str) -> List[Dict[str, Any]]:
    """Extracts papers from arXiv 'recent' list pages."""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # arXiv structure: <dt> contains link, <dd> contains title/authors
    dts = soup.find_all('dt')
    dds = soup.find_all('dd')
    
    for i in range(min(len(dts), len(dds))):
        try:
            # 1. Extract Link from <dt>
            # Look for the anchor that leads to the abstract
            a_tag = dts[i].find('a', title='Abstract')
            if not a_tag:
                continue
            
            link = "https://arxiv.org" + a_tag['href']
            
            # 2. Extract Title from <dd>
            title_div = dds[i].find('div', class_='list-title')
            title = "No Title"
            if title_div:
                # Remove the "Title: " prefix and extra whitespace
                title = title_div.get_text(strip=True).replace('Title:', '').strip()
            
            # 3. Extract Subjects/Authors as initial seed
            subjects = dds[i].find('div', class_='list-subjects')
            subject_text = subjects.get_text(strip=True) if subjects else ""
            
            authors_div = dds[i].find('div', class_='list-authors')
            authors_text = authors_div.get_text(strip=True) if authors_div else ""

            results.append({
                "title": title,
                "link": link,
                "summary": f"{authors_text}\n{subject_text}",
                "source_type": "arXiv Papers"
            })
        except Exception as e:
            print(f"Error parsing arXiv entry {i}: {e}")
            
    return results

def parse_arxiv_abstract(html_content: str) -> str:
    """Extracts the abstract text from a single arXiv paper page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try class 'abstract' or 'abstract mathjax' (bs4 finds by partial class match usually, but being explicit helps)
    abstract_block = soup.find('blockquote', class_=re.compile(r'abstract'))
    
    if abstract_block:
        # Remove the 'Abstract:' prefix if it exists
        text = abstract_block.get_text(strip=True)
        clean_text = text.replace('Abstract:', '').strip()
        # print(f"DEBUG: Parsed abstract: {clean_text[:50]}...")
        return clean_text
    
    # print("DEBUG: No abstract block found in HTML.")
    return ""

def parse_github_readme(html_content: str) -> str:
    """Extracts the README content from a GitHub repo page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    # GitHub READMEs are usually inside an article tag with class markdown-body
    readme_article = soup.find('article', class_='markdown-body')
    if readme_article:
        return readme_article.get_text(separator='\n', strip=True)
    
    # Fallback: sometimes it's in a div with id readme
    readme_div = soup.find('div', id='readme')
    if readme_div:
        return readme_div.get_text(separator='\n', strip=True)
        
    return ""

def parse_github_trending(html_content: str) -> List[Dict[str, Any]]:
    """Extracts repositories from GitHub Trending page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    articles = soup.find_all('article', class_='Box-row')
    for art in articles:
        try:
            h2 = art.find('h2')
            if not h2: continue
            
            a_tag = h2.find('a')
            repo_path = a_tag['href']
            link = "https://github.com" + repo_path
            title = repo_path.strip('/') # e.g. "user/repo"
            
            p_tag = art.find('p', class_='col-9')
            description = p_tag.get_text(strip=True) if h2 else ""
            
            # Stars & Language
            meta_div = art.find('div', class_='f6')
            stars = "0"
            if meta_div:
                star_a = meta_div.find('a', href=re.compile(r"stargazers"))
                if star_a:
                    stars = star_a.get_text(strip=True)

            results.append({
                "title": title,
                "link": link,
                "summary": description,
                "metadata": {"stars": stars},
                "source_type": "GitHub Trending"
            })
        except Exception as e:
            print(f"Error parsing GitHub Trending: {e}")
            
    return results

def parse_hf_model_card(html_content: str) -> str:
    """Extracts the model card text from a Hugging Face model page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # HF usually uses 'prose' or 'markdown-body' for its model cards
    content_div = soup.find('div', class_=re.compile(r'prose|markdown-body'))
    
    if content_div:
        return content_div.get_text(separator='\n', strip=True)
    
    # Fallback to looking for the main article or section
    article = soup.find('article')
    if article:
        return article.get_text(separator='\n', strip=True)
        
    return ""

def parse_reddit_list(html_content: str) -> List[Dict[str, Any]]:
    """Extracts posts from Reddit using highly robust attribute-based and tag-based extraction."""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    seen_links = set()
    
    # --- Method 1: shreddit-post Attributes ---
    # This is the gold mine for metadata.
    posts = soup.find_all('shreddit-post')
    
    # If no shreddit-posts found, try finding articles that CONTAIN shreddit-posts
    if not posts:
        articles = soup.find_all('article')
        for art in articles:
            p = art.find('shreddit-post')
            if p: posts.append(p)

    for post in posts:
        try:
            # 優先從標籤屬性拿
            title = post.get('post-title')
            permalink = post.get('permalink')
            
            if not title or not permalink:
                continue
                
            link = f"https://www.reddit.com{permalink}"
            if link in seen_links: continue
            
            score = post.get('score', '0')
            author = post.get('author', 'Unknown')
            comment_count = post.get('comment-count', '0')
            
            results.append({
                "title": title.strip(),
                "link": link,
                "upvotes": score,
                "metadata": {
                    "comments": comment_count,
                    "author": author,
                    "post_id": post.get('id')
                },
                "summary": f"Author: {author} | Comments: {comment_count}",
                "source_type": "Reddit Discussion"
            })
            seen_links.add(link)
        except: continue

    # --- Method 2: Pure Article tags (Fallback for simplified UI) ---
    if not results:
        articles = soup.find_all('article')
        for art in articles:
            # Find the first link that looks like a comments link
            a_tag = art.find('a', href=re.compile(r'/comments/'))
            title = art.get('aria-label') or (art.find('h3').get_text() if art.find('h3') else "")
            
            if a_tag and title:
                href = a_tag.get('href', '')
                link = f"https://www.reddit.com{href}" if href.startswith('/') else href
                if link in seen_links: continue
                
                results.append({
                    "title": title.strip(),
                    "link": link,
                    "upvotes": 50,
                    "metadata": {"author": "Unknown"},
                    "summary": f"Reddit Article: {title}",
                    "source_type": "Reddit (Article Fallback)"
                })
                seen_links.add(link)
            
    # --- Method 3: faceplate / Link tags (Ultimate Fallback) ---
    if not results:
        # ... (保持原有的 Method 2 邏輯)
        link_tags = soup.find_all('a', attrs={'slot': 'full-post-link'})
        for tag in link_tags:
            try:
                href = tag.get('href', '')
                if not href: continue
                link = f"https://www.reddit.com{href}" if href.startswith('/') else href
                if link in seen_links: continue
                
                title = ""
                reader = tag.find('faceplate-screen-reader-content')
                title = reader.get_text(strip=True) if reader else tag.get_text(strip=True)
                
                if not title: continue
                
                results.append({
                    "title": title,
                    "link": link,
                    "upvotes": 50,
                    "metadata": {"author": "Unknown"},
                    "summary": f"Reddit Post: {title}",
                    "source_type": "Reddit (Fallback)"
                })
                seen_links.add(link)
            except: continue
            
    return results

def parse_reddit_post_content(html_content: str) -> str:
    """Extracts the main OP text from a Reddit post page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Method 1: Look for <div slot="text-body"> inside <shreddit-post>
    content_div = soup.find('div', {'slot': 'text-body'})
    
    # Method 2: Look for user-generated-content div
    if not content_div:
        content_div = soup.find('div', class_=re.compile(r'user-generated-content'))
        
    # Method 3: Look for div with id ending in -post-rtjson-content (User provided structure)
    if not content_div:
        content_div = soup.find('div', id=re.compile(r'-post-rtjson-content$'))

    if content_div:
        # print(f"DEBUG: Found Reddit content div: {content_div.get_text()[:50]}...")
        return content_div.get_text(separator='\n', strip=True)
        
    # print("DEBUG: No Reddit content found.")
    return ""

def parse_huggingface_models(html_content: str) -> List[Dict[str, Any]]:
    """
    Extracts trending models from Hugging Face Models page.
    Uses data-props for accurate metadata (downloads, likes).
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # Try to find the hydration script or div with JSON data
    candidates = soup.find_all('div', {'data-props': True})
    
    for div in candidates:
        try:
            props = json.loads(div['data-props'])
            models = props.get('models')
            if models and isinstance(models, list):
                for m in models:
                    title = m.get('id', 'Unknown')
                    if not title: continue
                    
                    link = f"https://huggingface.co/{title}"
                    likes = m.get('likes', 0)
                    downloads = m.get('downloads', 0)
                    author = m.get('author', 'Unknown')
                    task = m.get('pipeline_tag', 'Unknown Task')
                    
                    summary = f"Task: {task}\nDownloads: {downloads}\nLikes: {likes}"

                    results.append({
                        "title": title,
                        "link": link,
                        "upvotes": likes, # Map likes to upvotes for scoring
                        "metadata": {
                            "downloads": downloads,
                            "task": task,
                            "author": author,
                            "stars": str(likes) # Map likes to stars for unified scoring
                        },
                        "summary": summary,
                        "source_type": "Hugging Face Models"
                    })
                if results:
                    break
        except:
            continue
            
    # Fallback: Manual HTML parsing if JSON fails
    if not results:
        # Based on user provided HTML, models are in <article class="overview-card-wrapper ...">
        articles = soup.find_all('article', class_=re.compile(r'overview-card-wrapper'))
        
        for art in articles:
            try:
                # Title and Link are in the first <a> tag
                a_tag = art.find('a', href=True)
                if not a_tag: continue
                
                link = f"https://huggingface.co{a_tag['href']}"
                
                # Title is in <header> -> <h4>
                header = art.find('header')
                title_tag = header.find('h4') if header else None
                title = title_tag.get_text(strip=True) if title_tag else a_tag['href'].strip('/')
                
                # Try to extract stats if possible, otherwise 0
                # We can try to parse the SVG icons context if needed later
                
                results.append({
                    "title": title,
                    "link": link,
                    "upvotes": 0, 
                    "metadata": {
                        "downloads": 0,
                        "task": "Unknown",
                    },
                    "summary": f"Model: {title}",
                    "source_type": "Hugging Face Models (Manual)"
                })
            except Exception as e:
                print(f"DEBUG: Error parsing HF model card: {e}")
                pass

    return results

def parse_huggingface_papers(html_content: str) -> List[Dict[str, Any]]:
    """
    Extracts structured paper data from Hugging Face Daily Papers HTML.
    Utilizes the JSON embedded in data-props for accuracy.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # Hugging Face often embeds the state in a SVELTE_HYDRATER div
    hydrater = soup.find('div', {'data-target': 'DailyPapers'})
    if hydrater and hydrater.has_attr('data-props'):
        try:
            props = json.loads(hydrater['data-props'])
            daily_papers = props.get('dailyPapers', [])
            
            for entry in daily_papers:
                paper = entry.get('paper', {})
                submitted_by = entry.get('submittedBy', {})
                
                # Extract requested fields
                item = {
                    "title": paper.get('title', 'No Title'),
                    "link": f"https://huggingface.co/papers/{paper.get('id', '')}",
                    "upvotes": paper.get('upvotes', 0),
                    "author": submitted_by.get('fullname') or submitted_by.get('name', 'Unknown'),
                    "github_stars": paper.get('githubStars'),
                    "summary": paper.get('summary', ''),
                    "published": paper.get('publishedAt', 'Unknown'),
                    "source_type": "Hugging Face Papers (Structured)"
                }
                results.append(item)
            
            return results
        except Exception as e:
            print(f"ERROR parsing HF data-props: {e}")

    # Fallback to manual parsing if JSON extraction fails
    articles = soup.find_all('article')
    for art in articles:
        try:
            title_tag = art.find('h3')
            if not title_tag: continue
            
            a_tag = title_tag.find('a')
            title = a_tag.get_text(strip=True)
            link = "https://huggingface.co" + a_tag['href']
            
            # Upvotes
            upvote_div = art.find('div', class_='leading-none')
            upvotes = upvote_div.get_text(strip=True) if upvote_div else "0"
            
            # Author - Look for "Submitted by" text
            author = "Unknown"
            sub_div = art.find(lambda tag: tag.name == "div" and "Submitted by" in tag.text)
            if sub_div:
                author = sub_div.get_text(strip=True).replace("Submitted by", "").strip()
            
            # Github Stars
            github_stars = None
            github_link = art.find('a', href=re.compile(r"github\.com")) # This might be the paper link if it redirects or has svg
            # Re-checking the HTML dump, github stars is in an 'a' tag with an SVG
            github_star_tag = art.find('a', href=re.compile(r"/papers/"))
            if github_star_tag and github_star_tag.find('svg'):
                github_stars = github_star_tag.get_text(strip=True)

            results.append({
                "title": title,
                "link": link,
                "upvotes": upvotes,
                "author": author,
                "github_stars": github_stars,
                "summary": "", # Manual parsing is hard for summary without JSON
                "source_type": "Hugging Face Papers (Manual Fallback)"
            })
        except Exception as e:
            print(f"ERROR in HF manual fallback: {e}")
            
    return results

def parse_anthropic_blog(html_content: str) -> List[Dict[str, Any]]:
    """Extracts articles from Anthropic News/Research page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # 1. Featured Articles (Grid)
    # Look for links containing /news/ or /research/
    # The structure seems to be <a> wrapping the whole card
    
    # Broad strategy: Find all anchors that link to internal news/research
    # Avoid duplicates
    seen_links = set()
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('/news/') or href.startswith('/research/'):
            full_link = f"https://www.anthropic.com{href}"
            if full_link in seen_links:
                continue
            
            # Try to extract title
            title = ""
            # Check for specific headings or spans used in their design
            for tag in ['h2', 'h3', 'h4', 'span']:
                title_elem = a.find(tag, class_=re.compile(r'title|headline', re.I))
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title:
                # Fallback: Just get all text in anchor if it's reasonable length
                text = a.get_text(strip=True)
                if 5 < len(text) < 200:
                    title = text
            
            if not title or title.lower() == "read more" or title.lower() == "see more":
                continue

            # Try to extract summary/date
            summary = ""
            date_time = a.find('time')
            if date_time:
                summary += f"Date: {date_time.get_text(strip=True)}\n"
            
            desc_elem = a.find('p', class_=re.compile(r'summary|body', re.I))
            if desc_elem:
                summary += desc_elem.get_text(strip=True)

            seen_links.add(full_link)
            results.append({
                "title": title,
                "link": full_link,
                "summary": summary.strip(),
                "source_type": "Anthropic Blog"
            })
            
    return results

def parse_openai_blog(html_content: str) -> List[Dict[str, Any]]:
    """Extracts articles from OpenAI News/Blog page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # OpenAI usually uses a list of <li> or <div> items.
    # We look for links pointing to /index/ or /news/ or /research/
    # 2026 check: links might look like /news/xyz or /index/xyz
    
    seen_links = set()
    
    # Generic container search
    # Often in a container with class 'cols-container' or similar
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        # OpenAI links are often relative
        if href.startswith('/') and ('news' in href or 'index' in href or 'research' in href):
            if href in ['/news', '/news/', '/index', '/index/']: continue # Skip self
            
            full_link = f"https://openai.com{href}"
            if full_link in seen_links: continue
            
            title = ""
            # Look for explicit title tags inside
            h_tag = a.find(['h3', 'h4', 'h5'])
            if h_tag:
                title = h_tag.get_text(strip=True)
            else:
                # If the link text is substantial, use it
                text = a.get_text(strip=True)
                if 10 < len(text) < 150:
                    title = text
            
            if not title: continue
            
            # Find date
            date_span = a.find('span', text=re.compile(r'\d{4}')) # Simple heuristic for year
            summary = ""
            if date_span:
                summary = f"Date: {date_span.get_text(strip=True)}"

            seen_links.add(full_link)
            results.append({
                "title": title,
                "link": full_link,
                "summary": summary,
                "source_type": "OpenAI Blog"
            })
            
    return results

def parse_deepmind_blog(html_content: str) -> List[Dict[str, Any]]:
    """Extracts articles from Google DeepMind Blog (List or Single)."""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # --- Case 1: Single Article View ---
    # Check for the cover section unique to single posts
    cover_section = soup.find('section', class_=re.compile(r'section-cover--blog'))
    if cover_section:
        try:
            # 1. Title
            title_tag = cover_section.find('h1', class_=re.compile(r'cover__text--title'))
            title = title_tag.get_text(strip=True) if title_tag else "No Title"
            
            # 2. Metadata (Date, Category, Authors)
            summary_parts = []
            
            # Date
            date_span = cover_section.find('span', class_='cover__text--date')
            if date_span:
                summary_parts.append(f"Date: {date_span.get_text(strip=True)}")
                
            # Category
            cat_span = cover_section.find('span', class_='cover__text--category')
            if cat_span:
                summary_parts.append(f"Category: {cat_span.get_text(strip=True)}")
                
            # Authors
            authors_p = cover_section.find('p', class_='cover__text--authors')
            if authors_p:
                summary_parts.append(f"Authors: {authors_p.get_text(strip=True)}")
            
            # 3. Main Content
            # Usually follows the cover. We'll look for standard content containers.
            # DeepMind often uses 'grid__column--span-8-md' for text blocks.
            content_text = ""
            # Find all text paragraphs in the main content area
            # We skip the cover section itself
            for p in soup.find_all('p'):
                # Simple heuristic: if parent is not in cover section
                if not p.find_parent(class_=re.compile(r'section-cover')):
                    text = p.get_text(strip=True)
                    if len(text) > 50: # Filter small UI text
                        content_text += text + "\n\n"
            
            # Combine metadata and preview of content
            summary = " | ".join(summary_parts) + "\n\n" + content_text[:3000]
            
            # Link is the current page (we don't have URL here, but downstream sets it)
            # We return empty link and let strategy fill it if possible, 
            # or we rely on the fact this parser is called with a specific URL context.
            # Ideally the parser should just return extracted data.
            
            results.append({
                "title": title,
                "link": "", # Placeholder, will be filled by caller if needed
                "summary": summary,
                "source_type": "Google DeepMind Blog (Single)"
            })
            return results
            
        except Exception as e:
            print(f"Error parsing DeepMind single article: {e}")

    # --- Case 2: List View (Fallback) ---
    # DeepMind uses <article class="card card-blog ..."> for posts
    articles = soup.find_all('article', class_=re.compile(r'card-blog'))
    
    for art in articles:
        try:
            # 1. Title (h3 with class card__title)
            title_tag = art.find('h3', class_=re.compile(r'card__title'))
            title = title_tag.get_text(strip=True) if title_tag else "No Title"
            
            # 2. Link
            # Look for the "Learn more" button link inside the article
            # It usually has class "button--tonal" or "button--text_link"
            a_tag = art.find('a', href=True)
            # Better specific targeting: look for the one with "Learn more" or just the first valid internal link
            if not a_tag:
                continue
                
            href = a_tag['href']
            # Resolve relative links
            if href.startswith('/'):
                link = f"https://deepmind.google{href}"
            else:
                link = href
                
            # 3. Metadata
            summary_parts = []
            
            # Date
            time_tag = art.find('time')
            if time_tag:
                summary_parts.append(f"Date: {time_tag.get_text(strip=True)}")
                
            # Category
            cat_span = art.find('span', class_='meta__category')
            if cat_span:
                summary_parts.append(f"Category: {cat_span.get_text(strip=True)}")
                
            summary = " | ".join(summary_parts)
            
            results.append({
                "title": title,
                "link": link,
                "summary": summary,
                "source_type": "Google DeepMind Blog"
            })
            
        except Exception as e:
            print(f"Error parsing DeepMind article: {e}")
            
    return results
            
def parse_meta_ai_blog(html_content: str) -> List[Dict[str, Any]]:
    """Extracts articles from Meta AI Blog."""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    seen_links = set()
    
    # Meta AI usually uses /blog/article-slug
    for a in soup.find_all('a', href=True):
        href = a['href']
        
        if '/blog/' in href and href != '/blog/':
            if href.startswith('/'):
                full_link = f"https://ai.meta.com{href}"
            else:
                full_link = href
                
            if full_link in seen_links: continue
            
            title = ""
            h_tag = a.find(['h3', 'h4'])
            if h_tag:
                title = h_tag.get_text(strip=True)
            else:
                text = a.get_text(strip=True)
                if 15 < len(text) < 150:
                    title = text
            
            if not title: continue
            
            seen_links.add(full_link)
            results.append({
                "title": title,
                "link": full_link,
                "summary": "", # Often meta info is separate or hard to parse generically
                "source_type": "Meta AI Blog"
            })
            
    return results

def parse_amazon_science_blog(html_content: str) -> List[Dict[str, Any]]:
    """Extracts articles from Amazon Science Blog (List or Single)."""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # --- Case 1: List View ---
    # Look for the promo cards
    promos = soup.find_all('div', class_='PromoF', attrs={'data-content-type': 'blog post'})
    
    if promos:
        seen_links = set()
        for promo in promos:
            try:
                # Title & Link
                title_div = promo.find('div', class_='PromoF-title')
                if not title_div: continue
                
                a_tag = title_div.find('a', class_='Link')
                if not a_tag: continue
                
                href = a_tag['href']
                title = a_tag.get_text(strip=True)
                
                if href.startswith('/'):
                    link = f"https://www.amazon.science{href}"
                else:
                    link = href
                    
                if link in seen_links: continue
                
                # Metadata
                summary_parts = []
                
                # Authors
                authors_div = promo.find('div', class_='PromoF-authors')
                if authors_div:
                    authors = authors_div.get_text(strip=True)
                    summary_parts.append(f"Authors: {authors}")
                    
                # Date
                date_div = promo.find('div', class_='PromoF-date')
                if date_div:
                    summary_parts.append(f"Date: {date_div.get_text(strip=True)}")
                    
                # Description
                desc_div = promo.find('div', class_='PromoF-description')
                if desc_div:
                    summary_parts.append(f"Description: {desc_div.get_text(strip=True)}")
                    
                summary = " | ".join(summary_parts)
                
                seen_links.add(link)
                results.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "source_type": "Amazon Science Blog"
                })
            except Exception as e:
                print(f"Error parsing Amazon Science promo: {e}")
        
        # If we found items in list view, return them
        if results:
            return results

    # --- Case 2: Single Article View (Fallback if no promos found) ---
    # Try to find article body content
    # Amazon Science articles usually have a main content area. 
    # We can try to find the title header and then the body.
    
    try:
        # Title - often in ArticlePage-title or similar, or just h1
        title_tag = soup.find('h1', class_=re.compile(r'ArticlePage-title|Headline'))
        if not title_tag:
            title_tag = soup.find('h1') # Fallback
            
        title = title_tag.get_text(strip=True) if title_tag else "No Title"
        
        # Content - Look for ArticlePage-articleBody or just collect paragraphs
        article_body = soup.find('div', class_=re.compile(r'ArticlePage-articleBody'))
        content_text = ""
        
        if article_body:
            # Extract text from specific container
            for p in article_body.find_all(['p', 'h2', 'h3']):
                content_text += p.get_text(strip=True) + "\n\n"
        else:
            # Fallback: Extract all paragraphs that look like content (long enough)
            # Avoid footer/header links
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if len(text) > 60:
                    content_text += text + "\n\n"
        
        if content_text:
            results.append({
                "title": title,
                "link": "", # Placeholder
                "summary": content_text[:3000], # Capture more for single page
                "source_type": "Amazon Science Blog (Single)"
            })
            
    except Exception as e:
        print(f"Error parsing Amazon Science single article: {e}")

    return results
            
def parse_hacker_news_list(html_content: str) -> List[Dict[str, Any]]:
    """Extracts stories from Hacker News front page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    # HN uses a table layout. Rows are grouped in 3s: Title row, Metadata row, Spacer row.
    # Title row has class 'athing'
    items = soup.find_all('tr', class_='athing')
    
    for item in items:
        try:
            # 1. Title & Link
            title_line = item.find('span', class_='titleline')
            if not title_line: continue
            
            a_tag = title_line.find('a')
            if not a_tag: continue
            
            title = a_tag.get_text(strip=True)
            link = a_tag['href']
            
            # Handle internal HN links (Ask HN, etc.) which might be relative
            if link.startswith('item?id='):
                link = f"https://news.ycombinator.com/{link}"
                
            # 2. Metadata (next sibling row)
            meta_row = item.find_next_sibling('tr')
            points = "0"
            author = "Unknown"
            comments = "0"
            
            if meta_row:
                subtext = meta_row.find('td', class_='subtext')
                if subtext:
                    # Points
                    score_span = subtext.find('span', class_='score')
                    if score_span:
                        points = score_span.get_text(strip=True).replace(' points', '')
                    
                    # Author
                    user_a = subtext.find('a', class_='hnuser')
                    if user_a:
                        author = user_a.get_text(strip=True)
                        
                    # Comments - usually the last anchor
                    # "10 comments", "discuss", "hide"
                    links = subtext.find_all('a')
                    for l in links:
                        txt = l.get_text(strip=True)
                        if 'comment' in txt:
                            comments = txt.replace('\xa0comments', '').replace(' comments', '')
                        elif txt == 'discuss':
                            comments = "0"
                            
            results.append({
                "title": title,
                "link": link,
                "upvotes": points, # Normalized field
                "metadata": {
                    "comments": comments,
                    "author": author,
                    "points": points
                },
                "summary": f"Points: {points} | Comments: {comments} | Author: {author}",
                "source_type": "Hacker News"
            })
            
        except Exception as e:
            print(f"Error parsing HN item: {e}")
            
    return results

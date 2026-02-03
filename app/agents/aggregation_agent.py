import numpy as np
from typing import List, Dict, Any
from sklearn.cluster import AgglomerativeClustering
from app.core.interfaces import EmbeddingProvider, LLMProvider

class AggregationAgent:
    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embedding_provider = embedding_provider

    async def purify_articles(self, articles: List[Dict[str, Any]], llm: LLMProvider, progress_callback=None) -> List[Dict[str, Any]]:
        """
        Noise Reduction: Uses LLM to score articles and filter out low-value content.
        NEW: The score (1-10) is now a comprehensive 'Value Score' considering Tech Depth, Hype, and Novelty.
        """
        if not articles: return []
        
        print(f"DEBUG: Purifying {len(articles)} articles with Deep Scoring...")
        purified = []
        total = len(articles)
        
        # Batch processing
        batch_size = 5
        score_distribution = {i: [] for i in range(1, 11)}
        
        for i in range(0, total, batch_size):
            batch = articles[i:i+batch_size]
            
            # Check if this batch is already fully processed (Resume capability)
            # If all articles in this batch have a valid quality_score, skip LLM call
            if all(a.get('quality_score') is not None for a in batch):
                # Re-populate the score_distribution for UI consistency
                for a in batch:
                    sc = a.get('quality_score', 0)
                    if 1 <= sc <= 10:
                        score_distribution[sc].append({
                            "title": a.get('title', 'No Title'),
                            "link": a.get('link', 'No Link')
                        })
                    if sc >= 6:
                        purified.append(a)
                
                # Update progress even for skipped batches
                if progress_callback:
                    try:
                        progress_callback(min(i + batch_size, total), total, score_distribution)
                    except TypeError:
                        progress_callback(min(i + batch_size, total), total)
                
                print(f"DEBUG: Skipping batch {i} (Already processed)")
                continue

            # Prepare rich context for the LLM
            batch_items = []
            for j, a in enumerate(batch):
                # Extract metadata safely
                meta = a.get('metadata', {}) or {}
                upvotes = a.get('upvotes', meta.get('upvotes', 'N/A'))
                stars = meta.get('stars', 'N/A')
                source = a.get('source_type', 'Unknown')
                
                batch_items.append(
                    f"ID {j}:\n"
                    f"Title: {a['title']}\n"
                    f"Source: {source} | Upvotes: {upvotes} | Stars: {stars}\n"
                    f"Summary: {a.get('summary', '')[:300]}..."
                )
            
            batch_str = "\n---\n".join(batch_items)
            
            if progress_callback:
                try:
                    progress_callback(i, total, score_distribution)
                except TypeError:
                    progress_callback(i, total)

            prompt = f"""
            You are a Senior Tech Trend Analyst. Evaluate the following articles for a developer-focused newsletter. 
            
            **Scoring Criteria (1-10 Scale):**
            Calculate a holistic score based on these factors:
            1. **Technical Depth:** Is it a breakthrough? Does it share code/architecture? (High weight)
            2. **Social Hype:** Check 'Upvotes' and 'Stars'. High numbers = High community interest. (Medium weight)
            3. **Novelty/Fun:** Is it cool? New? Or just corporate PR? (Medium weight)

            **Score Guide:**
            - **1-4:** Corporate PR, repetitive news, low-effort content, zero technical details.
            - **5-6:** Decent news, but not groundbreaking. Standard updates.
            - **7-8:** Strong technical content, good community discussion, or very useful tools.
            - **9-10:** MUST READ. Major industry shifts (e.g., GPT-4 release), viral open-source repos (10k+ stars), or deep architectural analysis.

            **Articles to Rate:**
            {batch_str}

            **Output ONLY a JSON array:**
            [ {{"id": 0, "score": 8}}, {{"id": 1, "score": 3}}, ... ]
            """
            try:
                response = await llm.generate(prompt=prompt, system_prompt="You are a Technical Quality Inspector.")
                import re
                import json
                
                # Try to find JSON list structure
                match = re.search(r'\[.*\]', response, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    try:
                        scores = json.loads(json_str)
                    except json.JSONDecodeError:
                        # Fallback: simple fix for single quotes which LLMs often use
                        try:
                            import ast
                            scores = ast.literal_eval(json_str)
                        except:
                            print(f"DEBUG: Failed to parse JSON even with ast.literal_eval. Content: {json_str[:100]}...")
                            scores = []

                    for s in scores:
                        idx = s.get('id')
                        score = s.get('score', 0)
                        
                        # Track distribution
                        if 1 <= score <= 10 and idx is not None and idx < len(batch):
                            art = batch[idx]
                            score_distribution[score].append({
                                "title": art.get('title', 'No Title'),
                                "link": art.get('link', 'No Link')
                            })
                        
                        if idx is not None and idx < len(batch):
                            # Always save the score if valid, even if low (for debugging or optional lower thresholds later)
                            batch[idx]['quality_score'] = score
                            
                            # Filter threshold: Keep 6+
                            if score >= 6:
                                purified.append(batch[idx])
                            
                    dist_summary = {k: len(v) for k, v in score_distribution.items() if v}
                    print(f"DEBUG: Current Score Distribution (Counts): {dist_summary}")

            except Exception as e:
                print(f"Purify error in batch {i}: {e}")
                # On error, maybe keep them but mark score as 0? Or just skip. 
                # Let's keep them to avoid data loss during API glitches, but give score 5.
                for item in batch:
                    item['quality_score'] = 5
                    purified.append(item)
        
        if progress_callback:
            try:
                progress_callback(total, total, score_distribution)
            except TypeError:
                progress_callback(total, total)
            
        print(f"DEBUG: Purification complete. {len(purified)}/{len(articles)} passed.")
        return purified

    async def generate_intent_tags(self, articles: List[Dict[str, Any]], llm: LLMProvider, progress_callback=None) -> List[Dict[str, Any]]:
        """
        Preprocessing: Generates 'Intent Tags' for each article to improve semantic clustering.
        Example: "DeepSeek R1" + "Local Inference" -> These tags help bridge the gap between Reddit and Arxiv.
        """
        if not articles: return []
        
        print(f"DEBUG: Generating Intent Tags for {len(articles)} articles...")
        batch_size = 10
        total = len(articles)
        
        for i in range(0, total, batch_size):
            batch = articles[i:i+batch_size]
            
            # Skip if already tagged
            if all('intent_tags' in a for a in batch): continue

            batch_text = ""
            for j, a in enumerate(batch):
                batch_text += f"ID {j}: {a['title']} (Source: {a.get('source_type', 'unknown')})\nSummary: {a.get('summary', '')[:200]}\n\n"
            
            prompt = f"""
            Task: Assign 3-5 standardized technical tags to each article.
            Goal: Unify diverse sources (Reddit vs Arxiv). e.g., both "DeepSeek-V3 paper" and "How to run DeepSeek locally" should get the tag "DeepSeek".

            Articles:
            {batch_text}

            Output STRICT JSON Array:
            [
                {{"id": 0, "tags": ["DeepSeek", "Quantization", "Local LLM"]}},
                {{"id": 1, "tags": ["React", "Frontend", "Performance"]}}
            ]
            """
            
            try:
                response = await llm.generate(prompt=prompt, system_prompt="You are a Tech Taxonomist.")
                import json
                import re
                
                json_str = ""
                match = re.search(r'\[.*\]', response, re.DOTALL)
                if match: json_str = match.group(0)
                else: json_str = response
                
                try:
                    tags_data = json.loads(json_str)
                    for item in tags_data:
                        idx = item.get('id')
                        tags = item.get('tags', [])
                        if idx is not None and 0 <= idx < len(batch):
                            batch[idx]['intent_tags'] = ", ".join(tags)
                except:
                    print(f"DEBUG: Tag parsing failed for batch {i}. Content: {response[:50]}...")
            
            except Exception as e:
                print(f"DEBUG: Tag generation error: {e}")
            
            if progress_callback:
                progress_callback(min(i + batch_size, total), total, "Tagging...")
                
        return articles

    async def refine_clusters_with_llm(self, initial_clusters: List[Dict[str, Any]], llm: LLMProvider) -> List[Dict[str, Any]]:
        """
        Post-processing: Asks LLM to merge clusters that are semantically identical but separated by vector distance.
        """
        if len(initial_clusters) < 2: return initial_clusters
        
        # Prepare cluster summaries for LLM
        cluster_summaries = []
        for c in initial_clusters:
            # Get top 3 tags if available, else titles
            titles = [a['title'] for a in c['articles'][:3]]
            tag_counts = {}
            for a in c['articles']:
                for t in a.get('intent_tags', '').split(', '):
                    if t: tag_counts[t] = tag_counts.get(t, 0) + 1
            top_tags = sorted(tag_counts, key=tag_counts.get, reverse=True)[:3]
            
            summary = f"Cluster {c['cluster_id']} (Tags: {', '.join(top_tags)}):\n- " + "\n- ".join(titles)
            cluster_summaries.append(summary)
            
        context = "\n\n".join(cluster_summaries[:30]) # Limit to top 30 clusters to save tokens
        
        prompt = f"""
        You are a Chief Editor organizing a newsletter. 
        Review these article clusters. Some split the same topic into two groups (e.g. "DeepSeek Paper" vs "DeepSeek Reddit Discussion").
        Identify clusters that SHOULD BE MERGED because they cover the same core topic from different angles.

        Clusters:
        {context}

        Output STRICT JSON of merge pairs:
        {{
            "merges": [
                [1, 5],  // Merge Cluster 5 into Cluster 1
                [2, 8]   // Merge Cluster 8 into Cluster 2
            ]
        }}
        If no merges needed, return strict empty list: {{ "merges": [] }}
        """
        
        try:
            response = await llm.generate(prompt=prompt, system_prompt="You are an Editor.")
            import json
            import re
            
            json_str = "{}"
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match: json_str = match.group(0)
            
            data = json.loads(json_str)
            merges = data.get('merges', [])
            
            if not merges: return initial_clusters
            
            # Execute Merges
            # Convert list to dict for easy access
            cluster_map = {c['cluster_id']: c for c in initial_clusters}
            
            for target_id, source_id in merges:
                if target_id in cluster_map and source_id in cluster_map and target_id != source_id:
                    target = cluster_map[target_id]
                    source = cluster_map[source_id]
                    
                    print(f"DEBUG: Merging Cluster {source_id} into {target_id}...")
                    
                    # Merge articles
                    target['articles'].extend(source['articles'])
                    target['size'] += source['size']
                    # Recalculate score
                    s, a, d = self._calculate_cluster_score(target['articles'])
                    target['score'] = s
                    target['academic_score'] = a
                    target['score_details'] = d
                    
                    # Remove source
                    del cluster_map[source_id]
            
            # Re-sort
            final_list = list(cluster_map.values())
            final_list.sort(key=lambda x: x['score'], reverse=True)
            return final_list

        except Exception as e:
            print(f"DEBUG: Refinement failed: {e}")
            return initial_clusters

    async def cluster_articles(self, articles: List[Dict[str, Any]], distance_threshold: float = 0.4) -> List[Dict[str, Any]]:
        """
        Clusters articles using Agglomerative Clustering. Pure physical grouping.
        Uses _prepare_text_for_embedding to check for Intent Tags.
        """
        if not articles: return []

        # 1. Prepare texts (Content + Tags checked internally)
        texts = [self._prepare_text_for_embedding(a) for a in articles]
        
        # 2. Get vectors
        vectors = await self.embedding_provider.embed_documents(texts)
        X = np.array(vectors)
        
        # Normalize vectors
        from sklearn.preprocessing import normalize
        X_norm = normalize(X)

        # 3. Perform Clustering
        clustering = AgglomerativeClustering(
            n_clusters=None, 
            metric='euclidean', 
            linkage='ward',
            distance_threshold=distance_threshold
        ).fit(X_norm)
        
        labels = clustering.labels_

        # 4. Group articles by labels
        clusters_map = {}
        for idx, label in enumerate(labels):
            label_id = int(label)
            if label_id not in clusters_map:
                clusters_map[label_id] = []
            clusters_map[label_id].append(articles[idx])

        # 5. Process Clusters into preliminary format
        final_clusters = []
        for label_id, member_articles in clusters_map.items():
            # Find representative article
            def get_sort_key(a):
                q = a.get('quality_score', 0)
                try:
                    uv = a.get('upvotes', 0)
                    uv_val = int(''.join(filter(str.isdigit, str(uv))) or 0)
                except: uv_val = 0
                return (q, uv_val)
            
            best_article = max(member_articles, key=get_sort_key)
            score, academic_score, details = self._calculate_cluster_score(member_articles)
            
            final_clusters.append({
                "cluster_id": label_id,
                "representative_title": best_article['title'],
                "articles": member_articles,
                "score": score,
                "academic_score": academic_score,
                "score_details": details,
                "size": len(member_articles)
            })

        final_clusters.sort(key=lambda x: x['score'], reverse=True)
        return final_clusters

    def _calculate_cluster_score(self, articles: List[Dict[str, Any]]) -> tuple[float, float, Dict[str, Any]]:
        """
        Calculates cluster score using the aggregated LLM 'Quality Scores'.
        Replaces the old heuristic math.
        """
        if not articles:
            return 0.0, 0.0, {}

        scores = [a.get('quality_score', 0) for a in articles]
        
        # If articles haven't been purified (score=0), we might need a fallback.
        # But assuming the pipeline runs Purify -> Cluster, we rely on these scores.
        # Filter out 0s for average calculation unless all are 0
        valid_scores = [s for s in scores if s > 0]
        if not valid_scores: valid_scores = [5] # Default fallback

        avg_score = sum(valid_scores) / len(valid_scores)
        max_score = max(valid_scores)
        
        # Size Bonus: Log2(Size). 1 art = 0 bonus. 2 arts = 1. 4 arts = 2.
        import math
        size_bonus = math.log2(len(articles)) * 0.5
        
        # Final Score Formula:
        # Heavily weight the BEST article (it defines the cluster's peak value)
        # Also consider the average (consistency) and size (importance).
        # Weighted: 30% Avg + 70% Max + SizeBonus
        final_total = (avg_score * 0.3) + (max_score * 0.7) + size_bonus
        
        # Academic/Paper Score logic (kept simple or based on Source)
        # We can just reuse the total score or filter for 'arxiv' presence if needed.
        # For now, let's make academic score synonymous with total score unless we specifically parse for 'arxiv'.
        is_academic = any('arxiv' in a.get('source_type', '').lower() for a in articles)
        final_academic = final_total + (2.0 if is_academic else 0.0)

        details = {
            "avg_llm_score": round(avg_score, 2),
            "max_llm_score": max_score,
            "size_bonus": round(size_bonus, 2),
            "is_academic_boost": is_academic,
            "raw_scores": scores
        }
        
        return round(final_total, 2), round(final_academic, 2), details

    def _prepare_text_for_embedding(self, article: Dict[str, Any]) -> str:
        """Helper to construct the text for embedding, prioritizing Intent Tags."""
        tags = article.get('intent_tags', '')
        content = article.get('content') or article.get('summary', '')
        # Tags at the start to heavily influence the vector
        if tags:
            return f"Tags: {tags}\nTitle: {article['title']}\n{content[:5000]}"
        else:
            return f"{article['title']}\n{content[:5000]}"

    async def optimize_threshold(self, articles: List[Dict[str, Any]], llm: LLMProvider) -> tuple[float, str]:
        """
        Scans thresholds and uses LLM to pick the best one with a focus on Topic Cohesion.
        Range: 0.5 - 0.8 with 0.02 step for high-precision clustering.
        """
        import numpy as np
        
        # 精細掃描：0.5 到 0.8，每 0.02 一格 (約 15 個點)
        thresholds = np.arange(0.5, 0.81, 0.02)
        sweep_results = []
        
        # FIXED: Use the unified text preparation (with tags if available)
        texts = [self._prepare_text_for_embedding(a) for a in articles]
        vectors = await self.embedding_provider.embed_documents(texts)
        from sklearn.preprocessing import normalize
        X_norm = normalize(np.array(vectors))
        
        for t in thresholds:
            t_val = round(float(t), 2)
            clustering = AgglomerativeClustering(n_clusters=None, metric='euclidean', linkage='ward', distance_threshold=t_val).fit(X_norm)
            
            clusters_map = {}
            for idx, label in enumerate(clustering.labels_):
                lid = int(label)
                if lid not in clusters_map: clusters_map[lid] = []
                clusters_map[lid].append(idx)
            
            # 統計數據
            num_clusters = len(clusters_map)
            singletons = sum(1 for c in clusters_map.values() if len(c) == 1)
            max_size = max(len(c) for c in clusters_map.values())

            # 挑選前 4 個代表性 Cluster (精簡輸出)
            top_clusters = sorted(clusters_map.items(), key=lambda x: len(x[1]), reverse=True)[:4]
            
            summary_str = f"T={t_val}: Clusters={num_clusters}, Singletons={singletons}, MaxSize={max_size}\n"
            for i, (lid, indices) in enumerate(top_clusters):
                titles = [articles[aidx]['title'][:80] for aidx in indices[:3]] # 限制標題長度
                summary_str += f"  G{i+1}({len(indices)}): {', '.join(titles)}\n"
            
            sweep_results.append(summary_str)
        

        system_prompt = (
            "You are a strict Data Science Assistant. You MUST respond ONLY with a valid JSON block. "
            "No conversational filler. No thinking process in the output. "
            "Your sole task is to analyze clustering statistics and select the best 'distance_threshold' (a number)."
        )

        user_prompt = f"""
### Task: Select Optimal Clustering Threshold
We are grouping {len(articles)} tech articles. Analyze the scan data below and pick the best threshold.

### Scan Data:
{chr(10).join(sweep_results)}

### Selection Criteria:
1. **Naming Test:** At a GOOD threshold, Group 1 can be named specifically (e.g., 'LLM Optimization'). At a BAD threshold, Group 1 is 'Word Salad' (mixing unrelated tech).
2. **Fragmentation:** If Singletons > 50%, the threshold is TOO LOW (Too many single-article groups).
3. **Mega-Clusters:** If any group contains > 25% of total articles, the threshold is TOO HIGH.

### Requirement:
Pick the threshold that balances these factors. If 1.0 looks like word salad, try 0.75 or 0.5.

### Output Format:
```json
{{
    "best_threshold": X.XX,
    "reasoning": "One sentence explanation focusing on Group 1's purity vs singleton count."
}}
```
"""
        response = await llm.generate(prompt=user_prompt, system_prompt=system_prompt)
        
        if not response or not response.strip():
            return 1.0, "模型未回傳內容。"

        try:
            import re
            import json
            
            # 1. 嘗試提取 JSON 區塊
            json_str = ""
            match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
            else:
                match = re.search(r'(\{.*\})', response, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
            
            # 2. 如果找到 JSON 結構，嘗試解析
            if json_str:
                try:
                    data = json.loads(json_str)
                    best_t = data.get('best_threshold')
                    if best_t: return float(best_t), data.get('reasoning', 'AI 選出的最優閾值。')
                except: pass

            # 3. 終極搶救：直接從整段文字中尋找第一個符合 0.5 - 2.5 範圍的浮點數
            # 搜尋格式如 1.0, 1.25, 1.5 等
            numbers = re.findall(r'(\d+\.\d+)', response)
            for n in numbers:
                val = float(n)
                if 0.4 <= val <= 2.6:
                    return val, f"自動從模型回應中提取數值 {val}。\n\n**原始回應 (Debug):**\n{response}"

            return 1.0, f"無法解析模型建議的閾值，使用預設值 1.0。\n\n**原始回應 (Debug):**\n{response}"
        except Exception as e:
            return 1.0, f"解析失敗: {e}"

    async def generate_intent_tags(self, articles: List[Dict[str, Any]], llm: LLMProvider, progress_callback=None) -> List[Dict[str, Any]]:
        """
        Preprocessing: Generates 'Intent Tags' for each article to improve semantic clustering.
        """
        if not articles: return []
        
        print(f"DEBUG: Generating Intent Tags for {len(articles)} articles...")
        batch_size = 10
        total = len(articles)
        
        for i in range(0, total, batch_size):
            batch = articles[i:i+batch_size]
            
            # Skip if already tagged
            if all('intent_tags' in a for a in batch): continue

            batch_text = ""
            for j, a in enumerate(batch):
                batch_text += f"ID {j}: {a['title']} (Source: {a.get('source_type', 'unknown')})\nSummary: {a.get('summary', '')[:200]}\n\n"
            
            prompt = f"""
            Task: Assign 3-5 standardized technical tags to each article.
            Goal: Unify diverse sources (Reddit vs Arxiv). e.g., both "DeepSeek-V3 paper" and "How to run DeepSeek locally" should get the tag "DeepSeek".

            Articles:
            {batch_text}

            Output STRICT JSON Array:
            [
                {{"id": 0, "tags": ["DeepSeek", "Quantization", "Local LLM"]}},
                {{"id": 1, "tags": ["React", "Frontend", "Performance"]}}
            ]
            """
            
            try:
                response = await llm.generate(prompt=prompt, system_prompt="You are a Tech Taxonomist.")
                import json
                import re
                
                json_str = ""
                match = re.search(r'\[.*\]', response, re.DOTALL)
                if match: json_str = match.group(0)
                else: json_str = response
                
                try:
                    tags_data = json.loads(json_str)
                    for item in tags_data:
                        idx = item.get('id')
                        tags = item.get('tags', [])
                        if idx is not None and 0 <= idx < len(batch):
                            batch[idx]['intent_tags'] = ", ".join(tags)
                except: pass
            except Exception as e:
                print(f"DEBUG: Tag generation error: {e}")
            
            if progress_callback:
                progress_callback(min(i + batch_size, total), total, "Tagging...")
                
        return articles

    async def refine_clusters_with_llm(self, initial_clusters: List[Dict[str, Any]], llm: LLMProvider) -> List[Dict[str, Any]]:
        """
        Post-processing: Asks LLM to merge clusters that are semantically identical.
        """
        if len(initial_clusters) < 2: return initial_clusters
        
        # Prepare cluster summaries for LLM
        cluster_summaries = []
        for c in initial_clusters:
            # Get top 3 tags if available, else titles
            titles = [a['title'] for a in c['articles'][:3]]
            tag_counts = {}
            for a in c['articles']:
                for t in a.get('intent_tags', '').split(', '):
                    if t: tag_counts[t] = tag_counts.get(t, 0) + 1
            top_tags = sorted(tag_counts, key=tag_counts.get, reverse=True)[:3]
            
            summary = f"Cluster {c['cluster_id']} (Tags: {', '.join(top_tags)}):\n- " + "\n- ".join(titles)
            cluster_summaries.append(summary)
            
        context = "\n\n".join(cluster_summaries[:30]) # Limit to top 30
        
        prompt = f"""
        You are a Chief Editor organizing a newsletter. 
        Review these article clusters.
        Identify clusters that SHOULD BE MERGED because they cover the same core topic.

        Clusters:
        {context}

        Output STRICT JSON of merge pairs:
        {{
            "merges": [
                [1, 5],  // Merge Cluster 5 into Cluster 1
                [2, 8]   // Merge Cluster 8 into Cluster 2
            ]
        }}
        If no merges needed, return strict empty list: {{ "merges": [] }}
        """
        
        try:
            response = await llm.generate(prompt=prompt, system_prompt="You are an Editor.")
            import json
            import re
            
            json_str = "{}"
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match: json_str = match.group(0)
            
            data = json.loads(json_str)
            merges = data.get('merges', [])
            
            if not merges: return initial_clusters
            
            # Execute Merges
            cluster_map = {c['cluster_id']: c for c in initial_clusters}
            for target_id, source_id in merges:
                if target_id in cluster_map and source_id in cluster_map and target_id != source_id:
                    target = cluster_map[target_id]
                    source = cluster_map[source_id]
                    target['articles'].extend(source['articles'])
                    target['size'] += source['size']
                    # Recalculate score
                    s, a, d = self._calculate_cluster_score(target['articles'])
                    target['score'] = s
                    target['academic_score'] = a
                    target['score_details'] = d
                    del cluster_map[source_id]
            
            final_list = list(cluster_map.values())
            final_list.sort(key=lambda x: x['score'], reverse=True)
            return final_list

        except Exception as e:
            print(f"DEBUG: Refinement failed: {e}")
            return initial_clusters
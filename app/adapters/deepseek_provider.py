import os
from typing import Optional, Any
from openai import AsyncOpenAI
from app.core.interfaces import LLMProvider

class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=base_url)
        self.last_usage = None # 新增：記錄最後一次 Token 消耗

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=kwargs.get("model", "deepseek-chat"),
            messages=messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048)
        )
        
        # 提取 Token 使用情況
        if hasattr(response, 'usage'):
            self.last_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
        content = response.choices[0].message.content
        # 移除思考過程
        import re
        content = re.sub(r'<(thought|reasoning)>.*?</\1>', '', content, flags=re.DOTALL).strip()
        
        return content

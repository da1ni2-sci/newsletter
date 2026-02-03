import os
from typing import Optional, Any
from openai import AsyncOpenAI
from app.core.interfaces import LLMProvider

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-5-mini-2025-08-07"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model_name = model_name
        self.last_usage = None # 記錄最後一次 Token 消耗

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model_to_use = kwargs.get("model", self.model_name)
        params = {
            "model": model_to_use,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
        }

        try:
            response = await self.client.chat.completions.create(**params)
        except Exception as e:
            # 針對不支援 temperature 的模型 (如 gpt-5-mini/o1 系列) 進行自動修正
            if "temperature" in str(e).lower():
                params.pop("temperature")
                response = await self.client.chat.completions.create(**params)
            else:
                raise e
        
        # 提取 Token 使用情況
        if hasattr(response, 'usage'):
            self.last_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
        content = response.choices[0].message.content
        return content

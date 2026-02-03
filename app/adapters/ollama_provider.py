from typing import Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.interfaces import LLMProvider

class OllamaProvider(LLMProvider):
    def __init__(self, model_name: str = "glm-4.7-flash:latest", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.client = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.7,
            num_ctx=32768, # 擴大上下文到 32k
            request_timeout=300.0 # 延長超時到 5 分鐘
        )
        self.last_usage = None

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        # Allow overriding temperature if passed in kwargs
        if "temperature" in kwargs:
            self.client.temperature = kwargs["temperature"]

        response = await self.client.ainvoke(messages)
        content = response.content
        
        if not content:
            print("DEBUG: Ollama returned EMPTY content.")
            return ""

        # 更強健的過濾邏輯：只移除完整的標籤，並處理未閉合的情況
        import re
        raw_len = len(content)
        # 移除已閉合的標籤
        content = re.sub(r'<(thought|reasoning)>.*?</\1>', '', content, flags=re.DOTALL)
        # 移除未閉合的起始標籤及其後所有內容 (針對超時或截斷情況)
        content = re.sub(r'<(thought|reasoning)>.*', '', content, flags=re.DOTALL).strip()
        
        print(f"DEBUG: Ollama Raw Length: {raw_len}, Cleaned Length: {len(content)}")
        
        # 提取 Ollama Token 數據 (LangChain 結構)
        try:
            if hasattr(response, 'usage_metadata'):
                self.last_usage = {
                    "prompt_tokens": response.usage_metadata.get('input_tokens', 0),
                    "completion_tokens": response.usage_metadata.get('output_tokens', 0),
                    "total_tokens": response.usage_metadata.get('total_tokens', 0)
                }
        except:
            self.last_usage = None

        return content

import asyncio
import os
import sys
from dotenv import load_dotenv

# 將專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.openai_provider import OpenAIProvider

async def test_openai():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ 錯誤：找不到 OPENAI_API_KEY 環境變數。請確認 .env 檔案內容。")
        return

    print(f"正在測試模型: gpt-5-mini-2025-08-07...")
    provider = OpenAIProvider(api_key=api_key, model_name="gpt-5-mini-2025-08-07")
    
    try:
        response = await provider.generate(
            prompt="請用繁體中文打招呼，並確認你的模型名稱。",
            system_prompt="You are a helpful assistant."
        )
        print("\n✅ 成功收到回應：")
        print("-" * 30)
        print(response)
        print("-" * 30)
    except Exception as e:
        print(f"\n❌ 調用失敗：{e}")

if __name__ == "__main__":
    asyncio.run(test_openai())


import json
import os
from typing import Dict, Any

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "llm_settings.json")

DEFAULT_CONFIG = {
    "default": {
        "provider": "Ollama (本地端)",
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model_name": "glm-4.7-flash:latest"
    },
    "aggregation": {
        "provider": "Ollama (本地端)",
        "model_name": "glm-4.7-flash:latest"
    },
    "editor": {
        "provider": "Ollama (本地端)",
        "model_name": "glm-4.7-flash:latest"
    },
    "newsletter": {
        "provider": "Ollama (本地端)",
        "model_name": "glm-4.7-flash:latest"
    },
    "chief_editor": {
        "provider": "DeepSeek (API)",  # Defaulting to DeepSeek for quality
        "model_name": "deepseek-chat"
    },
    "tagging": {
        "provider": "Ollama (本地端)",
        "model_name": "glm-4.7-flash:latest"
    },
    "cluster_refinement": {
        "provider": "DeepSeek (API)",
        "model_name": "deepseek-chat"
    }
}

class LLMConfigManager:
    @staticmethod
    def load_config() -> Dict[str, Any]:
        if not os.path.exists(CONFIG_PATH):
            return DEFAULT_CONFIG
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CONFIG

    @staticmethod
    def save_config(config: Dict[str, Any]):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    @staticmethod
    def get_agent_config(agent_name: str, full_config: Dict[str, Any] = None) -> Dict[str, Any]:
        if full_config is None:
            full_config = LLMConfigManager.load_config()
        
        # Merge with default settings to ensure keys exist
        base_defaults = full_config.get("default", DEFAULT_CONFIG["default"])
        agent_specific = full_config.get(agent_name, {})
        
        # If agent specific missing, fallback to default block
        if not agent_specific:
             return base_defaults

        # Construct final config
        final_config = base_defaults.copy()
        final_config.update(agent_specific)
        return final_config

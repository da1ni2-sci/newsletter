from typing import Dict

class TokenTracker:
    def __init__(self):
        # 紀錄各個階段的 Token 消耗
        # 結構: {"Ingestion": {"prompt": 0, "completion": 0}, ...}
        self.usage = {}

    def add_usage(self, stage: str, prompt_tokens: int, completion_tokens: int):
        if stage not in self.usage:
            self.usage[stage] = {"prompt": 0, "completion": 0}
        
        self.usage[stage]["prompt"] += prompt_tokens
        self.usage[stage]["completion"] += completion_tokens

    def get_stage_total(self, stage: str) -> int:
        if stage in self.usage:
            return self.usage[stage]["prompt"] + self.usage[stage]["completion"]
        return 0

    def get_total(self) -> int:
        total = 0
        for stage in self.usage:
            total += self.usage[stage]["prompt"] + self.usage[stage]["completion"]
        return total

    def reset(self):
        self.usage = {}

"""Compatibility adapter for existing planning/compiler calls."""
from modules.llm.provider import ProviderClient
from modules.config import GEMINI_MODEL

class NvidiaClient(ProviderClient):
    def __init__(self, max_retries=1, **kwargs):
        super().__init__(model=kwargs.pop("model", GEMINI_MODEL), **kwargs)
        self.max_retries = max_retries

    def _chat_gemini(self, messages, temperature=.2):
        return self.gemini(messages, temperature)

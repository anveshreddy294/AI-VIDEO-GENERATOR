"""Modern, instance-scoped Gemini adapter."""
from modules.llm.provider import ProviderClient, parse_json

class GeminiClient(ProviderClient):
    def __init__(self, model=None, max_retries=1, **kwargs):
        super().__init__(model=model, **kwargs)

    def generate_text(self, prompt, system=None):
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        return self.gemini(messages)

    def generate_json(self, prompt, system=None):
        return parse_json(self.generate_text(prompt, (system or "") + "\nReturn valid JSON only."))

_parse_json = parse_json

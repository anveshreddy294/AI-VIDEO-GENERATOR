"""One bounded live provider check; never print credentials or raw exceptions."""
import json
from modules.llm.provider import ProviderClient, ProviderError

client = ProviderClient()
result = {"model": client.model, "credentials_present": bool(client.gemini_key or client.nvidia_key)}
try:
    client.gemini([{"role": "user", "content": "Reply with OK only."}], max_tokens=64, timeout=30)
    result["LIVE_PROVIDER_TEST"] = "PASS"
except ProviderError as exc:
    result.update(LIVE_PROVIDER_TEST="NOT_VERIFIED", failure=exc.kind)
print(json.dumps(result))

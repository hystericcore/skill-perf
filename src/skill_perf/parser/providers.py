"""LLM provider detection from API URLs."""


_DOMAIN_MAP: dict[str, str] = {
    "api.anthropic.com": "anthropic",
    "api.openai.com": "openai",
    "generativelanguage.googleapis.com": "google",
    "api.together.xyz": "together",
    "api.groq.com": "groq",
    "api.mistral.ai": "mistral",
    "api.deepseek.com": "deepseek",
    "bedrock-runtime": "aws-bedrock",
}


def detect_provider(url: str) -> str:
    """Detect LLM provider from API URL.

    Returns one of: anthropic, openai, google, together, groq,
    mistral, deepseek, aws-bedrock, or unknown.
    """
    for domain, provider in _DOMAIN_MAP.items():
        if domain in url:
            return provider
    return "unknown"

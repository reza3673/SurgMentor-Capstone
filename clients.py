# clients.py
"""
Shared API clients — initialized once at import, reused everywhere.

Importing this module creates the DeepSeek client singleton.
All LLM calls across all skills use this single client instance.
"""

from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

# DeepSeek is OpenAI API-compatible; the OpenAI SDK is used with a custom base URL.
deepseek = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

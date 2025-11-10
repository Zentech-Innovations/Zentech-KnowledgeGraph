# llmWrapper.py
import google.generativeai as genai
from openai import OpenAI
import anthropic
from appConfig import (
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    CLAUDE_API_KEY,
    GEMINI_MODEL,
    OPENAI_MODEL,
    CLAUDE_MODEL,
)


class ModelWrapper:
    """A wrapper class to unify interactions with different LLM providers."""

    def __init__(self, provider: str):
        self.provider = provider.lower()

    def generate(self, prompt: str) -> str:
        """Generates content based on the selected provider."""
        if "gemini" in self.provider:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL)
            return model.generate_content(prompt).text

        elif "gpt" in self.provider:
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip()

        elif "claude" in self.provider:
            client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=10240,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

"""
LLM client utilities for SemQueryBench preprocessing.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests


class OpenAICompatibleClient:
    """
    Minimal OpenAI-compatible chat client.

    Supported base_url examples:
        https://api.openai.com/v1
        https://api.openai.com/v1/chat/completions
        https://dashscope.aliyuncs.com/compatible-mode/v1
        https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: int = 120,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty.")
        if not base_url:
            raise ValueError("base_url must not be empty.")
        if not model:
            raise ValueError("model must not be empty.")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.extra_body = extra_body or {}

    def _chat_completions_url(self) -> str:
        """
        Return a valid chat completions endpoint.

        If the user already passes a full /chat/completions endpoint, use it as-is.
        Otherwise append /chat/completions.
        """
        if self.base_url.endswith("/chat/completions"):
            return self.base_url

        return f"{self.base_url}/chat/completions"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a chat completion request and return the message content.
        """
        url = self._chat_completions_url()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        payload.update(self.extra_body)

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

        if not response.ok:
            raise RuntimeError(
                f"LLM request failed with status {response.status_code}. "
                f"URL: {url}. "
                f"Response: {response.text}"
            )

        data = response.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response format: {data}") from exc
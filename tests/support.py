from __future__ import annotations


class FakeLLMProvider:
    """LLM provider deterministico per i test: restituisce risposte preimpostate."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return ""

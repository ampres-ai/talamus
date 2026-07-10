"""Hard wall-clock timeout around an LLM provider.

Real finding: `subprocess.run(timeout=...)` does NOT reliably kill a hung
`gemini-cli` (node) call on Windows — the pipe stays open and the call blocks
indefinitely past the timeout. That stalled a whole eval batch for hours. This
wrapper runs each call in a daemon thread and abandons it after `seconds`,
raising TimeoutError so the caller's fault handling kicks in. The leaked thread
is a daemon, so it never blocks process exit.

(The product engine adapter has its own configurable timeout —
`TALAMUS_ENGINE_TIMEOUT`; this wrapper hardens the benchmark harness, which
drives engines the product does not.)"""

from __future__ import annotations

import threading


class TimeoutLLM:
    def __init__(self, inner, seconds: float = 90.0) -> None:
        self._inner = inner
        self._seconds = seconds

    def complete(self, prompt: str) -> str:
        result: dict = {}

        def work() -> None:
            try:
                result["value"] = self._inner.complete(prompt)
            except Exception as exc:  # carry the inner error across the thread
                result["error"] = exc

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        thread.join(self._seconds)
        if thread.is_alive():
            raise TimeoutError(f"LLM call exceeded {self._seconds:.0f}s (hung engine)")
        if "error" in result:
            raise result["error"]
        return result.get("value", "")

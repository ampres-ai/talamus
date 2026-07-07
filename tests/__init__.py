"""Test-suite bootstrap: hermetic TALAMUS_HOME (and CODEX_HOME).

Commands like ``talamus init`` register brains in the machine-wide registry under
``TALAMUS_HOME`` (default ``~/talamus``). Tests must never touch the developer's
real registry or brains, so the whole suite runs against a throwaway home.
Individual tests that need isolation from each other patch ``TALAMUS_HOME`` again.

``CODEX_HOME`` is redirected for the same reason: ``talamus mcp install`` (auto
mode, also called by setup) registers the MCP server GLOBALLY through the codex
CLI when it is on PATH — the developer's real ``~/.codex/config.toml`` must
never be mutated by a test run.
"""

import os
import tempfile

os.environ["TALAMUS_HOME"] = tempfile.mkdtemp(prefix="talamus-test-home-")
os.environ["CODEX_HOME"] = tempfile.mkdtemp(prefix="talamus-test-codex-home-")

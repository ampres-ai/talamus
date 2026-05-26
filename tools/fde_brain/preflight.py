from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def status_text(self) -> str:
        status = "OK" if self.ok else "MISSING"
        return f"{status}: {self.name} - {self.detail}"


def check_cli(name: str, command: str) -> CheckResult:
    found = shutil.which(command)
    if found:
        return CheckResult(name, True, found)
    return CheckResult(name, False, f"{command} not found on PATH")


def _ollama_model_names(stdout: str) -> list[str]:
    names = []
    for line in stdout.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        names.append(stripped.split()[0])
    return names


def _model_name_matches(installed: str, requested: str) -> bool:
    installed_l = installed.lower()
    requested_l = requested.lower()
    if ":" in requested_l:
        return installed_l == requested_l
    return installed_l == requested_l or installed_l.startswith(f"{requested_l}:")


def check_ollama_model(model_name: str = "glm-ocr", display_name: str = "GLM-OCR model") -> CheckResult:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(display_name, False, f"could not run ollama list: {exc}")

    if result.returncode != 0:
        detail = result.stderr.strip() or f"ollama list exited with {result.returncode}"
        return CheckResult(display_name, False, detail)

    if any(_model_name_matches(name, model_name) for name in _ollama_model_names(result.stdout)):
        return CheckResult(display_name, True, f"{model_name} found in ollama list")
    return CheckResult(display_name, False, f"{model_name} not found in ollama list")


def run_preflight(glm_ocr_model: str = "glm-ocr", distill_model: str = "gemma4:e4b") -> list[CheckResult]:
    return [
        check_cli("Claude Code", "claude"),
        check_cli("Codex CLI", "codex"),
        check_cli("Ollama", "ollama"),
        check_ollama_model(glm_ocr_model),
        check_ollama_model(distill_model, "Gemma distillation model"),
        check_cli("Graphify", "graphify"),
        check_cli("Git", "git"),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local engines for the FDE Brain pipeline.")
    parser.add_argument("--glm-ocr-model", default="glm-ocr", help="Ollama model name for GLM-OCR.")
    parser.add_argument("--distill-model", default="gemma4:e4b", help="Ollama model name for local distillation.")
    args = parser.parse_args(argv)

    results = run_preflight(args.glm_ocr_model, args.distill_model)
    for result in results:
        print(result.status_text())

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

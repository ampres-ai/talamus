from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ollama

OCR_MODEL = "glm-ocr"
OCR_PROMPT = (
    "Extract all text from this image. Return only the extracted text, "
    "preserving structure (paragraphs, lists, headings). No commentary."
)


@dataclass(frozen=True)
class OcrResult:
    ok: bool
    text: str
    model: str
    error: str | None = None


def extract_text_from_image(image_path: Path) -> OcrResult:
    try:
        response = ollama.chat(
            model=OCR_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": OCR_PROMPT,
                    "images": [str(image_path)],
                }
            ],
            options={"temperature": 0},
        )
        text = response["message"]["content"].strip()
        return OcrResult(ok=True, text=text, model=OCR_MODEL)
    except Exception as exc:
        return OcrResult(ok=False, text="", model=OCR_MODEL, error=str(exc))

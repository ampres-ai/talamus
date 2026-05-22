import unittest
from pathlib import Path
from unittest.mock import patch

from tools.fde_brain.ocr import OcrResult, extract_text_from_image


class OcrTests(unittest.TestCase):
    @patch("tools.fde_brain.ocr.ollama")
    def test_returns_text_on_success(self, ollama_module) -> None:
        ollama_module.chat.return_value = {
            "message": {"content": "  Hello world\nLine two  "}
        }

        result = extract_text_from_image(Path("C:/img.png"))

        self.assertTrue(result.ok)
        self.assertEqual("Hello world\nLine two", result.text)
        self.assertEqual("glm-ocr", result.model)
        self.assertIsNone(result.error)

    @patch("tools.fde_brain.ocr.ollama")
    def test_passes_image_path_to_ollama(self, ollama_module) -> None:
        ollama_module.chat.return_value = {"message": {"content": "x"}}

        extract_text_from_image(Path("C:/img.png"))

        call_kwargs = ollama_module.chat.call_args.kwargs
        self.assertEqual("glm-ocr", call_kwargs["model"])
        message = call_kwargs["messages"][0]
        self.assertEqual("user", message["role"])
        self.assertEqual(["C:/img.png"], [p.replace("\\", "/") for p in message["images"]])

    @patch("tools.fde_brain.ocr.ollama")
    def test_returns_error_when_ollama_raises(self, ollama_module) -> None:
        ollama_module.chat.side_effect = RuntimeError("model offline")

        result = extract_text_from_image(Path("C:/img.png"))

        self.assertFalse(result.ok)
        self.assertEqual("", result.text)
        self.assertIn("model offline", result.error or "")

    def test_ocr_result_is_frozen_dataclass(self) -> None:
        result = OcrResult(ok=True, text="x", model="m")
        with self.assertRaises(Exception):
            result.text = "y"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()

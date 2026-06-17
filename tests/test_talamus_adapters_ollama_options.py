import unittest

from talamus.adapters.llm import OllamaProvider


class OllamaOptionsTests(unittest.TestCase):
    def test_uses_cli_when_no_options(self):
        seen = {}

        def fake_runner(args, prompt):
            seen["args"] = args
            seen["prompt"] = prompt
            return "cli-answer"

        out = OllamaProvider("gemma4:e4b", runner=fake_runner).complete("hi")
        self.assertEqual(out, "cli-answer")
        self.assertEqual(seen["args"], ["ollama", "run", "gemma4:e4b"])

    def test_uses_http_with_options_and_caps_tokens(self):
        seen = {}

        def fake_poster(url, headers, payload):
            seen["url"] = url
            seen["payload"] = payload
            return {"response": "GROUNDED"}

        provider = OllamaProvider(
            "gemma4:e4b",
            options={"num_predict": 5, "temperature": 0.0},
            poster=fake_poster,
        )
        out = provider.complete("judge this")
        self.assertEqual(out, "GROUNDED")
        self.assertTrue(seen["url"].endswith("/api/generate"))
        self.assertEqual(seen["payload"]["options"]["num_predict"], 5)
        self.assertEqual(seen["payload"]["options"]["temperature"], 0.0)
        self.assertIs(seen["payload"]["stream"], False)

    def test_http_handles_missing_response_key(self):
        provider = OllamaProvider(
            "gemma4:e4b",
            options={"num_predict": 5},
            poster=lambda url, headers, payload: {},
        )
        self.assertEqual(provider.complete("x"), "")

    def test_think_flag_triggers_http_and_is_sent(self):
        seen = {}

        def fake_poster(url, headers, payload):
            seen["payload"] = payload
            return {"response": "CORRECT"}

        # think alone (no options) must still use HTTP — the CLI cannot set it
        provider = OllamaProvider("gemma4:e4b", think=False, poster=fake_poster)
        out = provider.complete("grade this")
        self.assertEqual(out, "CORRECT")
        self.assertIs(seen["payload"]["think"], False)
        self.assertNotIn("options", seen["payload"])


if __name__ == "__main__":
    unittest.main()

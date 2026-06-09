import unittest

from talamus.errors import (
    BrainNotInitialized,
    EngineFailed,
    EngineNotFound,
    TalamusError,
)


class ErrorsTests(unittest.TestCase):
    def test_specific_errors_subclass_base(self) -> None:
        for cls in (BrainNotInitialized, EngineNotFound, EngineFailed):
            self.assertTrue(issubclass(cls, TalamusError))

    def test_messages_are_actionable(self) -> None:
        self.assertIn("talamus init", str(BrainNotInitialized("/tmp/x")))
        self.assertIn("PATH", str(EngineNotFound("claude")))


if __name__ == "__main__":
    unittest.main()

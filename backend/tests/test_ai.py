import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai


class AiGenerateTests(unittest.TestCase):
    def setUp(self) -> None:
        # Ensure we test the offline fallback path deterministically.
        self._saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)

    def tearDown(self) -> None:
        if self._saved_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = self._saved_key

    def test_detect_mode(self) -> None:
        self.assertEqual(ai.detect_mode("write a caption"), "caption")
        self.assertEqual(ai.detect_mode("give me hashtags"), "hashtag")
        self.assertEqual(ai.detect_mode("reply to this review"), "review")
        self.assertEqual(ai.detect_mode("grow my shop"), "idea")

    def test_generate_always_returns_text_and_mode(self) -> None:
        for prompt in ["write a caption", "hashtags please", "review reply", ""]:
            result = ai.generate(prompt)
            self.assertIn("text", result)
            self.assertIn("mode", result)
            self.assertTrue(result["text"], "text should never be empty")

    def test_fallback_without_key_is_marked_sample(self) -> None:
        result = ai.generate("write a caption for the launch")
        self.assertEqual(result["source"], "sample")
        self.assertEqual(result["mode"], "caption")


if __name__ == "__main__":
    unittest.main()

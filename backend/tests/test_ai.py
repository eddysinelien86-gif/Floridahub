import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai


class AiGenerateTests(unittest.TestCase):
    def setUp(self) -> None:
        # Ensure we test the offline fallback path deterministically.
        self._saved = {
            k: os.environ.pop(k, None)
            for k in ("ANTHROPIC_API_KEY", "MARKETHUB_OLLAMA_MODEL", "OLLAMA_HOST")
        }
        os.environ["MARKETHUB_OLLAMA_MODEL"] = "off"

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value

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

    def test_status_without_any_ai_is_sample(self) -> None:
        self.assertEqual(ai.status()["provider"], "sample")

    def test_fallback_without_key_is_marked_sample(self) -> None:
        result = ai.generate("write a caption for the launch")
        self.assertEqual(result["source"], "sample")
        self.assertEqual(result["mode"], "caption")


class _FakeOllama(BaseHTTPRequestHandler):
    seen: list = []

    def do_GET(self) -> None:  # noqa: N802
        payload = json.dumps({"models": [{"name": "tiny-test"}]})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, body))
        payload = json.dumps({"message": {"content": ' "Warm attic, lower bills." '}})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))

    def log_message(self, *args: object) -> None:
        return


class AiOllamaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            k: os.environ.pop(k, None)
            for k in ("ANTHROPIC_API_KEY", "MARKETHUB_OLLAMA_MODEL", "OLLAMA_HOST")
        }
        _FakeOllama.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), _FakeOllama)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        for key, value in self._saved.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value

    def test_local_model_is_used_without_a_key(self) -> None:
        os.environ["OLLAMA_HOST"] = f"127.0.0.1:{self.server.server_port}"
        os.environ["MARKETHUB_OLLAMA_MODEL"] = "tiny-test"
        result = ai.generate("write a caption about attics")
        self.assertEqual(result["source"], "ollama")
        self.assertEqual(result["text"], "Warm attic, lower bills.")
        path, body = _FakeOllama.seen[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(body["model"], "tiny-test")
        self.assertFalse(body["stream"])

    def test_status_reports_local_model_only_when_downloaded(self) -> None:
        os.environ["OLLAMA_HOST"] = f"127.0.0.1:{self.server.server_port}"
        os.environ["MARKETHUB_OLLAMA_MODEL"] = "tiny-test"
        self.assertEqual(ai.status()["provider"], "ollama")
        os.environ["MARKETHUB_OLLAMA_MODEL"] = "not-pulled"
        self.assertEqual(ai.status()["provider"], "sample")

    def test_unreachable_local_model_falls_back_quietly(self) -> None:
        port = self.server.server_port
        self.server.shutdown()
        self.server.server_close()
        os.environ["OLLAMA_HOST"] = f"http://127.0.0.1:{port}"
        result = ai.generate("write a caption")
        self.assertEqual(result["source"], "sample")
        self.assertNotIn("error", result)
        self.server = HTTPServer(("127.0.0.1", 0), _FakeOllama)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


if __name__ == "__main__":
    unittest.main()

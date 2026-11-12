import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["HUB_DB"] = os.path.join(tempfile.mkdtemp(), "hub_test.db")
os.environ["HUB_ADMIN_TOKEN"] = "test-token"

import hub_db  # noqa: E402
import hub_server  # noqa: E402


class ParseTests(unittest.TestCase):
    def test_supported_links(self):
        cases = {
            "https://www.youtube.com/watch?v=aqz-KE-bpKQ&t=3": "https://www.youtube-nocookie.com/embed/aqz-KE-bpKQ",
            "https://youtu.be/aqz-KE-bpKQ": "https://www.youtube-nocookie.com/embed/aqz-KE-bpKQ",
            "https://youtube.com/shorts/aqz-KE-bpKQ": "https://www.youtube-nocookie.com/embed/aqz-KE-bpKQ",
            "https://vimeo.com/76979871": "https://player.vimeo.com/video/76979871",
            "https://www.tiktok.com/@some.user/video/7301234567890123456": "https://www.tiktok.com/embed/v2/7301234567890123456",
            "https://www.instagram.com/reel/Cx1Ab_c-dEf/": "https://www.instagram.com/p/Cx1Ab_c-dEf/embed",
        }
        for url, embed in cases.items():
            self.assertEqual(hub_db.parse_video_url(url)["embed_url"], embed, url)

    def test_rejected_links(self):
        for url in [
            "https://evil.example/watch?v=aqz-KE-bpKQ",
            "https://youtube.com.evil.example/watch?v=aqz-KE-bpKQ",
            "javascript:alert(1)",
            "https://www.youtube.com/watch?v=short",
            "https://www.youtube.com/embed/aqz-KE-bpKQ\"><script>",
            "not a url",
            "",
        ]:
            self.assertIsNone(hub_db.parse_video_url(url), url)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hub_db.init_db()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), hub_server.HubHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def call(self, path, body=None, token=None):
        req = urllib.request.Request(self.base + path, method="POST" if body is not None else "GET")
        if body is not None:
            req.data = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("X-Admin-Token", token)
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def submission(self, **over):
        body = {
            "url": "https://youtu.be/aqz-KE-bpKQ", "title": "Beach day", "category": "Lifestyle",
            "contact": "me@example.com", "rights_confirmed": True,
        }
        body.update(over)
        return body

    def test_submission_moderation_flow(self):
        status, _ = self.call("/api/submissions", self.submission(rights_confirmed=False))
        self.assertEqual(status, 400)
        status, _ = self.call("/api/submissions", self.submission(url="https://example.com/x.mp4"))
        self.assertEqual(status, 400)

        status, made = self.call("/api/submissions", self.submission())
        self.assertEqual(status, 201)
        vid = made["id"]
        self.assertEqual(self.call("/api/submissions", self.submission())[0], 409)

        # Pending videos are not public, and the queue needs the token.
        self.assertEqual(self.call(f"/api/videos/{vid}")[0], 404)
        self.assertEqual(self.call("/api/videos")[1]["total"], 0)
        self.assertEqual(self.call("/api/admin/videos")[0], 401)
        self.assertEqual(self.call("/api/admin/videos", token="wrong")[0], 401)
        self.assertEqual(self.call(f"/api/admin/videos/{vid}", {"action": "approve"})[0], 401)

        queue = self.call("/api/admin/videos", token="test-token")[1]["videos"]
        self.assertEqual([v["id"] for v in queue], [vid])
        self.assertEqual(self.call(f"/api/admin/videos/{vid}", {"action": "approve"}, "test-token")[0], 200)
        self.assertEqual(self.call(f"/api/admin/videos/{vid}", {"action": "feature"}, "test-token")[0], 200)
        self.assertEqual(self.call(f"/api/admin/videos/{vid}", {"action": "bogus"}, "test-token")[0], 400)

        status, video = self.call(f"/api/videos/{vid}")
        self.assertEqual(status, 200)
        self.assertNotIn("contact", video)
        self.call(f"/api/videos/{vid}/view", {})
        listing = self.call("/api/videos?q=beach&category=Lifestyle")[1]
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["videos"][0]["views"], 1)
        self.assertEqual(len(listing["featured"]), 1)
        self.assertEqual(self.call("/api/videos?q=%25")[1]["total"], 0)

        self.call(f"/api/admin/videos/{vid}", {"action": "reject"}, "test-token")
        self.assertEqual(self.call(f"/api/videos/{vid}")[0], 404)

    def test_inquiry(self):
        self.assertEqual(self.call("/api/inquiries", {"name": ""})[0], 400)
        status, _ = self.call("/api/inquiries", {"name": "Ana", "contact": "ana@example.com", "package": "featured"})
        self.assertEqual(status, 201)
        rows = self.call("/api/admin/inquiries", token="test-token")[1]["inquiries"]
        self.assertEqual(rows[0]["name"], "Ana")

    def test_static_and_traversal(self):
        with urllib.request.urlopen(self.base + "/") as res:
            self.assertIn("Content-Security-Policy", res.headers)
            self.assertIn(b"Florida Water", res.read())
        self.assertEqual(self.call("/../backend/hub_config.json")[0], 404)
        self.assertEqual(self.call("/%2e%2e/backend/hub_server.py")[0], 404)


if __name__ == "__main__":
    unittest.main()

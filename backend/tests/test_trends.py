from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import trends  # noqa: E402

SAMPLE_FEED = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>Kendrick Lamar announces surprise album drop this Friday</title>
  <link>https://example.com/a</link>
  <pubDate>Mon, 16 Nov 2026 20:00:00 GMT</pubDate>
  <description>The rapper teased new music on &lt;b&gt;TikTok&lt;/b&gt;, going viral overnight.</description>
</item>
<item>
  <title>Miami rapper lands first Billboard chart entry</title>
  <link>https://example.com/b</link>
  <pubDate>Mon, 16 Nov 2026 18:00:00 GMT</pubDate>
  <description>A Florida hip-hop artist breaks through with a new single.</description>
</item>
<item>
  <title>Local bakery wins small business award</title>
  <link>https://example.com/c</link>
  <pubDate>Sun, 15 Nov 2026 10:00:00 GMT</pubDate>
  <description>Unrelated news to test filtering.</description>
</item>
</channel></rss>"""


class TrendsTest(unittest.TestCase):
    def test_parse_feed_extracts_items(self) -> None:
        items = trends._parse_feed(SAMPLE_FEED, "TestFeed")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["source"], "TestFeed")
        self.assertIn("Kendrick", items[0]["title"])

    def test_html_is_stripped_from_summary(self) -> None:
        items = trends._parse_feed(SAMPLE_FEED, "TestFeed")
        self.assertNotIn("<b>", items[0]["summary"])
        self.assertIn("TikTok", items[0]["summary"])

    def test_relevance_scoring_prefers_on_beat_stories(self) -> None:
        items = trends._parse_feed(SAMPLE_FEED, "TestFeed")
        scores = {
            it["title"]: trends._relevance_score(it["title"] + " " + it["summary"])
            for it in items
        }
        music_scores = [s for t, s in scores.items() if "rapper" in t.lower() or "Kendrick" in t]
        bakery_score = next(s for t, s in scores.items() if "bakery" in t.lower())
        self.assertTrue(all(s > bakery_score for s in music_scores))
        self.assertEqual(bakery_score, 0)

    def test_caption_has_hook_cta_and_hashtags(self) -> None:
        items = trends._parse_feed(SAMPLE_FEED, "TestFeed")
        caption = trends.generate_caption(items[0], brand="Floridahub", seed=0)
        self.assertIn(items[0]["title"], caption)
        self.assertIn("#Floridahub", caption)
        self.assertIn("Floridahub", caption)  # brand appears in the CTA

    def test_hashtags_pull_from_headline(self) -> None:
        tags = trends.generate_hashtags("New Album drops in Miami", brand="Floridahub")
        self.assertIn("#Floridahub", tags)
        self.assertIn("#NewAlbum", tags)
        self.assertIn("#Miami", tags)
        self.assertLessEqual(len(tags), 8)

    def test_normalize_title_dedupes_variants(self) -> None:
        a = trends._normalize_title("Kendrick Lamar: Surprise Album!")
        b = trends._normalize_title("kendrick lamar surprise album")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()

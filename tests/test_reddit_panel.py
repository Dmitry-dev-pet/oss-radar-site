"""Regression tests for the deliberately conservative Reddit panel collector."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reddit_panel import compile_report, safe_post, matches_project, week_for, PANEL, PROJECTS

class PanelTests(unittest.TestCase):
    def test_week_boundaries(self):
        self.assertEqual(week_for(1790553600), 0)
        self.assertEqual(week_for(1791158400), 1)
        self.assertEqual(week_for(1791763200), 2)
        self.assertEqual(week_for(1792368000), 3)
        self.assertIsNone(week_for(1792972800))

    def test_does_not_keep_private_or_deleted_content(self):
        post = {"id": "1ws9ydg", "created_utc": 1790587673,
                "title": "some user content", "selftext": "secret",
                "author": "user", "subreddit": "LocalLLaMA",
                "score": 31, "num_comments": 3, "_meta": {"retrieved_2nd_on": 1790800000}}
        sanitized = safe_post(post)
        self.assertIsNotNone(sanitized)
        self.assertNotIn("title", sanitized)
        self.assertNotIn("author", sanitized)
        self.assertNotIn("selftext", sanitized)
        self.assertIsNone(safe_post({**post, "_meta": {"was_deleted_later": True}}))
        self.assertIsNone(safe_post({**post, "author": "[deleted]"}))

    def test_unrelated_short_name_does_not_match(self):
        project = next(p for p in PROJECTS if p["repo"] == "morluto/rea")
        self.assertFalse(matches_project({"title": "A real estate agency"}, project))
        self.assertTrue(matches_project({"title": "Reverse Engineer Anything"}, project))

    def test_failed_queries_are_not_zero(self):
        p = PROJECTS[0]
        r = compile_report([{"repo": p["repo"], "subreddit": PANEL[0],
                             "status": "error", "error": "HTTPError:422", "posts": []}],
                           expected_panel=PANEL[:2], projects=[p])
        self.assertEqual(r["weeks"][0]["projects"][0]["panel_status"], "incomplete_panel")
        self.assertEqual(r["weeks"][0]["projects"][0]["successful_subreddits"], 0)
        self.assertEqual(len(r["diagnostics"]), 2)

    def test_complete_search_and_crosspost_dedup(self):
        p = PROJECTS[0]
        raw = {"id":"1ws9ydg", "created_utc":1790587673, "subreddit":"LocalLLaMA", "score":7, "num_comments":8}
        one = safe_post(raw)
        two = safe_post({**raw,"id":"1ws9ydh","crosspost_parent":"t3_1ws9ydg"})
        response = compile_report([{"repo":p["repo"],"subreddit":PANEL[0],
                                    "status":"complete_query","posts":[one,two]}],
                                  expected_panel=PANEL[:1],projects=[p])
        w=response["weeks"][0]["projects"][0]
        self.assertEqual(w["panel_status"],"complete_panel")
        self.assertEqual(w["found_posts_lower_bound"],2)
        self.assertEqual(w["independent_threads_lower_bound"],1)

if __name__ == "__main__":
    unittest.main()

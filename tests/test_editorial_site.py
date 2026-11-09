"""Static contract: OSS Radar serves only trend-sourced editorial reviews."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote
import re
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "reviews" / "2026-11-08.html"
PUBLIC = [ROOT / "index.html", *sorted((ROOT / "reviews").glob("*.html"))]


class InspectHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.scripts = set(), [], []
        self.headings = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "script":
            self.scripts.append(attrs)
        if tag == "h1":
            self.headings.append(attrs)


class TestEditorialOnly(unittest.TestCase):
    def test_main_and_article_only_no_live_catalog_or_script(self):
        for path in PUBLIC:
            html = path.read_text(encoding="utf-8")
            parsed = InspectHTML()
            parsed.feed(html)
            self.assertEqual(len(parsed.headings), 1, path.name)
            self.assertTrue(all(x.get("src")=="./review-catalog.js" for x in parsed.scripts), path.name)
            self.assertEqual(len(parsed.scripts), 1 if path.name=="index.html" else 0)
            for banned in ('href="./trends.html"', 'href="./october.html"',
                           'href="#catalog"', 'src="./app.js"', 'data/manifest.json'):
                self.assertNotIn(banned, html, path.name)

    def test_all_internal_links_resolve(self):
        for path in PUBLIC:
            parsed = InspectHTML()
            parsed.feed(path.read_text(encoding="utf-8"))
            for href in parsed.links:
                if href.startswith(("http://", "https://", "mailto:")):
                    continue
                url = urlparse(href)
                if not url.path and url.fragment:
                    self.assertIn(url.fragment, parsed.ids, href)
                else:
                    target = (path.parent / unquote(url.path)).resolve()
                    self.assertTrue(target.is_relative_to(ROOT), href)
                    self.assertTrue(target.is_file(), href)

    def test_trend_signal_and_original_readmes_required(self):
        page = ORIGINAL.read_text(encoding="utf-8")
        self.assertIn("GitHub Trending Today", page)
        self.assertIn("06:58 UTC", page)
        self.assertIn("2026", page)
        for project in ("vercel-labs/agent-browser",
                        "cloudflare/security-audit-skill",
                        "milind-soni/OpenMausBot",
                        "ranxianglei/billion-context"):
            self.assertIn('href="https://github.com/' + project + '"', page)
        self.assertIn("Код не выполнялся", page)
        self.assertRegex(page, r"Что проверить:")
        self.assertGreaterEqual(page.count("Что проверить:"), 4)
        self.assertIn("githubtrending.today/methodology/", page)

    def test_editorial_catalog_is_local_and_matches_published_articles(self):
        catalog = json.loads((ROOT / "reviews/catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], 1)
        allowed = {"weekly", "monthly", "deep", "comparison", "experiment"}
        items = catalog["articles"]
        self.assertEqual(len(items), len({x["id"] for x in items}))
        self.assertTrue(items)
        self.assertGreaterEqual(len(items), 7)
        self.assertEqual(sum(x["type"]=="weekly" for x in items),5)
        self.assertEqual(sum(x["type"]=="monthly" for x in items),1)
        for row in items:
            self.assertIn(row["type"], allowed)
            self.assertRegex(row["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertRegex(row["url"], r"^reviews/[a-z0-9-]+\.html$")
            self.assertTrue((ROOT / row["url"]).is_file())
            self.assertTrue(row["projects"])
            self.assertTrue(row["trending_source"])
            self.assertTrue(row["trending_seen_at"])
            self.assertTrue(row["trending_evidence"].startswith("https://"))
            self.assertIn(row["verification"], {"documentation","source","executed"})
        for row in items:
            if row["url"].startswith("reviews/2026-10-"):
                self.assertRegex(row["period_start"],r"^2026-10-\d{2}$")
                self.assertRegex(row["period_end"],r"^2026-10-\d{2}$")
                self.assertLessEqual(row["period_start"],row["period_end"])
                page=(ROOT / row["url"]).read_text(encoding="utf-8")
                self.assertIn("GitStock",page)
                self.assertIn("23:00 UTC",page)
                self.assertIn("gitstock.org/api/v1/github/trending?",page)
                self.assertTrue(all('https://github.com/'+x in page for x in row["projects"]),row["url"])
                self.assertTrue("Код не" in page or "код не" in page,row["url"])
        client = (ROOT / "review-catalog.js").read_text(encoding="utf-8")
        self.assertIn('fetch("./reviews/catalog.json"', client)
        self.assertNotIn("githubtrending.today/api",client)
        self.assertNotIn("api.github.com",client)
        self.assertNotIn("localStorage",client)

    def test_only_editorial_files_are_published_without_cron(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertNotIn("  schedule:", workflow)
        self.assertNotIn("import_trends.py", workflow)
        self.assertNotIn("trends.js", workflow)
        self.assertIn("review-catalog.js", workflow)
        self.assertIn("catalog.json", workflow)
        self.assertNotIn("cp -R data", workflow)
        self.assertIn("reviews", workflow)
        self.assertIn("test_editorial_site.py", workflow)


if __name__ == "__main__":
    unittest.main()

"""Static contract: OSS Radar serves only trend-sourced editorial reviews."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = [ROOT / "index.html", ROOT / "reviews" / "2026-11-08.html"]


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
            self.assertFalse(parsed.scripts, path.name)
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
        page = PUBLIC[1].read_text(encoding="utf-8")
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

    def test_only_editorial_files_are_published_without_cron(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertNotIn("  schedule:", workflow)
        self.assertNotIn("import_trends.py", workflow)
        self.assertNotIn("trends.js", workflow)
        self.assertNotIn("cp -R data", workflow)
        self.assertIn("reviews", workflow)
        self.assertIn("test_editorial_site.py", workflow)


if __name__ == "__main__":
    unittest.main()

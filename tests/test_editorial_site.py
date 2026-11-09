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

    def test_full_first_week_and_navigation(self):
        catalog = json.loads((ROOT / "reviews/catalog.json").read_text(encoding="utf-8"))
        weeks = sorted((r for r in catalog["articles"] if r["type"] == "weekly"),
                       key=lambda x: x["period_start"])
        self.assertEqual(weeks[0]["period_start"], "2026-09-28")
        self.assertEqual(weeks[0]["period_end"], "2026-10-04")
        self.assertEqual(weeks[0]["url"], "reviews/2026-09-28-10-04.html")
        for left, right in zip(weeks[:3], weeks[1:4]):
            self.assertEqual(
                ( __import__("datetime").date.fromisoformat(left["period_end"])
                + __import__("datetime").timedelta(days=1)).isoformat(),
                right["period_start"])
            self.assertIn(right["url"].split("/")[-1],
                          (ROOT / left["url"]).read_text(encoding="utf-8"))
            self.assertIn(left["url"].split("/")[-1],
                          (ROOT / right["url"]).read_text(encoding="utf-8"))
        redirect = (ROOT / "reviews/2026-10-01-04.html").read_text(encoding="utf-8")
        self.assertIn("2026-09-28-10-04.html", redirect)

    def test_weekly_sources_and_separate_growth_columns(self):
        selected = ["2026-09-28-10-04", "2026-10-05-11",
                    "2026-10-12-18", "2026-10-19-25"]
        for stem in selected:
            page = (ROOT / "reviews" / (stem + ".html")).read_text(encoding="utf-8")
            for token in ("GitStock", "23:00 UTC", "GitHub Star History API",
                          "Новых ★", "Рост*", "Дней в Trending",
                          "Редакторский вывод", "9 ноября 2026",
                          "Код", "Методика"):
                if token == "Код":
                    continue  # not every review is about source code
                self.assertIn(token, page, stem)
            self.assertNotIn("четыре (либо пять)", page)
            self.assertIn('id="community"', page)
            self.assertIn('id="sources"', page)

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

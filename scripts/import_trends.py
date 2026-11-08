#!/usr/bin/env python3
"""Mirror *compiled public trends* for GitHub Pages, never crawl GitHub itself.

Single upstream JSON: https://githubtrending.today/api/trending.json, CC BY 4.0.
This job does not collect independent GitHub counts or read private resources.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

UPSTREAM = "https://githubtrending.today/api/trending.json"
NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
KEY = re.compile(r"(all|python|typescript|javascript|rust|go|java|cpp):(daily|weekly|monthly)\Z")
MAX_BYTES = 3_000_000


def parse_time(value):
    if not isinstance(value, str):
        raise ValueError("missing source collection time")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("source collection time must have timezone")
    return dt.astimezone(timezone.utc)


def normalize(raw, now=None):
    if not isinstance(raw, dict) or not isinstance(raw.get("lists"), dict):
        raise ValueError("trending source schema changed")
    now = now or datetime.now(timezone.utc)
    source_time = parse_time(raw.get("collectedAt"))
    if not -timedelta(hours=6) <= now - source_time < timedelta(hours=48):
        raise ValueError("source data too old or too far in the future")
    lists = {}
    metadata = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    for key, candidates in raw["lists"].items():
        if not KEY.fullmatch(key):
            continue
        if not isinstance(candidates, list):
            raise ValueError("invalid list: " + key)
        unique = set()
        repos = []
        for row in candidates[:100]:
            if not isinstance(row, dict):
                raise ValueError("invalid project row")
            name = row.get("name")
            if not isinstance(name, str) or not NAME.fullmatch(name):
                continue
            if name.casefold() in unique:
                continue
            unique.add(name.casefold())
            rank = row.get("rank")
            gained = row.get("gained")
            stars = row.get("stars")
            if not (isinstance(rank, int) and rank > 0 and
                    isinstance(stars, int) and stars >= 0 and
                    isinstance(gained, int) and gained >= 0):
                raise ValueError("invalid rank/star fields for " + name)
            m = metadata.get(name, {})
            if not isinstance(m, dict):
                m = {}
            description = row.get("description")
            license_declared = m.get("license")
            repos.append({
                "name": name, "rank": rank,
                "description": description[:280] if isinstance(description, str) else "",
                "language": row.get("language") if isinstance(row.get("language"), str) else None,
                "stars": stars, "gained": gained,
                "license_declared": license_declared if isinstance(license_declared, str) else None,
            })
        repos.sort(key=lambda x: (x["rank"], x["name"].casefold()))
        lists[key] = repos
    if not lists.get("all:daily") or not lists.get("all:weekly") or not lists.get("all:monthly"):
        raise ValueError("missing main daily/weekly/monthly lists")
    return {
        "schema": 1, "source": "GitHub Trending Today",
        "source_url": "https://githubtrending.today/",
        "methodology_url": "https://githubtrending.today/methodology/",
        "license": "CC BY 4.0",
        "collected_at": source_time.isoformat().replace("+00:00","Z"),
        "imported_at": now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
        "lists": lists,
        "disclaimer": "Trending list positions and gained stars are provided by the upstream collector. Not exhaustive, not a self-computed or independently verified growth ranking. Licenses are GitHub declarations only.",
    }


def download(opener=urlopen):
    request = Request(UPSTREAM, headers={"Accept":"application/json",
                                        "User-Agent":"oss-radar-pages-import/1.0"})
    try:
        with opener(request, timeout=25) as response:
            if getattr(response, "status", 200) != 200:
                raise RuntimeError("unexpected upstream HTTP status")
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise RuntimeError("upstream payload exceeds size limit")
            return json.loads(data)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise RuntimeError("could not read public upstream JSON") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("_site/data/external-trends.json"))
    parser.add_argument("--fixture", type=Path, help="offline contract testing only")
    args = parser.parse_args()
    raw = json.loads(args.fixture.read_text(encoding="utf-8")) if args.fixture else download()
    compiled = normalize(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(compiled, ensure_ascii=False, separators=(",",":"))+"\n", encoding="utf-8")
    print(json.dumps({"source_collected_at": compiled["collected_at"],
                      "main_daily": len(compiled["lists"]["all:daily"]),
                      "main_weekly": len(compiled["lists"]["all:weekly"]),
                      "main_monthly": len(compiled["lists"]["all:monthly"]),
                      "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Bounded Reddit archive *discovery* panel for OSS Radar.

This is NOT a count of all Reddit mentions. Searches a fixed set of named
subreddits, and fails open visibly as "incomplete", never as zero.
No account identifiers or Reddit-authored body/title text are persisted.
Third-party Arctic Shift is not the official Reddit API. No training use.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://arctic-shift.photon-reddit.com/api/posts/search"
PROVIDER_DOCS = "https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md"
USER_AGENT = "OSS-Radar-public-editorial-observation/0.1"
# This is the same fixed panel for every project. It is NOT Reddit-wide coverage.
PANEL = (
    "claudeskills", "ClaudeCode", "LocalLLaMA", "BestGitHubRepos",
    "ReverseEngineering", "robotics", "opensource", "Piracy",
)
WEEKS = (
    ("2026-09-28", "2026-10-05"),
    ("2026-10-05", "2026-10-12"),
    ("2026-10-12", "2026-10-19"),
    ("2026-10-19", "2026-10-26"),
)
# One narrow primary search phrase per repo. The match terms remove obvious
# unrelated hits; a post with only an unindexed reference may still be missed.
PROJECTS = (
    {"repo": "NVIDIA/OpenShell", "query": "OpenShell", "matches": ("openshell",)},
    {"repo": "DietrichGebert/ponytail", "query": "Ponytail", "matches": ("ponytail",)},
    {"repo": "obra/superpowers", "query": "superpowers", "matches": ("obra/superpowers", "superpowers skill", "superpowers plugin")},
    {"repo": "morluto/rea", "query": "Reverse Engineer Anything", "matches": ("reverse engineer anything", "morluto/rea", "rea-agents")},
    {"repo": "boykopovar/AnyPS5", "query": "AnyPS5", "matches": ("anyps5",)},
    {"repo": "storytold/artcraft", "query": "ArtCraft", "matches": ("storytold/artcraft", "artcraft")},
    {"repo": "debpalash/VoiceStudio", "query": "VoiceStudio", "matches": ("voicestudio",)},
    {"repo": "mksglu/context-mode", "query": "context-mode", "matches": ("context-mode", "context mode")},
    {"repo": "cloudflare/security-audit-skill", "query": "security audit skill", "matches": ("security-audit-skill", "security audit skill")},
    {"repo": "stablyai/orca", "query": "onOrca", "matches": ("stablyai/orca", "onorca", "orca ai orchestrator")},
    {"repo": "Graphify-Labs/graphify", "query": "Graphify", "matches": ("graphify",)},
    {"repo": "pollen-robotics/microduck", "query": "Microduck", "matches": ("microduck",)},
    {"repo": "K-Dense-AI/scientific-agent-skills", "query": "Scientific Agent Skills", "matches": ("scientific agent skills", "scientific-agent-skills")},
)
RATE_LIMITED = Event()
MAX_PAGES_PER_QUERY = 3
PAGE_LIMIT = 100
EPOCH_START = int(datetime.fromisoformat(WEEKS[0][0]).replace(tzinfo=timezone.utc).timestamp())
EPOCH_END = int(datetime.fromisoformat(WEEKS[-1][1]).replace(tzinfo=timezone.utc).timestamp())

def week_for(timestamp: int):
    for i, (start, stop) in enumerate(WEEKS):
        lo = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
        hi = int(datetime.fromisoformat(stop).replace(tzinfo=timezone.utc).timestamp())
        if lo <= timestamp < hi:
            return i
    return None

def matches_project(post: dict, project: dict) -> bool:
    hay = " ".join(str(post.get(k) or "") for k in ("title", "selftext", "url")).lower()
    return any(s in hay for s in project["matches"])

def safe_post(post: dict):
    """Return only aggregates, IDs, public permalink and archival metadata."""
    m = post.get("_meta") or {}
    if (post.get("author") == "[deleted]" or m.get("was_deleted_later")
            or post.get("removed_by_category") is not None
            or post.get("selftext") == "[deleted]"):
        return None
    pid = str(post.get("id") or "")
    created = post.get("created_utc")
    if not re.fullmatch(r"[0-9a-z]{5,12}", pid) or not isinstance(created, (int, float)):
        return None
    score = post.get("score")
    comments = post.get("num_comments")
    crosspost = post.get("crosspost_parent")
    return {
        "id": pid,
        "week": week_for(int(created)),
        "subreddit": str(post.get("subreddit") or ""),
        "score_archived": int(score) if isinstance(score, (int, float)) else None,
        "comments_archived": int(comments) if isinstance(comments, (int, float)) else None,
        "score_snapshot_utc": m.get("retrieved_2nd_on"),
        "crosspost_parent": crosspost if isinstance(crosspost, str) else None,
        "permalink": "https://www.reddit.com/comments/" + pid + "/",
    }

def fetch_query(project: dict, subreddit: str, timeout=13):
    if RATE_LIMITED.is_set():
        return {"subreddit": subreddit, "repo": project["repo"],
                "status": "rate_limited_skipped", "posts": []}
    before = EPOCH_END
    seen = set()
    rows = []
    for page in range(MAX_PAGES_PER_QUERY):
        if RATE_LIMITED.is_set():
            return {"subreddit": subreddit, "repo": project["repo"],
                    "status": "rate_limited_skipped", "posts": rows}
        params = {
            "subreddit": subreddit,
            "query": project["query"],
            "after": EPOCH_START,
            "before": before,
            "sort": "desc",
            "limit": PAGE_LIMIT,
        }
        url = ENDPOINT + "?" + urlencode(params)
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        last_error = None
        for attempt in range(2):
            try:
                with urlopen(req, timeout=timeout) as resp:
                    payload = json.loads(resp.read(4_000_000).decode("utf-8"))
                last_error = None
                break
            except (HTTPError, URLError, TimeoutError, ValueError, UnicodeError) as exc:
                last_error = "%s:%s" % (type(exc).__name__, getattr(exc, "code", str(exc))[:80] if isinstance(getattr(exc, "code", None), str) else getattr(exc, "code", str(exc)) )
                # An invalid query or unsupported search is not an empty result.
                if isinstance(exc, HTTPError) and exc.code == 429:
                    RATE_LIMITED.set()
                    break
                if isinstance(exc, HTTPError) and exc.code in (400, 401, 403, 404, 422):
                    break
                if attempt == 0:
                    time.sleep(1.5)
        if last_error:
            return {"subreddit": subreddit, "repo": project["repo"],
                    "status": "error", "error": str(last_error), "posts": []}
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            return {"subreddit": subreddit, "repo": project["repo"],
                    "status": "schema_error", "posts": []}
        batch = payload["data"]
        for post in batch:
            if not isinstance(post, dict) or not matches_project(post, project):
                continue
            clean = safe_post(post)
            if clean is not None and clean["week"] is not None and clean["id"] not in seen:
                seen.add(clean["id"])
                rows.append(clean)
        if len(batch) < PAGE_LIMIT:
            return {"subreddit": subreddit, "repo": project["repo"], "status": "complete_query", "posts": rows}
        earliest = min((int(p.get("created_utc", before)) for p in batch), default=before)
        if earliest >= before:
            break
        before = earliest
    return {"subreddit": subreddit, "repo": project["repo"], "status": "truncated", "posts": rows}

def compile_report(results: list[dict], expected_panel=PANEL, projects=PROJECTS):
    by_pair = {(x["repo"], x["subreddit"]): x for x in results}
    weeks = [{"start": s, "end_exclusive": e, "projects": []} for s, e in WEEKS]
    diagnostics = []
    for project in projects:
        repo = project["repo"]
        statuses = []
        posts_by_id = {}
        for sub in expected_panel:
            result = by_pair.get((repo, sub))
            status = result["status"] if result else "not_attempted"
            statuses.append(status)
            if status != "complete_query":
                diagnostics.append({"repo": repo, "subreddit": sub, "status": status,
                                    "error": result.get("error") if result else None})
            for post in (result or {}).get("posts", []):
                posts_by_id[post["id"]] = post
        complete = all(status == "complete_query" for status in statuses)
        for i, week in enumerate(weeks):
            posts = sorted((p for p in posts_by_id.values() if p["week"] == i),
                           key=lambda p: p["id"])
            communities = sorted(set(p["subreddit"] for p in posts))
            independent = len(set((p["crosspost_parent"] or p["id"]).removeprefix("t3_") for p in posts))
            score = sum(p["score_archived"] for p in posts if p["score_archived"] is not None)
            comments = sum(p["comments_archived"] for p in posts if p["comments_archived"] is not None)
            week["projects"].append({
                "repo": repo, "panel_status": "complete_panel" if complete else "incomplete_panel",
                "searched_subreddits": len(expected_panel),
                "successful_subreddits": sum(s == "complete_query" for s in statuses),
                "found_posts_lower_bound": len(posts),
                "independent_threads_lower_bound": independent,
                "archive_score_sum_lower_bound": score,
                "archive_comments_sum_lower_bound": comments,
                "communities_found": len(communities),
                "post_refs": posts,
            })
    return {
        "schema_version": 1,
        "source": "Arctic Shift third-party public archive; NOT official Reddit Data API",
        "source_docs": PROVIDER_DOCS,
        "coverage": {
            "scope": "fixed panel of subreddit searches, not Reddit-wide",
            "subreddits": list(expected_panel),
            "all_reddit_coverage": False,
            "score_is_historical_week_end": False,
            "score_note": "scores/comments are the archive snapshots, NOT values at the end of each October week",
            "zero_policy": "0 is meaningful only within a complete panel. For errors, counts are LOWER BOUNDS.",
            "keyword_policy": "one narrow query per project; mentions missed by search are not counted",
            "privacy": "No account names, usernames, user IDs, post titles or bodies are stored. Deleted posts are excluded.",
        },
        "weeks": weeks,
        "diagnostics": diagnostics,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reddit-panel-2026-10.json")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    selected = PROJECTS[:3] if args.pilot else PROJECTS
    chosen_panel = PANEL[:3] if args.pilot else PANEL
    jobs = [(p, s) for p in selected for s in chosen_panel]
    print(f"REDDIT_QUERY_PLAN projects={len(selected)} panel={len(chosen_panel)} queries={len(jobs)}", flush=True)
    reports = []
    with ThreadPoolExecutor(max_workers=min(3, max(1, args.workers))) as executor:
        futures = [executor.submit(fetch_query, p, s) for p, s in jobs]
        for done in as_completed(futures):
            row = done.result()
            reports.append(row)
            print(f"QUERY {row['repo']} r/{row['subreddit']} {row['status']} hits={len(row['posts'])}", flush=True)
    result = compile_report(reports, expected_panel=chosen_panel, projects=selected)
    result["collection_time_utc"] = datetime.now(timezone.utc).isoformat()
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    for week in result["weeks"]:
        print("WEEK %s" % week["start"], flush=True)
        for p in week["projects"]:
            print("  %-38s posts>=%3d subs=%d/%d %s" % (
                p["repo"], p["found_posts_lower_bound"], p["successful_subreddits"],
                p["searched_subreddits"], p["panel_status"]), flush=True)
    print("REDDIT_ERRORS=%d REPORT=%s" % (len(result["diagnostics"]), args.output), flush=True)
    if result["diagnostics"]:
        print("DATA_QUALITY=BLOCKED: archive does not provide reliable panel coverage", flush=True)
        sys.exit(2)
    print("DATA_QUALITY=PANEL_COMPLETE; not Reddit-wide coverage", flush=True)

if __name__ == "__main__":
    main()

# Reddit coverage panel — OSS Radar

This is an experimental **fixed-subreddit discovery index**, not a Reddit-wide ranking.

- Reproducible intervals: 28 Sep–4 Oct, 5–11 Oct, 12–18 Oct and 19–25 Oct 2026 (UTC).
- Uniform panel: r/claudeskills, r/ClaudeCode, r/LocalLLaMA, r/BestGitHubRepos, r/ReverseEngineering, r/robotics, r/opensource, r/Piracy.
- Collect one explicitly documented search term per project. Match references in title/body/link in-memory; discard all authored text and account information before writing snapshots.
- Record post ID, date window, subreddit, archival score/comment snapshots, and crosspost parent. Do not store usernames, authored titles/bodies, or deleted posts.
- For each project × community, record success/error/truncation. **Never convert a failed lookup to zero.**
- Engagement scores are values from archival snapshots, **not** scores at 23:59 UTC on the historical date and not raw upvote counts.
- Even if all panel requests succeed, the result is **not** a complete count of Reddit mentions: text matching, deleted content and omitted subreddits limit recall.
- Do not incorporate these figures into public editorial rankings until review of error rates, false positives, data protection and source terms.
- Unlike GitHub stars, Reddit engagement signals are not a reliable causal measure of technical quality.

Source: [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md), independent historical archive, **not the official Reddit Data API**. No service uptime guarantee.
Official Reddit [Data API rules](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) and [developer conditions](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data) impose additional restrictions for authorized ongoing harvesting or commercial uses. For ongoing production collection prefer properly approved access rather than treating the archive as a guaranteed service.

Run locally: `python3 -m unittest discover -s tests -p test_reddit_panel.py -v`; `python3 scripts/reddit_panel.py --pilot`.

The corresponding GitHub Action runs only on a change to the collector or explicit dispatch. It does not run on a daily schedule, does not publish raw content to Pages and does not commit its results to `main`. Its JSON artifact expires after 14 days.

## First validation result — 9 November 2026

The first full run attempted 104 project × subreddit queries. Only **3 completed**, with **87 HTTP 429** rate-limit responses and **14 HTTP 422** query errors. The resulting numeric report is **not usable to rank projects**. GitHub Actions run: https://github.com/Dmitry-dev-pet/oss-radar-site/actions/runs/42601662734. A private research receipt preserves the diagnostic totals.

The collector now stops attempting further queries upon HTTP 429 and explicitly fails the data-quality gate when any chosen panel query is incomplete. Its artifact is still uploaded for diagnosis. Do not interpret a collector's technical execution success as a successful popularity measurement. A defensible production Reddit metric will require authorized and stable access to a sufficiently comprehensive source; until then the website continues to show dated individual reports with clear evidence type and links, without a Reddit popularity score.

## Access status — 2026-11-09

Automated archive collection is **paused**. Reddit's official October 8 changelog says new public Data API applications closed on October 31, 2026, with remaining public access ending March 2027. Do not attempt to bypass authorization with third-party scraping or repeated rate-limited calls. The GitHub workflow now runs **offline tests only** when manually dispatched. A suitable authorized data source and permission to publish derived statistics must be established first. Track the request in private `Dmitry-dev-pet/research-lab#26`. Sources: https://support.reddithelp.com/hc/en-us/articles/54353370049684-Changelog-October-8-2026 and https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy .

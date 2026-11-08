#!/usr/bin/env python3
"""Daily measured OSS star growth for a fixed, explicitly sampled public panel.

GraphQL resolves stable repository node IDs once. Later snapshots query those
same IDs, so renames do not become new projects. No historical stars inferred.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API = "https://api.github.com/graphql"
BANDS = [(50, 99), (100, 249), (250, 499), (500, 999), (1000, 2000)]
FEATURED = [
    "CopilotKit/OpenDuet", "datalab-to/indra",
    "reason-machines/reason-network", "Pomerado/pomerado",
    "colinhacks/reylo", "Roboparty/RP1", "mistralai/timestral",
    "emanuele-em/kanzo", "openqodex/openqodex", "ManfredCh/Lyapunov",
]
FIELDS = "id databaseId nameWithOwner url stargazerCount isFork isArchived"
VALID_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


def timestamp(dt):
    if dt.tzinfo is None:
        raise ValueError("UTC-aware time required")
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def select_panel(data_dir):
    """At most 4 per creation-month/current-star band, plus 10 editorial picks."""
    manifest = load_json(data_dir / "manifest.json")
    selected = {}
    for m in manifest["months"]:
        month = m["month"]
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            raise ValueError("invalid month label")
        data = load_json(data_dir / (month + ".json"))
        if data.get("month") != month or not isinstance(data.get("projects"), list):
            raise ValueError("invalid monthly data: " + month)
        for low, high in BANDS:
            group = sorted(
                (r for r in data["projects"]
                 if isinstance(r.get("s"), int) and low <= r["s"] <= high
                 and isinstance(r.get("n"), str) and VALID_NAME.fullmatch(r["n"])),
                key=lambda r: (-r["s"], r["n"]),
            )
            for row in group[:2] + group[-2:]:
                key = row["n"].casefold()
                selected.setdefault(key, {"original_name": row["n"], "month": month,
                                          "selection_band": [low, high],
                                          "selected_stars": row["s"]})
        for row in data["projects"]:
            if row.get("n") in FEATURED and VALID_NAME.fullmatch(row["n"]):
                selected.setdefault(row["n"].casefold(),
                    {"original_name": row["n"], "month": month, "selection_band": "editorial",
                     "selected_stars": row["s"]})
    return list(selected.values())


def graphql(token, query, variables=None, opener=urlopen):
    if not token:
        raise ValueError("GITHUB_TOKEN is required")
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = Request(API, data=payload, headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "Content-Type": "application/json", "User-Agent": "alfred-oss-radar-growth/1.0",
    })
    try:
        with opener(req, timeout=45) as resp:
            response = json.load(resp)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("GraphQL request failed: " + type(exc).__name__) from exc
    if not isinstance(response.get("data"), dict):
        raise RuntimeError("invalid GraphQL response")
    # A deleted or made-private public repository may legitimately be NOT_FOUND.
    for error in response.get("errors", []):
        if error.get("type") != "NOT_FOUND":
            raise RuntimeError("GraphQL returned a non-NOT_FOUND error")
    return response["data"]


def get_batch_nodes(token, panel, existing, query_fn=graphql):
    """Return stable-ID keyed observations; missing/deleted IDs remain absent."""
    found = {}
    for start in range(0, len(panel), 20):
        batch = panel[start:start + 20]
        if existing:
            identifiers = [e["node_id"] for e in batch]
            data = query_fn(token, "query($ids:[ID!]!){nodes(ids:$ids){... on Repository{" +
                            FIELDS + "}}}", {"ids": identifiers})
            nodes = data.get("nodes")
            if not isinstance(nodes, list) or len(nodes) != len(batch):
                raise RuntimeError("invalid GraphQL nodes array")
            pairs = zip(batch, nodes)
        else:
            fields = []
            for i, e in enumerate(batch):
                owner, name = e["original_name"].split("/", 1)
                fields.append("r" + str(i) + ":repository(owner:" + json.dumps(owner) +
                              ",name:" + json.dumps(name) + "){" + FIELDS + "}")
            data = query_fn(token, "query{" + " ".join(fields) + "}")
            pairs = ((e, data.get("r" + str(i))) for i, e in enumerate(batch))
        for entry, node in pairs:
            if node is None:
                continue
            if (not isinstance(node.get("id"), str) or
                    not isinstance(node.get("databaseId"), int) or
                    not isinstance(node.get("stargazerCount"), int) or
                    not isinstance(node.get("nameWithOwner"), str)):
                raise RuntimeError("invalid repository node")
            if existing and node["id"] != entry["node_id"]:
                raise RuntimeError("repository node ID mismatch")
            if node.get("isFork") or node.get("isArchived"):
                continue
            found[node["id"]] = node
    return found


def baseline(repo_id, history, target, tolerance):
    options = []
    for snap in history:
        t = datetime.fromisoformat(snap["collected_at"].replace("Z", "+00:00"))
        distance = abs(t - target)
        if distance > tolerance:
            continue
        for row in snap["repositories"]:
            if row["id"] == repo_id:
                options.append((distance, t, row["stars"]))
    return min(options, key=lambda x: (x[0], x[1]))[2] if options else None


def measure(now, panel, observations, history):
    rows = []
    for entry in panel:
        node = observations.get(entry["node_id"])
        if node is None:
            continue
        repo_id = entry["database_id"]
        row = {"id": repo_id, "name": node["nameWithOwner"],
               "url": node["url"], "month": entry["month"],
               "stars": node["stargazerCount"],
               "delta_24h": None, "delta_7d": None}
        for field, age, tol in (("delta_24h", 1, 8), ("delta_7d", 7, 18)):
            previous = baseline(repo_id, history, now - timedelta(days=age),
                                timedelta(hours=tol))
            if previous is not None:
                row[field] = row["stars"] - previous
        rows.append(row)
    ranked = sorted((r for r in rows if r["delta_24h"] is not None),
                    key=lambda r: (-r["delta_24h"], -r["stars"], r["id"]))
    return {
        "schema": 1, "collected_at": timestamp(now), "panel_size": len(panel),
        "observed": len(rows), "measured_24h": len(ranked),
        "measured_7d": sum(r["delta_7d"] is not None for r in rows),
        "ranking_basis": "measured_24h" if ranked else "insufficient_history",
        "panel_selection": "2 highest + 2 lowest current stars per band/month, plus editorial 10; fixed after bootstrap",
        "caveat": "Tracked panel only, not all 12,188 catalog items; historical deltas require same GitHub ID and a time-matched saved snapshot.",
        "top10": ranked[:10], "repositories": rows,
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(now, data_dir, out_dir, token, query_fn=graphql):
    day = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
    path = out_dir / "snapshots" / (day + ".json")
    if path.exists():
        raise RuntimeError("snapshot for this UTC day exists; refusing overwrite")
    panel_path = out_dir / "panel.json"
    existing = panel_path.exists()
    panel = load_json(panel_path)["repositories"] if existing else select_panel(data_dir)
    if not panel:
        raise RuntimeError("empty tracked panel")
    nodes = get_batch_nodes(token, panel, existing, query_fn=query_fn)
    if existing:
        # ID-based lookup. Lost or deleted projects remain in the panel.
        if len(nodes) < max(1, len(panel) // 2):
            raise RuntimeError("too many tracked repositories unavailable; fail closed")
    else:
        fresh = []
        for e in panel:
            node = next((x for x in nodes.values()
                         if x["nameWithOwner"].casefold() == e["original_name"].casefold()), None)
            if node is None:
                continue
            fresh.append(dict(e, node_id=node["id"], database_id=node["databaseId"]))
        if len(fresh) < max(1, len(panel) // 2):
            raise RuntimeError("bootstrap failed to resolve at least half of public repositories")
        panel = fresh
    history = []
    for f in sorted((out_dir / "snapshots").glob("*.json")):
        record = load_json(f)
        observed = datetime.fromisoformat(record["collected_at"].replace("Z", "+00:00"))
        if timedelta(0) < now - observed <= timedelta(days=9):
            history.append(record)
    latest = measure(now, panel, nodes, history)
    snap = {"schema": 1, "collected_at": timestamp(now), "repositories":
            [{"id": e["id"], "stars": e["stars"]} for e in latest["repositories"]]}
    if not existing:
        write_json(panel_path, {"schema": 1, "selected_at": timestamp(now), "repositories": panel})
    write_json(path, snap)
    write_json(out_dir / "latest.json", latest)
    print(json.dumps({"snapshot": str(path), "panel": len(panel),
                      "observed": latest["observed"],
                      "measured_24h": latest["measured_24h"],
                      "measured_7d": latest["measured_7d"]}))
    return latest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/growth"))
    args = parser.parse_args()
    run(datetime.now(timezone.utc), args.data_dir, args.out_dir, os.environ.get("GITHUB_TOKEN"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

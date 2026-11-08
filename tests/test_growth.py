"""Offline contracts for measured OSS Radar growth. No external network."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "growth.py"
spec = importlib.util.spec_from_file_location("oss_growth", SOURCE)
growth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(growth)
NOW = datetime(2026, 11, 8, 22, 0, tzinfo=timezone.utc)


def node(name, ident=1, stars=100):
    return {"id": "gid-" + str(ident), "databaseId": ident, "nameWithOwner": name,
            "stargazerCount": stars, "url": "https://github.com/" + name,
            "isFork": False, "isArchived": False}


class TestGrowth(unittest.TestCase):
    def test_panel_selection_reproducible_and_stratified(self):
        with TemporaryDirectory() as td:
            p = Path(td)
            (p / "manifest.json").write_text(json.dumps({"months": [{"month": "2026-10"}]}))
            projects = [{"n": "acme/p" + str(i), "s": 60 + i, "d": ""} for i in range(8)]
            projects += [{"n": "CopilotKit/OpenDuet", "s": 1998}]
            (p / "2026-10.json").write_text(json.dumps({"month": "2026-10", "projects": projects}))
            panel = growth.select_panel(p)
            self.assertEqual([x["original_name"] for x in panel],
                             ["acme/p7", "acme/p6", "acme/p1", "acme/p0", "CopilotKit/OpenDuet"])
            self.assertEqual(panel, growth.select_panel(p))

    def test_no_history_returns_no_top_ranking(self):
        panel = [{"node_id": "gid-1", "database_id": 1, "month": "2026-10"}]
        report = growth.measure(NOW, panel, {"gid-1": node("acme/one")}, [])
        self.assertIsNone(report["repositories"][0]["delta_24h"])
        self.assertIsNone(report["repositories"][0]["delta_7d"])
        self.assertEqual(report["top10"], [])
        self.assertEqual(report["ranking_basis"], "insufficient_history")

    def test_24h_and_7d_are_actual_saved_observations(self):
        panel = [{"node_id": "gid-1", "database_id": 1, "month": "2026-10"}]
        history = [
            {"collected_at": growth.timestamp(NOW - timedelta(days=1)),
             "repositories": [{"id": 1, "stars": 70}]},
            {"collected_at": growth.timestamp(NOW - timedelta(days=7)),
             "repositories": [{"id": 1, "stars": 31}]},
        ]
        report = growth.measure(NOW, panel, {"gid-1": node("acme/renamed", stars=100)}, history)
        self.assertEqual(report["top10"][0]["delta_24h"], 30)
        self.assertEqual(report["top10"][0]["delta_7d"], 69)

    def test_stale_or_different_id_has_no_delta(self):
        panel = [{"node_id": "gid-1", "database_id": 1, "month": "2026-10"}]
        history = [
            {"collected_at": growth.timestamp(NOW - timedelta(days=2)),
             "repositories": [{"id": 1, "stars": 70}]},
            {"collected_at": growth.timestamp(NOW - timedelta(days=1)),
             "repositories": [{"id": 2, "stars": 5}]},
        ]
        report = growth.measure(NOW, panel, {"gid-1": node("acme/one")}, history)
        self.assertIsNone(report["repositories"][0]["delta_24h"])

    def test_existing_queries_by_immutable_node_id_not_name(self):
        panel = [{"node_id": "gid-1", "database_id": 1, "original_name": "old/repo"}]
        calls = []
        def fake(token, query, variables=None):
            calls.append((query, variables))
            return {"nodes": [node("new/repo")]}
        found = growth.get_batch_nodes("token", panel, True, query_fn=fake)
        self.assertEqual(found["gid-1"]["nameWithOwner"], "new/repo")
        self.assertEqual(calls[0][1]["ids"], ["gid-1"])
        self.assertNotIn("old/repo", calls[0][0])

    def test_existing_mismatched_node_is_rejected(self):
        panel = [{"node_id": "gid-1", "database_id": 1, "original_name": "old/repo"}]
        with self.assertRaisesRegex(RuntimeError, "ID mismatch"):
            growth.get_batch_nodes("token", panel, True,
                                   query_fn=lambda *args: {"nodes": [node("new/repo", ident=2)]})

    def test_same_day_cannot_overwrite_a_verified_snapshot(self):
        with TemporaryDirectory() as td:
            out = Path(td) / "growth"
            (out / "snapshots").mkdir(parents=True)
            (out / "snapshots" / "2026-11-08.json").write_text("{}")
            with self.assertRaisesRegex(RuntimeError, "refusing overwrite"):
                growth.run(NOW, Path(td), out, "test", query_fn=lambda *args: {})

    def test_never_access_network_without_token(self):
        with self.assertRaisesRegex(ValueError, "GITHUB_TOKEN"):
            growth.graphql("", "query{viewer{login}}")

    def test_ties_for_ranking_are_deterministic(self):
        panel = [
            {"node_id": "gid-1", "database_id": 1, "month": "2026-10"},
            {"node_id": "gid-2", "database_id": 2, "month": "2026-10"},
        ]
        history = [{"collected_at": growth.timestamp(NOW - timedelta(days=1)),
                    "repositories": [{"id": 1, "stars": 90}, {"id": 2, "stars": 90}]}]
        obs = {"gid-2": node("a/two", 2, 100), "gid-1": node("a/one", 1, 100)}
        result = growth.measure(NOW, panel, obs, history)
        self.assertEqual([x["id"] for x in result["top10"]], [1, 2])


if __name__ == "__main__":
    unittest.main()

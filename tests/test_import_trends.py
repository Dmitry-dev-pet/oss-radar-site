"""Strict offline contracts: no network required for fixture normalization."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "scripts" / "import_trends.py"
spec = importlib.util.spec_from_file_location("trends_import", path)
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)
NOW = datetime(2026, 11, 8, 22, 0, tzinfo=timezone.utc)


def payload():
    meta = {"acme/agent": {"license":"MIT"}}
    item = {"name":"acme/agent","rank":1,"description":"Hello",
            "language":"Python","stars":100,"gained":30}
    return {"collectedAt":"2026-11-08T21:00:00Z",
            "lists":{"all:daily":[item],"all:weekly":[dict(item, gained=60)],
                     "all:monthly":[dict(item,gained=150)]},"meta":meta}


class TestImport(unittest.TestCase):
    def test_dated_source_with_attribution_and_no_invented_history(self):
        normalized = imp.normalize(payload(),NOW)
        self.assertEqual(normalized["license"],"CC BY 4.0")
        self.assertEqual(normalized["source"],"GitHub Trending Today")
        self.assertEqual(normalized["lists"]["all:daily"][0]["gained"],30)
        self.assertEqual(normalized["lists"]["all:daily"][0]["license_declared"],"MIT")
        self.assertFalse(any("history" in x for x in normalized["lists"]["all:daily"][0]))

    def test_duplicate_names_and_nongithub_names_not_published(self):
        p=payload()
        p["lists"]["all:daily"].extend([
            dict(p["lists"]["all:daily"][0],rank=2),
            dict(p["lists"]["all:daily"][0],name="../evil",rank=3),
        ])
        self.assertEqual(len(imp.normalize(p,NOW)["lists"]["all:daily"]),1)

    def test_missing_period_or_invalid_counts_fail_closed(self):
        p=payload();del p["lists"]["all:weekly"]
        with self.assertRaisesRegex(ValueError,"missing main"):
            imp.normalize(p,NOW)
        p=payload();p["lists"]["all:daily"][0]["gained"]=-3
        with self.assertRaisesRegex(ValueError,"invalid rank"):
            imp.normalize(p,NOW)

    def test_stale_data_rejected_instead_of_called_current(self):
        p=payload()
        with self.assertRaisesRegex(ValueError,"too old"):
            imp.normalize(p,NOW+timedelta(days=4))

    def test_no_network_in_offline_normalizer(self):
        with self.assertRaisesRegex(ValueError,"schema"):
            imp.normalize({"collectedAt":"2026-11-08T21:00:00Z"},NOW)


if __name__=="__main__":
    unittest.main()

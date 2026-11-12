from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_clone_metrics as metrics

CREATED = "2026-10-31T20:14:10Z"
NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
REPO = "owner/repository"


def traffic(**daily):
    return {"count": sum(daily.values()), "clones": [
        {"timestamp": day + "T00:00:00Z", "count": count}
        for day, count in daily.items()]}


class CloneMetricsTests(unittest.TestCase):
    def test_overlapping_snapshots_replace_counts_and_preserve_expired_history(self):
        first = metrics.merge_history(None, traffic(**{"2026-10-31": 13, "2026-11-01": 12}), REPO, CREATED, NOW)
        second = metrics.merge_history(first, traffic(**{"2026-11-01": 14, "2026-11-02": 7}), REPO, CREATED, NOW)
        repeated = metrics.merge_history(second, traffic(**{"2026-11-01": 14, "2026-11-02": 7}), REPO, CREATED, NOW)
        self.assertEqual(metrics.figures(repeated, NOW.date()), (7, 34, True))
        corrected = metrics.merge_history(repeated, traffic(**{"2026-11-01": 0, "2026-11-02": 7}), REPO, CREATED, NOW)
        self.assertEqual(sum(corrected["daily_clones"].values()), 20)

    def test_week_rolls_over_at_monday_utc(self):
        history = metrics.merge_history(None, traffic(**{"2026-10-31": 13, "2026-11-01": 12, "2026-11-02": 7}), REPO, CREATED, NOW)
        self.assertEqual(metrics.figures(history, date(2026, 11, 1))[0], 25)
        self.assertEqual(metrics.figures(history, date(2026, 11, 2))[0], 7)

    def test_missing_history_does_not_claim_lifetime_or_complete_week(self):
        history = metrics.merge_history(None, traffic(**{"2026-11-04": 2}), REPO, CREATED, NOW)
        self.assertFalse(history["complete_history"])
        self.assertFalse(metrics.figures(history, NOW.date())[2])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            metrics.write_metrics(output, history, NOW.date())
            self.assertIn("Clones tracked", (output / "clones-overall.svg").read_text())
            self.assertIn("partial", (output / "clones-week.svg").read_text())
            ET.parse(output / "clones-overall.svg")
            self.assertEqual(json.loads((output / "history.json").read_text()), history)

    def test_collection_gap_marks_overall_and_affected_week_incomplete(self):
        first = metrics.merge_history(None, traffic(**{"2026-10-31": 13, "2026-11-01": 12}), REPO, CREATED, NOW)
        after_gap = metrics.merge_history(first, traffic(**{"2026-11-04": 2}), REPO, CREATED, NOW)
        self.assertFalse(after_gap["complete_history"])
        self.assertEqual(after_gap["gaps"], [["2026-11-02", "2026-11-03"]])
        self.assertFalse(metrics.figures(after_gap, NOW.date())[2])

    def test_invalid_api_data_and_other_repository_history_are_rejected(self):
        with self.assertRaises(ValueError):
            metrics.merge_history(None, {"count": 5, "clones": []}, REPO, CREATED, NOW)
        with self.assertRaises(ValueError):
            metrics.merge_history(None, traffic(**{"2026-11-05": 1}), REPO, CREATED, NOW)
        history = metrics.merge_history(None, traffic(**{"2026-10-31": 1}), REPO, CREATED, NOW)
        with self.assertRaises(ValueError):
            metrics.merge_history(history, traffic(**{"2026-10-31": 1}), "other/repository", CREATED, NOW)


if __name__ == "__main__":
    unittest.main()

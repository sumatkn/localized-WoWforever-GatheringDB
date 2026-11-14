import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sync_foreverdb import build_database, collect_zone_ids, parse_material, collect_beasts


class ConverterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT / "tests" / "fixture.json").read_text())

    def test_summary_zones(self):
        self.assertEqual(collect_zone_ids(self.fixture["summary"]), {1413: "The Barrens"})

    def test_input_records(self):
        beasts = collect_beasts(self.fixture["zones"][0]["response"])
        self.assertEqual(len(beasts), 2)

    def test_material_does_not_fabricate_counts(self):
        self.assertIsNone(parse_material({"itemId": 2318, "name": "Light Leather"})["observed"])

    def test_creature_and_reverse_index(self):
        zones = [(z["id"], z["name"], z["response"]) for z in self.fixture["zones"]]
        data = build_database(self.fixture["summary"], zones, self.fixture["meta"])
        self.assertEqual(data["stats"]["creatures"], 2)
        self.assertEqual(data["stats"]["materials"], 2)
        self.assertEqual(data["items"]["2318"]["creatures"], [50001, 50002])
        self.assertIsNone(data["creatures"]["50001"]["items"]["2318"]["observed"])
        self.assertEqual(data["creatures"]["50002"]["items"]["2318"]["observed"]["hits"], 29)

    def test_export_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT/"scripts"/"sync_foreverdb.py"),
                "--fixture", str(ROOT/"tests"/"fixture.json"), "--output", tmp], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            lua = (Path(tmp)/"LocalizedGatheringDB"/"Data.lua").read_text()
            self.assertIn("Data from ForeverDB.net", lua)
            self.assertIn("[50001]", lua)
            self.assertIn("[2318]", lua)
            self.assertNotIn("TEST_PRIVATE_KEY", lua)


if __name__ == "__main__":
    unittest.main()
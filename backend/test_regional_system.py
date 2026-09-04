import asyncio
import sys
import unittest

from backend.services.geo_hierarchy import (
    get_all_regions_meta, get_region,
    get_all_sublocations, get_sublocations_for_region,
    get_location, get_location_by_name,
    search_locations, generate_region_grid
)
from backend.services.risk_service import calculate_risk_assessment


class TestRegionalLandslideSystem(unittest.TestCase):

    def test_01_all_regions_present(self):
        regions = get_all_regions_meta()
        self.assertEqual(len(regions), 8)
        region_ids = [r["id"] for r in regions]
        for expected in ["sikkim", "meghalaya", "mizoram", "nagaland", "arunachal_pradesh", "assam", "manipur", "tripura"]:
            self.assertIn(expected, region_ids)

    def test_02_sublocations_lookup(self):
        rimbi = get_location_by_name("Rimbi")
        self.assertIsNotNone(rimbi)
        self.assertEqual(rimbi["name"], "Rimbi")
        self.assertEqual(rimbi["region_id"], "sikkim")
        self.assertAlmostEqual(rimbi["lat"], 27.2025, places=2)
        self.assertAlmostEqual(rimbi["lon"], 88.2114, places=2)

        singlitam = get_location_by_name("Singlitam")
        self.assertIsNotNone(singlitam)
        self.assertEqual(singlitam["region_id"], "sikkim")

        mawlai = get_location_by_name("Mawlai")
        self.assertIsNotNone(mawlai)
        self.assertEqual(mawlai["region_id"], "meghalaya")

        tupul = get_location_by_name("Tupul")
        self.assertIsNotNone(tupul)
        self.assertEqual(tupul["region_id"], "manipur")

    def test_03_search_locations(self):
        res = search_locations("Rimbi")
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["name"], "Rimbi")

        res_gyal = search_locations("Gyalshing")
        self.assertTrue(len(res_gyal) > 0)
        self.assertEqual(res_gyal[0]["name"], "Gyalshing")

    def test_04_grid_generation(self):
        grid = generate_region_grid("sikkim", step_deg=0.22)
        self.assertTrue(len(grid) > 0)
        for cell in grid:
            self.assertIn("cell_id", cell)
            self.assertIn("bounds", cell)
            self.assertEqual(cell["region_id"], "sikkim")

    def test_05_coordinate_specific_risk_differentiation(self):
        async def _run():
            # Test Rimbi
            res_rimbi = await calculate_risk_assessment("Rimbi, Sikkim", 27.2025, 88.2114)
            self.assertEqual(res_rimbi.region, "sikkim")
            self.assertIsNotNone(res_rimbi.risk_score)
            self.assertIn(res_rimbi.risk_level, ["LOW", "MODERATE", "HIGH", "CRITICAL"])
            self.assertGreater(len(res_rimbi.why_explanation), 0)

            # Test Gangtok
            res_gangtok = await calculate_risk_assessment("Gangtok, Sikkim", 27.3389, 88.6065)
            self.assertIsNotNone(res_gangtok.risk_score)

            # Coordinates must remain exact
            self.assertAlmostEqual(res_rimbi.latitude, 27.2025, places=3)
            self.assertAlmostEqual(res_gangtok.latitude, 27.3389, places=3)

            # Test Tupul, Manipur
            res_tupul = await calculate_risk_assessment("Tupul / Noney, Manipur", 24.7083, 93.6333)
            self.assertEqual(res_tupul.region, "manipur")

            print(f"\n[OK] Risk for Rimbi: {res_rimbi.risk_level} ({res_rimbi.risk_score}%) - Slope: {res_rimbi.environmental_data.slope}°")
            print(f"[OK] Risk for Gangtok: {res_gangtok.risk_level} ({res_gangtok.risk_score}%) - Slope: {res_gangtok.environmental_data.slope}°")
            print(f"[OK] Risk for Tupul: {res_tupul.risk_level} ({res_tupul.risk_score}%) - Slope: {res_tupul.environmental_data.slope}°")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()

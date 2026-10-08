"""Tests for deterministic synthetic scenarios and baseline generator."""

import unittest

from ecotwin.categories import WasteCategory
from ecotwin.scenario import ScenarioExecutionResult
from ecotwin.synthetic import (
    SYNTHETIC_ASSUMPTION_NOTICE,
    generate_baseline_scenario,
    generate_synthetic_city_scenario,
)
from ecotwin.units import EnergyUnit, Mass


class TestSyntheticScenarios(unittest.TestCase):
    def test_baseline_scenario_generation(self):
        scenario = generate_baseline_scenario()

        self.assertEqual(scenario.name, "Metropolis_Baseline_2026")
        self.assertEqual(scenario.daily_waste_generation, Mass.tonnes(1000.0))
        self.assertEqual(len(scenario.facilities), 4)

        # Ensure assumptions are clearly documented in metadata
        self.assertTrue(scenario.metadata.get("is_synthetic"))
        self.assertIn("assumptions", scenario.metadata)
        self.assertEqual(scenario.metadata["assumptions"]["notice"], SYNTHETIC_ASSUMPTION_NOTICE)

        # Run simulation
        result = scenario.run(energy_output_unit=EnergyUnit.MWH)

        self.assertIsInstance(result, ScenarioExecutionResult)
        self.assertEqual(result.total_waste_processed, Mass.tonnes(1000.0))

        # Expected mass breakdown for 1000 t:
        # AD: 450 t (cap: 500) -> Mat: 202.5 t (45%), Landfill: 45 t (10%), Loss: 202.5 t (45%), Energy: 450 * 320 * 0.38 = 54720 kWh = 54.72 MWh
        # MRF: 250 t (cap: 300) -> Mat: 205.0 t (82%), Landfill: 45 t (18%), Loss: 0 t, Energy: 0 MWh
        # EWaste: 50 t (cap: 65) -> Mat: 36.0 t (72%), Landfill: 14 t (28%), Loss: 0 t, Energy: 0 MWh
        # WTE: 250 t (cap: 300) -> Mat: 30.0 t (12%), Landfill: 45 t (18%), Loss: 175.0 t (70%), Energy: 250 * 2400 * 0.25 = 150000 kWh = 150.0 MWh

        # Total Mat: 202.5 + 205.0 + 36.0 + 30.0 = 473.5 t (47.35%)
        # Total Landfill: 45.0 + 45.0 + 14.0 + 45.0 = 149.0 t (14.90%)
        # Total Process Loss: 202.5 + 0 + 0 + 175.0 = 377.5 t (37.75%)
        # Total Output Mass: 473.5 + 149.0 + 377.5 = 1000.0 t
        # Total Energy: 54.72 + 150.0 = 204.72 MWh

        self.assertAlmostEqual(result.total_material_recovered.to_tonnes().value, 473.5)
        self.assertAlmostEqual(result.total_landfill_residue.to_tonnes().value, 149.0)
        self.assertAlmostEqual(result.total_process_loss.to_tonnes().value, 377.5)
        self.assertAlmostEqual(result.total_energy_recovered.to_mwh().value, 204.72)

        # Recovery & diversion rates
        self.assertAlmostEqual(result.material_recovery_rate, 0.4735)
        self.assertAlmostEqual(result.landfill_diversion_rate, 0.8510)

        # Facility utilizations
        self.assertAlmostEqual(result.facility_utilizations["Anaerobic_Digestion_Plant"], 450.0 / 500.0)  # 90.0%
        self.assertAlmostEqual(result.facility_utilizations["Materials_Recovery_Facility"], 250.0 / 300.0) # 83.33%
        self.assertAlmostEqual(result.facility_utilizations["E_Waste_Refurbishment_Hub"], 50.0 / 65.0)     # 76.92%
        self.assertAlmostEqual(result.facility_utilizations["Waste_to_Energy_Plant"], 250.0 / 300.0)       # 83.33%

        # Mass balance closure
        self.assertAlmostEqual(result.mass_balance_error_kg, 0.0, places=5)

    def test_reproducibility_determinism(self):
        """Verify that multiple generations and runs produce identical bitwise deterministic results."""
        run1 = generate_baseline_scenario().run()
        run2 = generate_baseline_scenario().run()

        self.assertEqual(run1.total_waste_processed, run2.total_waste_processed)
        self.assertEqual(run1.total_material_recovered, run2.total_material_recovered)
        self.assertEqual(run1.total_landfill_residue, run2.total_landfill_residue)
        self.assertEqual(run1.total_process_loss, run2.total_process_loss)
        self.assertEqual(run1.total_energy_recovered, run2.total_energy_recovered)
        self.assertEqual(run1.facility_utilizations, run2.facility_utilizations)
        self.assertEqual(run1.mass_balance_error_kg, run2.mass_balance_error_kg)

    def test_synthetic_presets(self):
        high_div = generate_synthetic_city_scenario(preset="high_diversion")
        self.assertEqual(high_div.daily_waste_generation, Mass.tonnes(800.0))
        res_hd = high_div.run()
        self.assertGreater(res_hd.landfill_diversion_rate, 0.85)

        district = generate_synthetic_city_scenario(preset="eco_district")
        self.assertEqual(district.daily_waste_generation, Mass.tonnes(200.0))
        res_dist = district.run()
        self.assertEqual(res_dist.total_waste_processed, Mass.tonnes(200.0))

        with self.assertRaises(ValueError):
            generate_synthetic_city_scenario(preset="unknown_preset_123")


if __name__ == "__main__":
    unittest.main()

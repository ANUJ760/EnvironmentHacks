"""Integration tests for complete EcoTwin mass & energy balance engine."""

import unittest
from ecotwin.balance import EcoTwinEngine
from ecotwin.categories import WasteCategory
from ecotwin.exceptions import CapacityExceededError
from ecotwin.facility import CategoryProcessingProfile, ProcessingFacility
from ecotwin.routing import RoutingPlan
from ecotwin.stream import WasteStream
from ecotwin.units import EnergyUnit, Mass, SpecificEnergy


class TestBalanceEngine(unittest.TestCase):
    def setUp(self):
        self.compost_fac = ProcessingFacility(
            name="Compost_Plant",
            capacity=Mass.tonnes(300.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.50,
                landfill_residue_rate=0.10,
                process_loss_rate=0.40,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(150.0),
                energy_efficiency=0.40,
            ),
        )

        self.mrf_fac = ProcessingFacility(
            name="MRF",
            capacity=Mass.tonnes(200.0),
            accepted_categories={WasteCategory.RECYCLABLE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.85,
                landfill_residue_rate=0.15,
                process_loss_rate=0.00,
            ),
        )

        self.ewaste_fac = ProcessingFacility(
            name="EWaste_Hub",
            capacity=Mass.tonnes(50.0),
            accepted_categories={WasteCategory.E_WASTE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.75,
                landfill_residue_rate=0.25,
                process_loss_rate=0.00,
            ),
        )

        self.wte_fac = ProcessingFacility(
            name="WTE_Plant",
            capacity=Mass.tonnes(250.0),
            accepted_categories={WasteCategory.RESIDUAL},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.10,
                landfill_residue_rate=0.20,
                process_loss_rate=0.70,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(2000.0),
                energy_efficiency=0.30,
            ),
        )

        self.engine = EcoTwinEngine([self.compost_fac, self.mrf_fac, self.ewaste_fac, self.wte_fac])
        self.routing = RoutingPlan.create_direct({
            WasteCategory.ORGANIC: "Compost_Plant",
            WasteCategory.RECYCLABLE: "MRF",
            WasteCategory.E_WASTE: "EWaste_Hub",
            WasteCategory.RESIDUAL: "WTE_Plant",
        })

    def test_full_system_mass_energy_balance(self):
        stream = WasteStream.create(
            mass=Mass.tonnes(400.0),
            composition={
                WasteCategory.ORGANIC: 0.40,     # 160 t
                WasteCategory.RECYCLABLE: 0.30,  # 120 t
                WasteCategory.E_WASTE: 0.05,     # 20 t
                WasteCategory.RESIDUAL: 0.25,    # 100 t
            },
        )

        result = self.engine.simulate(stream, self.routing, energy_output_unit=EnergyUnit.MWH)

        # Expected mass calculations:
        # Compost: 160 t -> Mat: 80 t, Landfill: 16 t, Loss: 64 t, Energy: 160 * 150 * 0.4 = 9600 kWh = 9.6 MWh
        # MRF: 120 t -> Mat: 102 t, Landfill: 18 t, Loss: 0 t, Energy: 0 MWh
        # EWaste: 20 t -> Mat: 15 t, Landfill: 5 t, Loss: 0 t, Energy: 0 MWh
        # WTE: 100 t -> Mat: 10 t, Landfill: 20 t, Loss: 70 t, Energy: 100 * 2000 * 0.3 = 60000 kWh = 60.0 MWh

        # Total Mat = 80 + 102 + 15 + 10 = 207 t
        # Total Landfill = 16 + 18 + 5 + 20 = 59 t
        # Total Loss = 64 + 0 + 0 + 70 = 134 t
        # Total Sum Out = 207 + 59 + 134 = 400 t
        # Total Energy = 9.6 + 60.0 = 69.6 MWh

        self.assertAlmostEqual(result.total_material_recovered.to_tonnes().value, 207.0)
        self.assertAlmostEqual(result.total_landfill_residue.to_tonnes().value, 59.0)
        self.assertAlmostEqual(result.total_process_loss.to_tonnes().value, 134.0)
        self.assertAlmostEqual(result.total_energy_recovered.to_mwh().value, 69.6)

        # Recovery rate: 207 / 400 = 51.75%
        self.assertAlmostEqual(result.material_recovery_rate, 207.0 / 400.0)
        # Landfill diversion rate: 1 - (59 / 400) = 85.25%
        self.assertAlmostEqual(result.landfill_diversion_rate, 1.0 - (59.0 / 400.0))

        # Check summary dict
        summary = result.summary()
        self.assertIn("material_recovery_rate_pct", summary)
        self.assertEqual(summary["material_recovery_rate_pct"], 51.75)

    def test_system_capacity_overload(self):
        # E-waste exceeds 50 tonnes capacity
        overload_stream = WasteStream.create(
            mass=Mass.tonnes(200.0),
            composition={
                WasteCategory.ORGANIC: 0.20,
                WasteCategory.RECYCLABLE: 0.20,
                WasteCategory.E_WASTE: 0.40,  # 80 tonnes > 50 tonnes capacity
                WasteCategory.RESIDUAL: 0.20,
            },
        )

        with self.assertRaises(CapacityExceededError):
            self.engine.simulate(overload_stream, self.routing)


if __name__ == "__main__":
    unittest.main()

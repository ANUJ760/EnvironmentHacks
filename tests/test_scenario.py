"""Unit and integration tests for EcoTwin scenario data layer and validation."""

import unittest

from ecotwin.categories import WasteCategory
from ecotwin.exceptions import (
    CapacityExceededError,
    InvalidCompositionError,
    InvalidRoutingError,
    ScenarioValidationError,
)
from ecotwin.facility import CategoryProcessingProfile, ProcessingFacility
from ecotwin.routing import RouteSplit, RoutingPlan
from ecotwin.scenario import Scenario, ScenarioExecutionResult, UrbanScenario
from ecotwin.units import EnergyUnit, Mass, SpecificEnergy


class TestUrbanScenarioValidation(unittest.TestCase):
    def setUp(self):
        self.facility_org = ProcessingFacility(
            name="Organics_Plant",
            capacity=Mass.tonnes(200.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.50,
                landfill_residue_rate=0.10,
                process_loss_rate=0.40,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(200.0),
                energy_efficiency=0.35,
            ),
        )
        self.facility_rec = ProcessingFacility(
            name="Recycling_Plant",
            capacity=Mass.tonnes(150.0),
            accepted_categories={WasteCategory.RECYCLABLE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.85,
                landfill_residue_rate=0.15,
                process_loss_rate=0.00,
            ),
        )
        self.facility_res = ProcessingFacility(
            name="Residual_Plant",
            capacity=Mass.tonnes(200.0),
            accepted_categories={WasteCategory.RESIDUAL, WasteCategory.E_WASTE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.10,
                landfill_residue_rate=0.20,
                process_loss_rate=0.70,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(2000.0),
                energy_efficiency=0.25,
            ),
        )

        self.facilities = [self.facility_org, self.facility_rec, self.facility_res]
        self.routing = {
            WasteCategory.ORGANIC: "Organics_Plant",
            WasteCategory.RECYCLABLE: "Recycling_Plant",
            WasteCategory.E_WASTE: "Residual_Plant",
            WasteCategory.RESIDUAL: "Residual_Plant",
        }

    def test_valid_scenario_creation_and_properties(self):
        scenario = UrbanScenario.create(
            name="Test_Valid_Scenario",
            daily_waste_generation=Mass.tonnes(300.0),
            composition={
                WasteCategory.ORGANIC: 0.50,     # 150 tonnes -> Organics_Plant (cap: 200 t)
                WasteCategory.RECYCLABLE: 0.30,  # 90 tonnes -> Recycling_Plant (cap: 150 t)
                WasteCategory.E_WASTE: 0.05,     # 15 tonnes -> Residual_Plant (cap: 200 t)
                WasteCategory.RESIDUAL: 0.15,    # 45 tonnes -> Residual_Plant (total 60 t)
            },
            facilities=self.facilities,
            routing_plan=self.routing,
            metadata={"city": "Synthetic Test City"},
            description="A valid test scenario",
        )

        self.assertEqual(scenario.name, "Test_Valid_Scenario")
        self.assertEqual(scenario.daily_waste_generation, Mass.tonnes(300.0))
        self.assertEqual(len(scenario.facilities), 3)

        # Facility loads calculation
        loads = scenario.calculate_facility_loads()
        self.assertAlmostEqual(loads["Organics_Plant"].to_tonnes().value, 150.0)
        self.assertAlmostEqual(loads["Recycling_Plant"].to_tonnes().value, 90.0)
        self.assertAlmostEqual(loads["Residual_Plant"].to_tonnes().value, 60.0)

        # Facility utilization calculation
        utilizations = scenario.calculate_facility_utilizations()
        self.assertAlmostEqual(utilizations["Organics_Plant"], 150.0 / 200.0)  # 75%
        self.assertAlmostEqual(utilizations["Recycling_Plant"], 90.0 / 150.0)  # 60%
        self.assertAlmostEqual(utilizations["Residual_Plant"], 60.0 / 200.0)   # 30%

    def test_invalid_composition_sum_fails(self):
        with self.assertRaises(InvalidCompositionError):
            UrbanScenario.create(
                name="Bad_Composition_Sum",
                daily_waste_generation=Mass.tonnes(100.0),
                composition={
                    WasteCategory.ORGANIC: 0.40,
                    WasteCategory.RECYCLABLE: 0.40,
                    WasteCategory.RESIDUAL: 0.10,  # Sum = 0.90 != 1.0
                },
                facilities=self.facilities,
                routing_plan=self.routing,
            )

    def test_negative_composition_fraction_fails(self):
        with self.assertRaises(InvalidCompositionError):
            UrbanScenario.create(
                name="Negative_Fraction",
                daily_waste_generation=Mass.tonnes(100.0),
                composition={
                    WasteCategory.ORGANIC: 0.80,
                    WasteCategory.RECYCLABLE: -0.10,
                    WasteCategory.RESIDUAL: 0.30,
                },
                facilities=self.facilities,
                routing_plan=self.routing,
            )

    def test_missing_route_for_active_category_fails(self):
        with self.assertRaises(InvalidRoutingError):
            UrbanScenario.create(
                name="Missing_Route",
                daily_waste_generation=Mass.tonnes(100.0),
                composition={
                    WasteCategory.ORGANIC: 0.50,
                    WasteCategory.RECYCLABLE: 0.50,
                },
                facilities=self.facilities,
                routing_plan={
                    WasteCategory.ORGANIC: "Organics_Plant",
                    # Missing RECYCLABLE
                },
            )

    def test_route_to_unknown_facility_fails(self):
        with self.assertRaises(InvalidRoutingError):
            UrbanScenario.create(
                name="Unknown_Facility_Route",
                daily_waste_generation=Mass.tonnes(100.0),
                composition={
                    WasteCategory.ORGANIC: 0.50,
                    WasteCategory.RECYCLABLE: 0.50,
                },
                facilities=self.facilities,
                routing_plan={
                    WasteCategory.ORGANIC: "Non_Existent_Facility",
                    WasteCategory.RECYCLABLE: "Recycling_Plant",
                },
            )

    def test_route_to_incompatible_facility_category_fails(self):
        # Recycling_Plant only accepts RECYCLABLE, route ORGANIC there
        with self.assertRaises(InvalidRoutingError):
            UrbanScenario.create(
                name="Incompatible_Category_Route",
                daily_waste_generation=Mass.tonnes(100.0),
                composition={
                    WasteCategory.ORGANIC: 0.50,
                    WasteCategory.RECYCLABLE: 0.50,
                },
                facilities=self.facilities,
                routing_plan={
                    WasteCategory.ORGANIC: "Recycling_Plant",  # Incompatible!
                    WasteCategory.RECYCLABLE: "Recycling_Plant",
                },
            )

    def test_facility_capacity_exceeded_fails(self):
        # Organics_Plant has capacity 200 tonnes, route 250 tonnes there
        with self.assertRaises(CapacityExceededError):
            UrbanScenario.create(
                name="Capacity_Exceeded",
                daily_waste_generation=Mass.tonnes(500.0),
                composition={
                    WasteCategory.ORGANIC: 0.50,     # 250 tonnes > 200 tonnes capacity
                    WasteCategory.RECYCLABLE: 0.20,
                    WasteCategory.RESIDUAL: 0.30,
                },
                facilities=self.facilities,
                routing_plan=self.routing,
            )

    def test_scenario_validation_empty_name_or_facilities(self):
        with self.assertRaises(ScenarioValidationError):
            UrbanScenario.create(
                name="",
                daily_waste_generation=Mass.tonnes(100.0),
                composition={WasteCategory.ORGANIC: 1.0},
                facilities=self.facilities,
                routing_plan={WasteCategory.ORGANIC: "Organics_Plant"},
            )

        with self.assertRaises(ScenarioValidationError):
            UrbanScenario.create(
                name="Empty_Facilities",
                daily_waste_generation=Mass.tonnes(100.0),
                composition={WasteCategory.ORGANIC: 1.0},
                facilities=[],
                routing_plan={WasteCategory.ORGANIC: "Organics_Plant"},
            )


class TestScenarioExecution(unittest.TestCase):
    def test_run_scenario_produces_structured_result(self):
        ad_facility = ProcessingFacility(
            name="Anaerobic_Plant",
            capacity=Mass.tonnes(300.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.40,
                landfill_residue_rate=0.10,
                process_loss_rate=0.50,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(300.0),
                energy_efficiency=0.40,
            ),
        )
        mrf_facility = ProcessingFacility(
            name="MRF_Plant",
            capacity=Mass.tonnes(200.0),
            accepted_categories={WasteCategory.RECYCLABLE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.80,
                landfill_residue_rate=0.20,
                process_loss_rate=0.00,
            ),
        )

        scenario = Scenario.create(
            name="Test_Run_Scenario",
            daily_waste_generation=Mass.tonnes(200.0),
            composition={
                WasteCategory.ORGANIC: 0.60,     # 120 tonnes
                WasteCategory.RECYCLABLE: 0.40,  # 80 tonnes
            },
            facilities=[ad_facility, mrf_facility],
            routing_plan={
                WasteCategory.ORGANIC: "Anaerobic_Plant",
                WasteCategory.RECYCLABLE: "MRF_Plant",
            },
            metadata={"experiment": "Phase 2 baseline"},
        )

        result = scenario.run(energy_output_unit=EnergyUnit.MWH)

        self.assertIsInstance(result, ScenarioExecutionResult)
        self.assertEqual(result.scenario_name, "Test_Run_Scenario")
        self.assertEqual(result.total_waste_processed, Mass.tonnes(200.0))

        # Expected mass:
        # AD: 120 t -> Mat: 48 t, Landfill: 12 t, Loss: 60 t, Energy: 120 * 300 * 0.4 = 14400 kWh = 14.4 MWh
        # MRF: 80 t -> Mat: 64 t, Landfill: 16 t, Loss: 0 t, Energy: 0 MWh
        # Total Mat: 48 + 64 = 112 t
        # Total Landfill: 12 + 16 = 28 t
        # Total Loss: 60 + 0 = 60 t
        # Sum out: 112 + 28 + 60 = 200 t

        self.assertAlmostEqual(result.total_material_recovered.to_tonnes().value, 112.0)
        self.assertAlmostEqual(result.total_landfill_residue.to_tonnes().value, 28.0)
        self.assertAlmostEqual(result.total_process_loss.to_tonnes().value, 60.0)
        self.assertAlmostEqual(result.total_energy_recovered.to_mwh().value, 14.4)

        # Performance metrics
        self.assertAlmostEqual(result.material_recovery_rate, 112.0 / 200.0)  # 56.0%
        self.assertAlmostEqual(result.landfill_diversion_rate, 1.0 - (28.0 / 200.0))  # 86.0%

        # Facility utilizations
        self.assertAlmostEqual(result.facility_utilizations["Anaerobic_Plant"], 120.0 / 300.0)  # 40%
        self.assertAlmostEqual(result.facility_utilizations["MRF_Plant"], 80.0 / 200.0)         # 40%

        # Mass balance closure
        self.assertAlmostEqual(result.mass_balance_error_kg, 0.0, places=5)
        self.assertAlmostEqual(result.mass_balance_error.to_kg().value, 0.0, places=5)

        # Summary and report verification
        summary = result.summary()
        self.assertEqual(summary["metrics"]["material_recovery_rate_pct"], 56.0)
        self.assertEqual(summary["metrics"]["landfill_diversion_rate_pct"], 86.0)
        self.assertEqual(summary["facility_utilization_pct"]["Anaerobic_Plant"], 40.0)

        report = result.format_report()
        self.assertIn("EcoTwin Scenario Execution Report: Test_Run_Scenario", report)
        self.assertIn("Mass Balance Closure Error", report)


if __name__ == "__main__":
    unittest.main()

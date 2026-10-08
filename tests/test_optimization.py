"""Unit and integration tests for Phase 4 waste-routing optimization layer."""

import unittest

from ecotwin.categories import WasteCategory
from ecotwin.facility import CategoryProcessingProfile, ProcessingFacility
from ecotwin.optimization import (
    LinearProgramSolver,
    OptimizationResult,
    OptimizationWeights,
    WasteRoutingOptimizer,
    optimize_scenario_routing,
)
from ecotwin.routing import RoutingPlan
from ecotwin.scenario import ScenarioExecutionResult, UrbanScenario
from ecotwin.synthetic import generate_baseline_scenario
from ecotwin.units import EnergyUnit, Mass, SpecificEnergy


class TestLinearProgramSolver(unittest.TestCase):
    def test_solve_simple_linear_program(self):
        # Maximize 3*x1 + 2*x2
        # Subject to:
        #   x1 + x2 <= 4
        #   2*x1 + x2 <= 5
        #   x1, x2 >= 0
        # Optimal solution: x1 = 1, x2 = 3, Max obj = 9
        c = [3.0, 2.0]
        A_ub = [
            [1.0, 1.0],
            [2.0, 1.0],
        ]
        b_ub = [4.0, 5.0]
        A_eq = []
        b_eq = []

        status, sol, obj_val = LinearProgramSolver.solve_lp(c, A_ub, b_ub, A_eq, b_eq)
        self.assertEqual(status, "OPTIMAL")
        self.assertIsNotNone(sol)
        self.assertAlmostEqual(sol[0], 1.0, places=4)
        self.assertAlmostEqual(sol[1], 3.0, places=4)
        self.assertAlmostEqual(obj_val, 9.0, places=4)


class TestWasteRoutingOptimization(unittest.TestCase):
    def setUp(self):
        # Create an urban system with routing trade-offs:
        # Facility A: High-efficiency Composting (70% material recovery, 10% landfill, 20% loss, 0 energy)
        # Facility B: Biogas / AD Plant (40% material recovery, 10% landfill, 50% loss, high energy 350 kWh/t)
        # Facility C: MRF for recyclables (85% recovery, 15% landfill)
        # Facility D: Incinerator for residual & overflow (10% recovery, 20% landfill, 70% loss, 2200 kWh/t)

        self.compost = ProcessingFacility(
            name="Compost_Plant",
            capacity=Mass.tonnes(300.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.70,
                landfill_residue_rate=0.10,
                process_loss_rate=0.20,
            ),
        )

        self.biogas = ProcessingFacility(
            name="Biogas_Plant",
            capacity=Mass.tonnes(300.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.40,
                landfill_residue_rate=0.10,
                process_loss_rate=0.50,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(350.0),
                energy_efficiency=0.40,
            ),
        )

        self.mrf = ProcessingFacility(
            name="MRF",
            capacity=Mass.tonnes(300.0),
            accepted_categories={WasteCategory.RECYCLABLE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.85,
                landfill_residue_rate=0.15,
                process_loss_rate=0.00,
            ),
        )

        self.wte = ProcessingFacility(
            name="WTE_Plant",
            capacity=Mass.tonnes(400.0),
            accepted_categories={WasteCategory.RESIDUAL, WasteCategory.E_WASTE, WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.10,
                landfill_residue_rate=0.20,
                process_loss_rate=0.70,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(2200.0),
                energy_efficiency=0.25,
            ),
        )

        self.facilities = [self.compost, self.biogas, self.mrf, self.wte]

        # Inefficient sub-optimal baseline routing:
        # Sends organics to WTE instead of Compost/Biogas!
        self.baseline_scenario = UrbanScenario.create(
            name="Tradeoff_City_Baseline",
            daily_waste_generation=Mass.tonnes(500.0),
            composition={
                WasteCategory.ORGANIC: 0.40,     # 200 tonnes
                WasteCategory.RECYCLABLE: 0.30,  # 150 tonnes
                WasteCategory.E_WASTE: 0.05,     # 25 tonnes
                WasteCategory.RESIDUAL: 0.25,    # 125 tonnes
            },
            facilities=self.facilities,
            routing_plan=RoutingPlan.create_direct({
                WasteCategory.ORGANIC: "WTE_Plant",  # Sub-optimal routing
                WasteCategory.RECYCLABLE: "MRF",
                WasteCategory.E_WASTE: "WTE_Plant",
                WasteCategory.RESIDUAL: "WTE_Plant",
            }),
        )

    def test_optimizer_improves_material_recovery(self):
        # Weight heavily towards material recovery
        weights = OptimizationWeights(
            material_recovery_weight=2.0,
            landfill_penalty_weight=1.0,
            energy_recovery_weight=0.0,
        )

        opt_res = optimize_scenario_routing(self.baseline_scenario, weights=weights)

        self.assertEqual(opt_res.status, "OPTIMAL")
        self.assertGreater(opt_res.optimized_score, opt_res.baseline_score)
        self.assertGreater(
            opt_res.optimized_execution.total_material_recovered.to_tonnes().value,
            opt_res.baseline_execution.total_material_recovered.to_tonnes().value,
        )

        # In material-focused optimization, organics should be routed to Compost_Plant (70% recovery)
        org_splits = opt_res.optimized_routing.routes[WasteCategory.ORGANIC]
        compost_routed = sum(s.fraction for s in org_splits if s.facility_name == "Compost_Plant")
        self.assertAlmostEqual(compost_routed, 1.0, places=4)

    def test_routing_fractions_and_mass_conservation(self):
        opt_res = optimize_scenario_routing(self.baseline_scenario)

        # Check routing plan invariants
        for cat, splits in opt_res.optimized_routing.routes.items():
            split_sum = sum(s.fraction for s in splits)
            self.assertAlmostEqual(split_sum, 1.0, places=5)
            for s in splits:
                self.assertGreaterEqual(s.fraction, 0.0)
                self.assertLessEqual(s.fraction, 1.0)
                # Check category compatibility
                fac = self.baseline_scenario.facilities[s.facility_name]
                self.assertTrue(fac.is_category_accepted(cat))

        # Check that physical mass balance holds strictly on optimized result
        self.assertAlmostEqual(opt_res.optimized_execution.mass_balance_error_kg, 0.0, places=5)

    def test_facility_capacity_constraints_respected(self):
        # Scenario where Organics exceeds Compost_Plant capacity (300 t), requiring split to Biogas_Plant
        overload_scenario = UrbanScenario.create(
            name="Large_Organics_Scenario",
            daily_waste_generation=Mass.tonnes(800.0),
            composition={
                WasteCategory.ORGANIC: 0.50,     # 400 tonnes > 300 t capacity of Compost_Plant
                WasteCategory.RECYCLABLE: 0.25,  # 200 tonnes -> MRF (cap 300)
                WasteCategory.E_WASTE: 0.05,     # 40 tonnes -> WTE (cap 400)
                WasteCategory.RESIDUAL: 0.20,    # 160 tonnes -> WTE (total WTE = 200 t)
            },
            facilities=self.facilities,
            routing_plan=RoutingPlan.create({
                WasteCategory.ORGANIC: [("Compost_Plant", 0.5), ("Biogas_Plant", 0.5)], # 200 t each
                WasteCategory.RECYCLABLE: [("MRF", 1.0)],
                WasteCategory.E_WASTE: [("WTE_Plant", 1.0)],
                WasteCategory.RESIDUAL: [("WTE_Plant", 1.0)],
            }),
        )

        weights = OptimizationWeights(
            material_recovery_weight=2.0,
            landfill_penalty_weight=1.0,
            energy_recovery_weight=0.5,
        )

        opt_res = optimize_scenario_routing(overload_scenario, weights=weights)
        self.assertEqual(opt_res.status, "OPTIMAL")

        # Compost_Plant cannot receive more than 300 tonnes
        loads = opt_res.optimized_scenario.calculate_facility_loads()
        for fac_name, load in loads.items():
            cap = overload_scenario.facilities[fac_name].capacity
            self.assertLessEqual(load.to_tonnes().value, cap.to_tonnes().value + 1e-4)

    def test_reproducibility(self):
        res1 = optimize_scenario_routing(self.baseline_scenario)
        res2 = optimize_scenario_routing(self.baseline_scenario)

        self.assertEqual(res1.status, res2.status)
        self.assertAlmostEqual(res1.optimized_score, res2.optimized_score, places=6)
        self.assertEqual(res1.optimized_routing, res2.optimized_routing)


if __name__ == "__main__":
    unittest.main()

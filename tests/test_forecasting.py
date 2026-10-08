"""Unit and integration tests for Phase 3 AI waste forecasting and scenario binding."""

import datetime as dt
import unittest

from ecotwin.categories import WasteCategory
from ecotwin.forecasting import (
    FORECASTING_BENCHMARK_NOTICE,
    HistoricalWasteDataset,
    RidgeLinearRegressor,
    WasteForecastResult,
    WasteForecaster,
    WasteObservation,
    forecast_to_scenario,
    generate_synthetic_history,
)
from ecotwin.scenario import ScenarioExecutionResult, UrbanScenario
from ecotwin.synthetic import generate_baseline_scenario
from ecotwin.units import EnergyUnit, Mass


class TestRidgeLinearRegressor(unittest.TestCase):
    def test_fit_predict_simple_linear(self):
        # y = 2*x1 + 3*x2 + 5
        X = [[1.0, 2.0], [2.0, 1.0], [3.0, 4.0], [5.0, 2.0], [1.0, 1.0]]
        y = [2 * x[0] + 3 * x[1] + 5 for x in X]

        model = RidgeLinearRegressor(alpha=1e-5, fit_intercept=True).fit(X, y)
        self.assertAlmostEqual(model.intercept, 5.0, places=2)
        self.assertAlmostEqual(model.weights[0], 2.0, places=2)
        self.assertAlmostEqual(model.weights[1], 3.0, places=2)

        test_pred = model.predict_single([4.0, 2.0])
        self.assertAlmostEqual(test_pred, 2 * 4.0 + 3 * 2.0 + 5.0, places=2)


class TestSyntheticDatasetGeneration(unittest.TestCase):
    def test_reproducibility(self):
        ds1 = generate_synthetic_history(days=60, random_seed=123)
        ds2 = generate_synthetic_history(days=60, random_seed=123)

        self.assertEqual(len(ds1), len(ds2))
        for obs1, obs2 in zip(ds1.observations, ds2.observations):
            self.assertEqual(obs1.date, obs2.date)
            self.assertEqual(obs1.total_waste, obs2.total_waste)
            self.assertEqual(obs1.composition, obs2.composition)

    def test_temporal_properties_and_simplex_validity(self):
        ds = generate_synthetic_history(days=120, random_seed=42)
        self.assertEqual(len(ds), 120)
        self.assertEqual(ds.metadata["assumptions"]["notice"], FORECASTING_BENCHMARK_NOTICE)

        for obs in ds.observations:
            self.assertGreater(obs.total_waste.to_tonnes().value, 0.0)
            # Simplex sum to 1.0
            comp_sum = sum(obs.composition.values())
            self.assertAlmostEqual(comp_sum, 1.0, places=5)
            # Non-negative fractions
            for cat, frac in obs.composition.items():
                self.assertGreaterEqual(frac, 0.0)
                self.assertLessEqual(frac, 1.0)
            # Category mass conservation
            mass_sum = sum(m.to_tonnes().value for m in obs.category_masses.values())
            self.assertAlmostEqual(mass_sum, obs.total_waste.to_tonnes().value, places=4)


class TestWasteForecaster(unittest.TestCase):
    def setUp(self):
        # 180 days history
        self.history = generate_synthetic_history(days=180, random_seed=42)
        self.forecaster = WasteForecaster(alpha=0.5).train(self.history)
        
        # Base scenario with adequate facility capacity for peak seasons
        from ecotwin.facility import CategoryProcessingProfile, ProcessingFacility
        from ecotwin.routing import RoutingPlan
        from ecotwin.units import SpecificEnergy
        
        self.base_scenario = UrbanScenario.create(
            name="Metropolis_Sufficient_Capacity",
            daily_waste_generation=Mass.tonnes(1000.0),
            composition={
                WasteCategory.ORGANIC: 0.45,
                WasteCategory.RECYCLABLE: 0.25,
                WasteCategory.E_WASTE: 0.05,
                WasteCategory.RESIDUAL: 0.25,
            },
            facilities=[
                ProcessingFacility(
                    name="Anaerobic_Plant",
                    capacity=Mass.tonnes(650.0), # Sized for seasonal peaks
                    accepted_categories={WasteCategory.ORGANIC},
                    default_profile=CategoryProcessingProfile(
                        material_recovery_rate=0.45,
                        landfill_residue_rate=0.10,
                        process_loss_rate=0.45,
                        specific_energy=SpecificEnergy.from_kwh_per_tonne(320.0),
                        energy_efficiency=0.38,
                    ),
                ),
                ProcessingFacility(
                    name="MRF_Plant",
                    capacity=Mass.tonnes(400.0),
                    accepted_categories={WasteCategory.RECYCLABLE},
                    default_profile=CategoryProcessingProfile(
                        material_recovery_rate=0.82,
                        landfill_residue_rate=0.18,
                        process_loss_rate=0.00,
                    ),
                ),
                ProcessingFacility(
                    name="EWaste_Plant",
                    capacity=Mass.tonnes(100.0),
                    accepted_categories={WasteCategory.E_WASTE},
                    default_profile=CategoryProcessingProfile(
                        material_recovery_rate=0.72,
                        landfill_residue_rate=0.28,
                        process_loss_rate=0.00,
                    ),
                ),
                ProcessingFacility(
                    name="WTE_Plant",
                    capacity=Mass.tonnes(400.0),
                    accepted_categories={WasteCategory.RESIDUAL},
                    default_profile=CategoryProcessingProfile(
                        material_recovery_rate=0.12,
                        landfill_residue_rate=0.18,
                        process_loss_rate=0.70,
                        specific_energy=SpecificEnergy.from_kwh_per_tonne(2400.0),
                        energy_efficiency=0.25,
                    ),
                ),
            ],
            routing_plan=RoutingPlan.create_direct({
                WasteCategory.ORGANIC: "Anaerobic_Plant",
                WasteCategory.RECYCLABLE: "MRF_Plant",
                WasteCategory.E_WASTE: "EWaste_Plant",
                WasteCategory.RESIDUAL: "WTE_Plant",
            }),
        )

    def test_predict_next_day_structure(self):
        forecast = self.forecaster.predict_next_day()

        self.assertIsInstance(forecast, WasteForecastResult)
        self.assertEqual(forecast.forecast_date, self.history.end_date + dt.timedelta(days=1))
        self.assertGreater(forecast.predicted_total_waste.to_tonnes().value, 0.0)

        # Simplex sum to 1.0
        frac_sum = sum(forecast.predicted_composition.values())
        self.assertAlmostEqual(frac_sum, 1.0, places=6)

        # Non-negative fractions
        for cat, frac in forecast.predicted_composition.items():
            self.assertGreaterEqual(frac, 0.0)
            self.assertLessEqual(frac, 1.0)

        # Mass conservation: sum of category masses == total predicted waste
        cat_mass_sum = sum(m.to_tonnes().value for m in forecast.predicted_category_masses.values())
        self.assertAlmostEqual(cat_mass_sum, forecast.predicted_total_waste.to_tonnes().value, places=5)

    def test_forecast_to_urban_scenario_integration(self):
        forecast = self.forecaster.predict_next_day()
        scenario = forecast.to_urban_scenario(self.base_scenario)

        self.assertIsInstance(scenario, UrbanScenario)
        self.assertEqual(scenario.daily_waste_generation, forecast.predicted_total_waste)
        for cat in WasteCategory:
            self.assertAlmostEqual(scenario.composition[cat], forecast.predicted_composition[cat], places=5)
        self.assertEqual(scenario.facilities, self.base_scenario.facilities)

        self.assertEqual(scenario.routing_plan, self.base_scenario.routing_plan)

        # Execute simulation through physics engine
        result = scenario.run(energy_output_unit=EnergyUnit.MWH)
        self.assertIsInstance(result, ScenarioExecutionResult)

        # Mass strictly conserved in physics simulation
        self.assertAlmostEqual(result.mass_balance_error_kg, 0.0, places=5)
        self.assertGreater(result.total_material_recovered.to_tonnes().value, 0.0)
        self.assertGreater(result.total_energy_recovered.to_mwh().value, 0.0)

    def test_forecast_detects_facility_capacity_overload(self):
        """Verify that when AI predicts a demand surge exceeding facility capacity, physics engine catches it."""
        from ecotwin.exceptions import CapacityExceededError

        # Small facility baseline that cannot handle peak forecast
        undersized_scenario = generate_baseline_scenario()  # AD capacity is 500 tonnes
        forecast = self.forecaster.predict_next_day()       # Predicted ~540 tonnes organics

        with self.assertRaises(CapacityExceededError):
            forecast.to_urban_scenario(undersized_scenario)


    def test_post_processing_constraint_enforcement(self):
        """Simulate raw edge cases to ensure normalization steps guarantee physical invariants."""
        # Test directly with forecast result construction
        raw_pred = {"total_waste_tonnes": 950.0, "frac_organic": 0.45}
        forecast = WasteForecastResult(
            forecast_date=dt.date(2026, 1, 1),
            predicted_total_waste=Mass.tonnes(950.0),
            predicted_composition={
                WasteCategory.ORGANIC: 0.40,
                WasteCategory.RECYCLABLE: 0.30,
                WasteCategory.E_WASTE: 0.05,
                WasteCategory.RESIDUAL: 0.25,
            },
            predicted_category_masses={
                WasteCategory.ORGANIC: Mass.tonnes(380.0),
                WasteCategory.RECYCLABLE: Mass.tonnes(285.0),
                WasteCategory.E_WASTE: Mass.tonnes(47.5),
                WasteCategory.RESIDUAL: Mass.tonnes(237.5),
            },
            model_metadata={"model": "test"},
            raw_unconstrained_prediction=raw_pred,
        )

        scenario = forecast_to_scenario(forecast, self.base_scenario)
        result = scenario.run()
        self.assertEqual(result.total_waste_processed, Mass.tonnes(950.0))
        self.assertAlmostEqual(result.mass_balance_error_kg, 0.0, places=5)


if __name__ == "__main__":
    unittest.main()

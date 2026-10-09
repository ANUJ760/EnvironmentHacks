"""Unit and integration tests for Phase 5 waste transportation and emissions model."""

import math
import unittest

from ecotwin.categories import WasteCategory
from ecotwin.exceptions import PhysicsViolationError
from ecotwin.facility import CategoryProcessingProfile, ProcessingFacility
from ecotwin.optimization import (
    OptimizationWeights,
    WasteRoutingOptimizer,
    optimize_scenario_routing,
)
from ecotwin.routing import RoutingPlan
from ecotwin.scenario import UrbanScenario
from ecotwin.synthetic import generate_baseline_scenario
from ecotwin.transport import (
    TRANSPORT_BENCHMARK_NOTICE,
    RouteTransportResult,
    TransportConfig,
    TransportEvaluationResult,
    TransportModel,
    evaluate_transport,
)
from ecotwin.units import Distance, DistanceUnit, Energy, EnergyUnit, Mass, MassUnit, SpecificEnergy


class TestDistanceUnit(unittest.TestCase):
    """Tests for Distance unit type."""

    def test_distance_km_creation(self):
        d = Distance.km(15.0)
        self.assertEqual(d.value, 15.0)
        self.assertEqual(d.unit, DistanceUnit.KM)

    def test_distance_meters_creation(self):
        d = Distance.meters(5000.0)
        self.assertEqual(d.value, 5000.0)
        self.assertEqual(d.unit, DistanceUnit.M)

    def test_distance_km_to_meters(self):
        d = Distance.km(2.5)
        d_m = d.to_meters()
        self.assertAlmostEqual(d_m.value, 2500.0)
        self.assertEqual(d_m.unit, DistanceUnit.M)

    def test_distance_meters_to_km(self):
        d = Distance.meters(7500.0)
        d_km = d.to_km()
        self.assertAlmostEqual(d_km.value, 7.5)
        self.assertEqual(d_km.unit, DistanceUnit.KM)

    def test_distance_negative_rejected(self):
        with self.assertRaises(PhysicsViolationError):
            Distance.km(-1.0)

    def test_distance_nan_rejected(self):
        with self.assertRaises(PhysicsViolationError):
            Distance.km(float("nan"))

    def test_distance_inf_rejected(self):
        with self.assertRaises(PhysicsViolationError):
            Distance.km(float("inf"))

    def test_distance_zero(self):
        d = Distance.zero()
        self.assertEqual(d.value, 0.0)
        self.assertEqual(d.unit, DistanceUnit.KM)

    def test_distance_arithmetic(self):
        d1 = Distance.km(10.0)
        d2 = Distance.km(5.0)
        total = d1 + d2
        self.assertAlmostEqual(total.value, 15.0)
        diff = d1 - d2
        self.assertAlmostEqual(diff.value, 5.0)
        scaled = d1 * 3
        self.assertAlmostEqual(scaled.value, 30.0)

    def test_distance_equality_cross_unit(self):
        d_km = Distance.km(5.0)
        d_m = Distance.meters(5000.0)
        self.assertEqual(d_km, d_m)


class TestVehicleTripCalculation(unittest.TestCase):
    """Tests for vehicle trip count calculation."""

    def test_exact_payload_single_trip(self):
        # 10 tonnes / 10 t payload = 1 trip
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(10.0),
            distance=Distance.km(20.0),
            config=TransportConfig(vehicle_payload=Mass.tonnes(10.0)),
        )
        self.assertEqual(result.trips, 1)

    def test_multiple_full_trips(self):
        # 30 tonnes / 10 t payload = 3 trips
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(30.0),
            distance=Distance.km(15.0),
            config=TransportConfig(vehicle_payload=Mass.tonnes(10.0)),
        )
        self.assertEqual(result.trips, 3)

    def test_partial_final_truck_load(self):
        # 25 tonnes / 10 t payload = ceil(2.5) = 3 trips
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(25.0),
            distance=Distance.km(10.0),
            config=TransportConfig(vehicle_payload=Mass.tonnes(10.0)),
        )
        self.assertEqual(result.trips, 3)

    def test_small_partial_load(self):
        # 1 tonne / 10 t payload = ceil(0.1) = 1 trip
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(1.0),
            distance=Distance.km(10.0),
            config=TransportConfig(vehicle_payload=Mass.tonnes(10.0)),
        )
        self.assertEqual(result.trips, 1)

    def test_zero_mass_zero_trips(self):
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(0.0),
            distance=Distance.km(20.0),
            config=TransportConfig(vehicle_payload=Mass.tonnes(10.0)),
        )
        self.assertEqual(result.trips, 0)
        self.assertAlmostEqual(result.total_distance.to_km().value, 0.0)


class TestTransportEnergyCalculation(unittest.TestCase):
    """Tests for transport energy and distance calculations."""

    def test_transport_distance_calculation(self):
        # 3 trips * 20 km = 60 km total
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(25.0),
            distance=Distance.km(20.0),
            config=TransportConfig(
                vehicle_payload=Mass.tonnes(10.0),
                vehicle_energy_per_km=Energy.kwh(3.5),
            ),
        )
        self.assertEqual(result.trips, 3)
        self.assertAlmostEqual(result.total_distance.to_km().value, 60.0)

    def test_transport_energy_calculation(self):
        # 3 trips * 20 km = 60 km * 3.5 kWh/km = 210 kWh
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(25.0),
            distance=Distance.km(20.0),
            config=TransportConfig(
                vehicle_payload=Mass.tonnes(10.0),
                vehicle_energy_per_km=Energy.kwh(3.5),
                emissions_factor=0.27,
            ),
        )
        self.assertAlmostEqual(result.transport_energy.to_kwh().value, 210.0)

    def test_zero_distance_zero_energy(self):
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(100.0),
            distance=Distance.km(0.0),
            config=TransportConfig(vehicle_payload=Mass.tonnes(10.0)),
        )
        self.assertAlmostEqual(result.transport_energy.to_kwh().value, 0.0)


class TestEmissionsCalculation(unittest.TestCase):
    """Tests for CO2 emissions calculation."""

    def test_emissions_formula(self):
        # 3 trips * 20 km = 60 km * 3.5 kWh/km = 210 kWh * 0.27 kg CO2/kWh = 56.7 kg CO2
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(25.0),
            distance=Distance.km(20.0),
            config=TransportConfig(
                vehicle_payload=Mass.tonnes(10.0),
                vehicle_energy_per_km=Energy.kwh(3.5),
                emissions_factor=0.27,
            ),
        )
        expected_co2_kg = 60.0 * 3.5 * 0.27  # 56.7 kg
        self.assertAlmostEqual(result.transport_emissions.to_kg().value, expected_co2_kg, places=4)

    def test_zero_mass_zero_emissions(self):
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(0.0),
            distance=Distance.km(20.0),
            config=TransportConfig(),
        )
        self.assertAlmostEqual(result.transport_emissions.to_kg().value, 0.0)

    def test_zero_distance_zero_emissions(self):
        result = TransportModel.calculate_route_transport(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(100.0),
            distance=Distance.km(0.0),
            config=TransportConfig(),
        )
        self.assertAlmostEqual(result.transport_emissions.to_kg().value, 0.0)


class TestDeterministicResults(unittest.TestCase):
    """Tests for strict determinism in transport calculations."""

    def test_reproducibility(self):
        config = TransportConfig(
            vehicle_payload=Mass.tonnes(10.0),
            vehicle_energy_per_km=Energy.kwh(3.5),
            emissions_factor=0.27,
        )
        args = dict(
            facility_name="TestFac",
            waste_mass=Mass.tonnes(47.3),
            distance=Distance.km(18.7),
            config=config,
        )
        r1 = TransportModel.calculate_route_transport(**args)
        r2 = TransportModel.calculate_route_transport(**args)
        self.assertEqual(r1.trips, r2.trips)
        self.assertEqual(r1.total_distance, r2.total_distance)
        self.assertAlmostEqual(r1.transport_energy.to_kwh().value, r2.transport_energy.to_kwh().value)
        self.assertAlmostEqual(r1.transport_emissions.to_kg().value, r2.transport_emissions.to_kg().value)

    def test_system_level_reproducibility(self):
        scenario = generate_baseline_scenario()
        res1 = scenario.evaluate_transport()
        res2 = scenario.evaluate_transport()
        self.assertEqual(res1.total_trips, res2.total_trips)
        self.assertAlmostEqual(res1.total_distance.to_km().value, res2.total_distance.to_km().value)
        self.assertAlmostEqual(
            res1.total_transport_emissions.to_kg().value,
            res2.total_transport_emissions.to_kg().value,
        )


class TestTransportAwareOptimization(unittest.TestCase):
    """Tests for transport-aware optimization integration."""

    def setUp(self):
        # Facility A: better recovery (70% mat, 10% landfill, 20% loss) but farther (50 km)
        # Facility B: worse recovery (50% mat, 20% landfill, 30% loss) but closer (5 km)
        self.fac_far = ProcessingFacility(
            name="Far_Good_Recovery",
            capacity=Mass.tonnes(600.0),
            accepted_categories={WasteCategory.ORGANIC},
            distance=Distance.km(50.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.70,
                landfill_residue_rate=0.10,
                process_loss_rate=0.20,
            ),
        )
        self.fac_near = ProcessingFacility(
            name="Near_Moderate_Recovery",
            capacity=Mass.tonnes(600.0),
            accepted_categories={WasteCategory.ORGANIC},
            distance=Distance.km(5.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.50,
                landfill_residue_rate=0.20,
                process_loss_rate=0.30,
            ),
        )
        self.mrf = ProcessingFacility(
            name="MRF",
            capacity=Mass.tonnes(300.0),
            accepted_categories={WasteCategory.RECYCLABLE},
            distance=Distance.km(10.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.85,
                landfill_residue_rate=0.15,
                process_loss_rate=0.00,
            ),
        )
        self.wte = ProcessingFacility(
            name="WTE",
            capacity=Mass.tonnes(300.0),
            accepted_categories={WasteCategory.RESIDUAL, WasteCategory.E_WASTE},
            distance=Distance.km(15.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.10,
                landfill_residue_rate=0.20,
                process_loss_rate=0.70,
            ),
        )
        self.facilities = [self.fac_far, self.fac_near, self.mrf, self.wte]

        self.scenario = UrbanScenario.create(
            name="Transport_Tradeoff_Scenario",
            daily_waste_generation=Mass.tonnes(500.0),
            composition={
                WasteCategory.ORGANIC: 0.50,
                WasteCategory.RECYCLABLE: 0.25,
                WasteCategory.E_WASTE: 0.05,
                WasteCategory.RESIDUAL: 0.20,
            },
            facilities=self.facilities,
            routing_plan=RoutingPlan.create_direct({
                WasteCategory.ORGANIC: "Far_Good_Recovery",
                WasteCategory.RECYCLABLE: "MRF",
                WasteCategory.E_WASTE: "WTE",
                WasteCategory.RESIDUAL: "WTE",
            }),
        )

    def test_no_transport_penalty_prefers_better_recovery(self):
        """Without transport penalty, optimizer picks better recovery (far facility)."""
        weights = OptimizationWeights(
            material_recovery_weight=2.0,
            landfill_penalty_weight=1.0,
            energy_recovery_weight=0.0,
            transport_penalty_weight=0.0,
        )
        opt_res = optimize_scenario_routing(self.scenario, weights=weights)
        # Should prefer far facility because of better recovery
        org_splits = opt_res.optimized_routing.routes[WasteCategory.ORGANIC]
        far_frac = sum(s.fraction for s in org_splits if s.facility_name == "Far_Good_Recovery")
        self.assertAlmostEqual(far_frac, 1.0, places=3)

    def test_high_transport_penalty_prefers_closer_facility(self):
        """With high transport penalty, optimizer shifts to closer facility."""
        weights = OptimizationWeights(
            material_recovery_weight=1.0,
            landfill_penalty_weight=1.0,
            energy_recovery_weight=0.0,
            transport_penalty_weight=0.5,
            transport_reference_km_per_tonne=10.0,
        )
        opt_res = optimize_scenario_routing(self.scenario, weights=weights)
        org_splits = opt_res.optimized_routing.routes[WasteCategory.ORGANIC]
        near_frac = sum(s.fraction for s in org_splits if s.facility_name == "Near_Moderate_Recovery")
        # With strong transport penalty, near facility should be preferred
        self.assertGreater(near_frac, 0.5)


class TestMassBalanceConservation(unittest.TestCase):
    """Tests that transport metrics do NOT affect mass/energy balance."""

    def test_mass_balance_unchanged_with_transport(self):
        scenario = generate_baseline_scenario()
        result = scenario.run(evaluate_transport=True)
        # Mass balance must hold exactly
        self.assertAlmostEqual(result.mass_balance_error_kg, 0.0, places=5)
        # Transport evaluation must be present
        self.assertIsNotNone(result.transport_result)
        self.assertGreater(result.transport_result.total_trips, 0)
        self.assertGreater(result.transport_result.total_distance.to_km().value, 0.0)

    def test_mass_balance_same_with_and_without_transport(self):
        scenario = generate_baseline_scenario()
        result_with = scenario.run(evaluate_transport=True)
        result_without = scenario.run(evaluate_transport=False)
        # Mass balance identical
        self.assertAlmostEqual(
            result_with.total_material_recovered.to_kg().value,
            result_without.total_material_recovered.to_kg().value,
            places=5,
        )
        self.assertAlmostEqual(
            result_with.total_landfill_residue.to_kg().value,
            result_without.total_landfill_residue.to_kg().value,
            places=5,
        )
        self.assertAlmostEqual(
            result_with.total_energy_recovered.to_kwh().value,
            result_without.total_energy_recovered.to_kwh().value,
            places=5,
        )
        self.assertAlmostEqual(result_with.mass_balance_error_kg, 0.0, places=5)
        self.assertAlmostEqual(result_without.mass_balance_error_kg, 0.0, places=5)

    def test_optimized_mass_balance_with_transport_penalty(self):
        scenario = generate_baseline_scenario()
        weights = OptimizationWeights(
            material_recovery_weight=1.0,
            landfill_penalty_weight=1.0,
            energy_recovery_weight=0.5,
            transport_penalty_weight=0.3,
            transport_reference_km_per_tonne=10.0,
        )
        opt_res = optimize_scenario_routing(scenario, weights=weights)
        self.assertAlmostEqual(opt_res.optimized_execution.mass_balance_error_kg, 0.0, places=5)
        self.assertAlmostEqual(opt_res.baseline_execution.mass_balance_error_kg, 0.0, places=5)


class TestFacilityDistance(unittest.TestCase):
    """Tests for facility distance configuration."""

    def test_facility_distance_from_distance_object(self):
        fac = ProcessingFacility(
            name="Test",
            capacity=Mass.tonnes(100.0),
            distance=Distance.km(12.5),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.5,
                landfill_residue_rate=0.3,
                process_loss_rate=0.2,
            ),
        )
        self.assertAlmostEqual(fac.distance_km, 12.5)

    def test_facility_distance_from_float(self):
        fac = ProcessingFacility(
            name="Test",
            capacity=Mass.tonnes(100.0),
            distance=7.5,
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.5,
                landfill_residue_rate=0.3,
                process_loss_rate=0.2,
            ),
        )
        self.assertAlmostEqual(fac.distance_km, 7.5)

    def test_facility_no_distance_defaults_zero(self):
        fac = ProcessingFacility(
            name="Test",
            capacity=Mass.tonnes(100.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.5,
                landfill_residue_rate=0.3,
                process_loss_rate=0.2,
            ),
        )
        self.assertAlmostEqual(fac.distance_km, 0.0)

    def test_facility_location_computes_distance(self):
        fac = ProcessingFacility(
            name="Test",
            capacity=Mass.tonnes(100.0),
            location=(3.0, 4.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.5,
                landfill_residue_rate=0.3,
                process_loss_rate=0.2,
            ),
        )
        self.assertAlmostEqual(fac.distance_km, 5.0)


class TestTransportConfig(unittest.TestCase):
    """Tests for TransportConfig validation."""

    def test_default_config(self):
        config = TransportConfig()
        self.assertAlmostEqual(config.vehicle_payload.to_tonnes().value, 10.0)
        self.assertAlmostEqual(config.vehicle_energy_per_km.to_kwh().value, 3.5)
        self.assertAlmostEqual(config.emissions_factor, 0.27)

    def test_negative_emissions_factor_rejected(self):
        with self.assertRaises(PhysicsViolationError):
            TransportConfig(emissions_factor=-0.1)

    def test_zero_payload_rejected(self):
        with self.assertRaises(PhysicsViolationError):
            TransportConfig(vehicle_payload=Mass.tonnes(0.0))

    def test_benchmark_notice_exists(self):
        self.assertIn("ASSUMPTION", TRANSPORT_BENCHMARK_NOTICE)


class TestSystemTransportEvaluation(unittest.TestCase):
    """Tests for system-level transport evaluation."""

    def test_baseline_scenario_has_transport(self):
        scenario = generate_baseline_scenario()
        transport_res = scenario.evaluate_transport()
        self.assertGreater(transport_res.total_trips, 0)
        self.assertGreater(transport_res.total_distance.to_km().value, 0.0)
        self.assertGreater(transport_res.total_transport_energy.to_kwh().value, 0.0)
        self.assertGreater(transport_res.total_transport_emissions.to_kg().value, 0.0)

    def test_evaluate_transport_convenience_function(self):
        scenario = generate_baseline_scenario()
        loads = scenario.calculate_facility_loads()
        transport_res = evaluate_transport(
            facility_loads=loads,
            facilities=scenario.facilities,
        )
        self.assertGreater(transport_res.total_trips, 0)

    def test_transport_summary_structure(self):
        scenario = generate_baseline_scenario()
        transport_res = scenario.evaluate_transport()
        summary = transport_res.summary()
        self.assertIn("total_vehicle_trips", summary)
        self.assertIn("total_distance_km", summary)
        self.assertIn("total_transport_energy_kwh", summary)
        self.assertIn("total_transport_emissions_kg_co2", summary)
        self.assertIn("routes", summary)


if __name__ == "__main__":
    unittest.main()

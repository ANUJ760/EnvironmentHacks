"""
Phase 5 End-to-End Waste Transportation & Optimization Pipeline for EcoTwin.

Pipeline Flow:
Synthetic History
      ↓
ML Forecast
      ↓
Urban Scenario
      ↓
Baseline Routing
      ↓
Transport Evaluation
      ↓
Optimized Routing
      ↓
Transport + Physics Evaluation

Demonstrates:
1. Generating a reproducible synthetic historical dataset (365 days).
2. Training an interpretable multi-output ML forecaster with physical constraints.
3. Predicting next-day generation and composition subject to physics conservation.
4. Converting the forecast into an UrbanScenario with synthetic facility locations/distances.
5. Evaluating baseline physical performance and transport logistics (trips, distance, energy, CO2).
6. Optimizing waste routing via deterministic LP Simplex accounting for transport cost penalties.
7. Evaluating optimized routing with complete physics and transport balance.
8. Reporting a side-by-side comparison containing all required Phase 5 metrics.
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecotwin import (
    CategoryProcessingProfile,
    Distance,
    Energy,
    EnergyUnit,
    Mass,
    OptimizationWeights,
    ProcessingFacility,
    RoutingPlan,
    SpecificEnergy,
    TransportConfig,
    UrbanScenario,
    WasteCategory,
    WasteForecaster,
    generate_synthetic_history,
    optimize_scenario_routing,
)
from ecotwin.transport import TRANSPORT_BENCHMARK_NOTICE


def run_transport_optimization_pipeline() -> None:
    print("=" * 80)
    print(" EcoTwin Phase 5: Transport-Aware Waste Forecasting & Optimization Pipeline")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # Step 1: Generate Synthetic History
    # -------------------------------------------------------------------------
    print("\n[Step 1] Generating Synthetic Historical Waste Observations (365 days)...")
    history = generate_synthetic_history(
        days=365,
        base_generation_tonnes=1000.0,
        annual_growth_rate=0.02,
        city_name="Metropolis Gamma",
        random_seed=42,
    )
    print(f"  * Generated {len(history)} daily records ({history.start_date} to {history.end_date})")

    # -------------------------------------------------------------------------
    # Step 2: ML Forecast
    # -------------------------------------------------------------------------
    print("\n[Step 2] Training Physics-Constrained ML Forecaster...")
    forecaster = WasteForecaster(alpha=0.5).train(history)

    # -------------------------------------------------------------------------
    # Step 3: Predict Next-Day Generation & Composition
    # -------------------------------------------------------------------------
    print("\n[Step 3] Predicting Next-Day Urban Waste Generation & Composition...")
    forecast = forecaster.predict_next_day()
    print(f"  * Forecast Horizon Date : {forecast.forecast_date.isoformat()}")
    print(f"  * Predicted Total Waste : {forecast.predicted_total_waste.value:.2f} tonnes")
    print("  * Predicted Composition Breakdown:")
    for cat, frac in forecast.predicted_composition.items():
        mass = forecast.predicted_category_masses[cat]
        print(f"      - {cat.value:<12}: {mass.value:>7.2f} tonnes ({frac * 100:>5.2f}%)")

    # -------------------------------------------------------------------------
    # Step 4: Configure Urban Scenario with Transport Locations/Distances
    # -------------------------------------------------------------------------
    print("\n[Step 4] Configuring Urban Facilities & Synthetic Transport Distances...")
    print(f"  * Benchmark Note: {TRANSPORT_BENCHMARK_NOTICE}")

    # Facilities configured with realistic conversion physics and synthetic distances:
    # 1. Composting Center: Close (8 km), high material recovery for organics (75% mat, 10% landfill, 15% loss)
    # 2. Anaerobic Digestion Plant: Moderate distance (25 km), biogas energy + digestate (45% mat, 10% landfill, 45% loss)
    # 3. Materials Recovery Facility (MRF): Near (12 km), high recyclables recovery (85% mat, 15% landfill)
    # 4. E-Waste Refurbishment Hub: (18 km), high metal extraction (75% mat, 25% landfill)
    # 5. Waste-to-Energy Plant: Far (35 km), accepts residual & overflow organics (12% mat, 18% landfill, 70% loss)
    facilities = [
        ProcessingFacility(
            name="Composting_Center",
            capacity=Mass.tonnes(450.0),
            accepted_categories={WasteCategory.ORGANIC},
            distance=Distance.km(8.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.75,
                landfill_residue_rate=0.10,
                process_loss_rate=0.15,
            ),
        ),
        ProcessingFacility(
            name="Anaerobic_Digestion_Plant",
            capacity=Mass.tonnes(450.0),
            accepted_categories={WasteCategory.ORGANIC},
            distance=Distance.km(25.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.45,
                landfill_residue_rate=0.10,
                process_loss_rate=0.45,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(320.0),
                energy_efficiency=0.38,
            ),
        ),
        ProcessingFacility(
            name="Materials_Recovery_Facility",
            capacity=Mass.tonnes(450.0),
            accepted_categories={WasteCategory.RECYCLABLE},
            distance=Distance.km(12.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.85,
                landfill_residue_rate=0.15,
                process_loss_rate=0.00,
            ),
        ),
        ProcessingFacility(
            name="E_Waste_Refurbishment_Hub",
            capacity=Mass.tonnes(120.0),
            accepted_categories={WasteCategory.E_WASTE},
            distance=Distance.km(18.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.75,
                landfill_residue_rate=0.25,
                process_loss_rate=0.00,
            ),
        ),
        ProcessingFacility(
            name="Waste_to_Energy_Plant",
            capacity=Mass.tonnes(450.0),
            accepted_categories={WasteCategory.RESIDUAL, WasteCategory.ORGANIC},
            distance=Distance.km(35.0),
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.12,
                landfill_residue_rate=0.18,
                process_loss_rate=0.70,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(2400.0),
                energy_efficiency=0.25,
            ),
        ),
    ]

    print("  * Facility Transport Distances:")
    for fac in facilities:
        print(f"      - {fac.name:<32}: {fac.distance_km:>6.1f} km")

    # Baseline routing sends 100% of organics to the farther Anaerobic Digestion Plant (25 km)
    baseline_routing = RoutingPlan.create({
        WasteCategory.ORGANIC: [("Anaerobic_Digestion_Plant", 1.0)],
        WasteCategory.RECYCLABLE: [("Materials_Recovery_Facility", 1.0)],
        WasteCategory.E_WASTE: [("E_Waste_Refurbishment_Hub", 1.0)],
        WasteCategory.RESIDUAL: [("Waste_to_Energy_Plant", 1.0)],
    })

    fleet_config = TransportConfig(
        vehicle_payload=Mass.tonnes(10.0),
        vehicle_energy_per_km=Energy.kwh(3.5),
        emissions_factor=0.27,
    )

    base_scenario = UrbanScenario.create(
        name="Metropolis_Gamma_Baseline",
        daily_waste_generation=forecast.predicted_total_waste,
        composition=forecast.predicted_composition,
        facilities=facilities,
        routing_plan=baseline_routing,
        transport_config=fleet_config,
        description="Baseline synthetic city scenario with sub-optimal routing.",
    )

    # -------------------------------------------------------------------------
    # Step 5: Baseline Routing + Transport Evaluation
    # -------------------------------------------------------------------------
    print("\n[Step 5] Evaluating Baseline Routing (Physics + Transport Logistics)...")
    baseline_exec = base_scenario.run(energy_output_unit=EnergyUnit.MWH, evaluate_transport=True)
    baseline_transport = baseline_exec.transport_result
    assert baseline_transport is not None
    print(baseline_transport.format_report())

    # -------------------------------------------------------------------------
    # Step 6: Optimized Routing with Transport Penalty
    # -------------------------------------------------------------------------
    print("\n[Step 6] Executing Multi-Objective Routing Optimization (LP Simplex)...")
    weights = OptimizationWeights(
        material_recovery_weight=1.5,
        landfill_penalty_weight=1.0,
        energy_recovery_weight=0.5,
        transport_penalty_weight=0.3,
        transport_reference_km_per_tonne=10.0,
    )

    opt_result = optimize_scenario_routing(
        scenario=base_scenario,
        weights=weights,
        energy_output_unit=EnergyUnit.MWH,
    )

    print("\n[Optimized Category Routing Decisions]")
    for cat, splits in opt_result.optimized_routing.routes.items():
        split_desc = ", ".join(f"{s.facility_name} ({s.fraction * 100:.1f}%)" for s in splits)
        print(f"  * {cat.value:<12} -> {split_desc}")

    # -------------------------------------------------------------------------
    # Step 7: Transport + Physics Evaluation of Optimized Routing
    # -------------------------------------------------------------------------
    print("\n[Step 7] Evaluating Optimized Routing (Physics Balance + Transport Logistics)...")
    opt_exec = opt_result.optimized_execution
    opt_transport = opt_exec.transport_result
    if opt_transport is None:
        opt_transport = base_scenario.evaluate_transport(routing_plan=opt_result.optimized_routing)

    print(opt_transport.format_report())

    # Calculate objective scores including transport penalty
    baseline_score = weights.calculate_score(baseline_exec)
    optimized_score = weights.calculate_score(opt_exec, transport_result=opt_transport)
    score_improvement = optimized_score - baseline_score
    score_improvement_pct = (score_improvement / abs(baseline_score) * 100.0) if abs(baseline_score) > 1e-9 else 0.0

    # -------------------------------------------------------------------------
    # Step 8: Print Comparison Report
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" EcoTwin Phase 5: Complete Transport-Aware Optimization Comparison")
    print("=" * 80)

    base_mat = baseline_exec.total_material_recovered.to_tonnes().value
    opt_mat = opt_exec.total_material_recovered.to_tonnes().value

    base_energy = baseline_exec.total_energy_recovered.to_mwh().value
    opt_energy = opt_exec.total_energy_recovered.to_mwh().value

    base_landfill = baseline_exec.total_landfill_residue.to_tonnes().value
    opt_landfill = opt_exec.total_landfill_residue.to_tonnes().value

    base_dist = baseline_transport.total_distance.to_km().value
    opt_dist = opt_transport.total_distance.to_km().value

    base_t_energy = baseline_transport.total_transport_energy.to_kwh().value
    opt_t_energy = opt_transport.total_transport_energy.to_kwh().value

    base_co2 = baseline_transport.total_transport_emissions.to_kg().value
    opt_co2 = opt_transport.total_transport_emissions.to_kg().value

    base_trips = baseline_transport.total_trips
    opt_trips = opt_transport.total_trips

    print(f"\n  {'Metric':<34} | {'Baseline':>12} | {'Optimized':>12} | {'Delta':>12}")
    print(f"  {'-'*34}-|-{'-'*12}-|-{'-'*12}-|-{'-'*12}")
    print(f"  {'Material Recovered (tonnes)':<34} | {base_mat:>10.2f} t | {opt_mat:>10.2f} t | {opt_mat - base_mat:>+10.2f} t")
    print(f"  {'Energy Recovered (MWh)':<34} | {base_energy:>10.2f}   | {opt_energy:>10.2f}   | {opt_energy - base_energy:>+10.2f}  ")
    print(f"  {'Landfill Residue (tonnes)':<34} | {base_landfill:>10.2f} t | {opt_landfill:>10.2f} t | {opt_landfill - base_landfill:>+10.2f} t")
    print(f"  {'Transport Distance (km)':<34} | {base_dist:>10.2f}   | {opt_dist:>10.2f}   | {opt_dist - base_dist:>+10.2f} km")
    print(f"  {'Transport Energy (kWh)':<34} | {base_t_energy:>10.2f}   | {opt_t_energy:>10.2f}   | {opt_t_energy - base_t_energy:>+10.2f} kWh")
    print(f"  {'Transport CO2 (kg)':<34} | {base_co2:>10.2f}   | {opt_co2:>10.2f}   | {opt_co2 - base_co2:>+10.2f} kg")
    print(f"  {'Vehicle Trips':<34} | {base_trips:>10}   | {opt_trips:>10}   | {opt_trips - base_trips:>+10} trips")
    print(f"  {'Objective Score':<34} | {baseline_score:>10.4f}   | {optimized_score:>10.4f}   | {score_improvement:>+10.4f}  ")
    print(f"  {'Objective Improvement (%)':<34} | {'':>10}   | {'':>10}   | {score_improvement_pct:>+10.2f} %")
    print(f"  {'Mass-Balance Closure (kg)':<34} | {baseline_exec.mass_balance_error_kg:>10.6f} kg| {opt_exec.mass_balance_error_kg:>10.6f} kg| {'0.000000 kg':>12}")

    print("\n" + "=" * 80)
    print(" EcoTwin Phase 5 Pipeline Execution Successfully Completed.")
    print("=" * 80)


if __name__ == "__main__":
    run_transport_optimization_pipeline()

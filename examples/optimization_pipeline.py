"""
Phase 4 End-to-End Waste Forecasting & Routing Optimization Pipeline for EcoTwin.

Demonstrates:
1. Generating a reproducible synthetic historical dataset (365 days).
2. Training an interpretable multi-output ML forecaster.
3. Predicting next-day generation and composition subject to physical constraints.
4. Converting the forecast into a baseline UrbanScenario.
5. Evaluating baseline physical performance through EcoTwinEngine.
6. Optimizing waste routing via deterministic Linear Programming (Two-Phase Simplex).
7. Evaluating optimized routing through EcoTwinEngine.
8. Reporting a side-by-side comparison of baseline vs optimized metrics.

Principle:
"AI predicts the uncertain future; Optimization proposes routing decisions; Physics determines what happens."
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecotwin import (
    CategoryProcessingProfile,
    EnergyUnit,
    Mass,
    OptimizationWeights,
    ProcessingFacility,
    RoutingPlan,
    SpecificEnergy,
    UrbanScenario,
    WasteCategory,
    WasteForecaster,
    generate_synthetic_history,
    optimize_scenario_routing,
)


def run_optimization_pipeline() -> None:
    print("=" * 74)
    print(" EcoTwin Phase 4: Waste Forecasting & Routing Optimization Pipeline")
    print("=" * 74)

    # Step 1: Generate synthetic historical observations (365 days)
    print("\n[Step 1] Generating Synthetic Historical Waste Dataset (365 days)...")
    history = generate_synthetic_history(
        days=365,
        base_generation_tonnes=1000.0,
        annual_growth_rate=0.02,
        city_name="Metropolis Beta",
        random_seed=42,
    )
    print(f"  * Generated {len(history)} daily observations ({history.start_date} to {history.end_date})")

    # Step 2: Train Autoregressive ML Forecaster
    print("\n[Step 2] Training ML Forecaster on Historical Dynamics...")
    forecaster = WasteForecaster(alpha=0.5).train(history)

    # Step 3: Predict Next-Day Generation & Composition with Physical Constraints
    print("\n[Step 3] Predicting Next-Day Urban Waste Generation & Composition...")
    forecast = forecaster.predict_next_day()
    print(f"  * Forecast Date        : {forecast.forecast_date.isoformat()}")
    print(f"  * Predicted Total Waste: {forecast.predicted_total_waste.value:.2f} tonnes")
    print("  * Predicted Composition:")
    for cat, frac in forecast.predicted_composition.items():
        mass = forecast.predicted_category_masses[cat]
        print(f"      - {cat.value:<12}: {mass.value:>7.2f} tonnes ({frac * 100:>5.2f}%)")

    # Step 4: Configure Urban Facilities and Sub-Optimal Baseline Routing
    print("\n[Step 4] Configuring Urban Facilities & Baseline Scenario...")
    # Facility setup with multiple viable routes:
    # 1. Composting Center: High material recovery for organics (75% mat, 10% landfill, 15% loss)
    # 2. Anaerobic Digestion: Moderate material recovery, high biogas energy (45% mat, 10% landfill, 45% loss, 320 kWh/t)
    # 3. Materials Recovery Facility (MRF): High recyclables recovery (85% mat, 15% landfill)
    # 4. E-Waste Hub: High metal/component extraction (75% mat, 25% landfill)
    # 5. Waste-to-Energy Plant: Multi-fuel thermal conversion (12% mat, 18% landfill, 70% loss, 2400 kWh/t)

    facilities = [
        ProcessingFacility(
            name="Composting_Center",
            capacity=Mass.tonnes(300.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.75,
                landfill_residue_rate=0.10,
                process_loss_rate=0.15,
            ),
        ),
        ProcessingFacility(
            name="Anaerobic_Digestion_Plant",
            capacity=Mass.tonnes(350.0),
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
            name="Materials_Recovery_Facility",
            capacity=Mass.tonnes(400.0),
            accepted_categories={WasteCategory.RECYCLABLE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.85,
                landfill_residue_rate=0.15,
                process_loss_rate=0.00,
            ),
        ),
        ProcessingFacility(
            name="E_Waste_Hub",
            capacity=Mass.tonnes(100.0),
            accepted_categories={WasteCategory.E_WASTE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.75,
                landfill_residue_rate=0.25,
                process_loss_rate=0.00,
            ),
        ),
        ProcessingFacility(
            name="Waste_to_Energy_Plant",
            capacity=Mass.tonnes(400.0),
            accepted_categories={WasteCategory.RESIDUAL, WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.12,
                landfill_residue_rate=0.18,
                process_loss_rate=0.70,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(2400.0),
                energy_efficiency=0.25,
            ),
        ),
    ]

    # Baseline routing (splits organics 50/50 between Composting and AD)
    baseline_routing = RoutingPlan.create({
        WasteCategory.ORGANIC: [("Composting_Center", 0.5), ("Anaerobic_Digestion_Plant", 0.5)],
        WasteCategory.RECYCLABLE: [("Materials_Recovery_Facility", 1.0)],
        WasteCategory.E_WASTE: [("E_Waste_Hub", 1.0)],
        WasteCategory.RESIDUAL: [("Waste_to_Energy_Plant", 1.0)],
    })

    base_scenario = UrbanScenario.create(

        name="Metropolis_Beta_Unoptimized",
        daily_waste_generation=forecast.predicted_total_waste,
        composition=forecast.predicted_composition,
        facilities=facilities,
        routing_plan=baseline_routing,
        description="Baseline scenario with unoptimized direct waste routing.",
    )

    # Step 5: Execute Waste Routing Optimization
    print("\n[Step 5] Optimizing Waste Routing via Linear Programming (Two-Phase Simplex)...")
    weights = OptimizationWeights(
        material_recovery_weight=1.5,
        landfill_penalty_weight=1.0,
        energy_recovery_weight=0.8,
    )
    opt_result = optimize_scenario_routing(
        scenario=base_scenario,
        weights=weights,
        energy_output_unit=EnergyUnit.MWH,
    )

    # Step 6: Print Detailed Side-by-Side Comparison Report
    print("\n[Step 6] Execution & Physical Balance Comparison:")
    print(opt_result.format_report())

    print("\n[Optimized Category Routing Decisions]")
    for cat, splits in opt_result.optimized_routing.routes.items():
        split_desc = ", ".join(f"{s.facility_name} ({s.fraction * 100:.1f}%)" for s in splits)
        print(f"  * {cat.value:<12} -> {split_desc}")


if __name__ == "__main__":
    run_optimization_pipeline()

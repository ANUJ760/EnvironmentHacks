"""
Phase 3 End-to-End Waste Forecasting & Simulation Pipeline for EcoTwin.

Demonstrates:
1. Generating a reproducible synthetic historical dataset of daily urban waste (trend + weekly/seasonal dynamics).
2. Training an interpretable autoregressive multi-output ML forecaster.
3. Predicting next-day waste generation and composition subject to physical constraints (non-negativity, sum-to-1 simplex).
4. Binding the forecast into an UrbanScenario.
5. Executing deterministic physical mass/energy balance simulation through the EcoTwin physics engine.

Principle:
"AI predicts the uncertain future; the physics engine determines what is physically possible."
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecotwin import (
    EnergyUnit,
    Mass,
    WasteCategory,
    WasteForecaster,
    generate_baseline_scenario,
    generate_synthetic_history,
)


def run_forecasting_pipeline() -> None:
    print("=" * 74)
    print(" EcoTwin Phase 3: AI Waste Forecasting & Physics Simulation Pipeline")
    print("=" * 74)

    # Step 1: Generate synthetic historical observations (365 days)
    print("\n[Step 1] Generating Synthetic Historical Waste Dataset (365 days)...")
    history = generate_synthetic_history(
        days=365,
        base_generation_tonnes=1000.0,
        annual_growth_rate=0.02,
        city_name="Metropolis Alpha",
        random_seed=42,
    )
    print(f"  * Generated {len(history)} daily observations ({history.start_date} to {history.end_date})")
    print(f"  * Average Generation: {sum(history.get_total_waste_series()) / len(history):.2f} tonnes/day")
    print(f"  * Notice: {history.metadata['assumptions']['notice']}")

    # Step 2: Train Autoregressive ML Forecaster
    print("\n[Step 2] Training Interpretable Multi-Output Autoregressive Forecaster...")
    forecaster = WasteForecaster(alpha=0.5).train(history)
    print("  * Model trained successfully on lag, trend, and cyclical calendar features.")

    # Step 3: Predict Next-Day Generation & Composition with Physical Constraints
    print("\n[Step 3] Predicting Next-Day Urban Waste Generation & Composition...")
    forecast = forecaster.predict_next_day()
    print(forecast.format_report())

    # Step 4: Convert Forecast into Validated UrbanScenario
    print("\n[Step 4] Converting Forecast into UrbanScenario...")
    # Sizing base scenario facilities with buffer for peak seasonal demand
    from ecotwin import CategoryProcessingProfile, ProcessingFacility, RoutingPlan, SpecificEnergy, UrbanScenario
    
    metropolis_facilities = [
        ProcessingFacility(
            name="Anaerobic_Digestion_Plant",
            capacity=Mass.tonnes(650.0),
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
                material_recovery_rate=0.82,
                landfill_residue_rate=0.18,
                process_loss_rate=0.00,
            ),
        ),
        ProcessingFacility(
            name="E_Waste_Refurbishment_Hub",
            capacity=Mass.tonnes(100.0),
            accepted_categories={WasteCategory.E_WASTE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.72,
                landfill_residue_rate=0.28,
                process_loss_rate=0.00,
            ),
        ),
        ProcessingFacility(
            name="Waste_to_Energy_Plant",
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
    ]

    base_scenario = UrbanScenario.create(
        name="Metropolis_Alpha_Baseline",
        daily_waste_generation=Mass.tonnes(1000.0),
        composition={
            WasteCategory.ORGANIC: 0.45,
            WasteCategory.RECYCLABLE: 0.25,
            WasteCategory.E_WASTE: 0.05,
            WasteCategory.RESIDUAL: 0.25,
        },
        facilities=metropolis_facilities,
        routing_plan=RoutingPlan.create_direct({
            WasteCategory.ORGANIC: "Anaerobic_Digestion_Plant",
            WasteCategory.RECYCLABLE: "Materials_Recovery_Facility",
            WasteCategory.E_WASTE: "E_Waste_Refurbishment_Hub",
            WasteCategory.RESIDUAL: "Waste_to_Energy_Plant",
        }),
    )

    forecasted_scenario = forecast.to_urban_scenario(base_scenario)
    print(f"  * Created scenario '{forecasted_scenario.name}'")
    print(f"  * Daily Input Mass: {forecasted_scenario.daily_waste_generation.value:.2f} tonnes")

    # Step 5: Execute Simulation through Deterministic Physics Engine
    print("\n[Step 5] Simulating Physical Flows via EcoTwinEngine...")
    result = forecasted_scenario.run(energy_output_unit=EnergyUnit.MWH)
    print(result.format_report())


if __name__ == "__main__":
    run_forecasting_pipeline()

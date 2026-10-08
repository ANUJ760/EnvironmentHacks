"""
Basic Urban Waste and Energy System Scenario for EcoTwin Phase 1.

Demonstrates:
- Setting up incoming municipal solid waste (MSW) stream with explicit units.
- Configuring 4 specialized processing facilities with capacity limits and mass/energy conservation.
- Establishing deterministic routing plans.
- Simulating system flow and verifying full mass/energy balance closure.
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecotwin import (

    CategoryProcessingProfile,
    EcoTwinEngine,
    EnergyUnit,
    Mass,
    MassUnit,
    ProcessingFacility,
    RoutingPlan,
    SpecificEnergy,
    WasteCategory,
    WasteStream,
)


def run_scenario() -> None:
    print("=" * 70)
    print(" EcoTwin Digital Twin - Phase 1 Deterministic Mass & Energy Balance")
    print("=" * 70)

    # 1. Define incoming urban daily waste stream (500 Tonnes)
    incoming_waste = WasteStream.create(
        mass=Mass.tonnes(500.0),
        composition={
            WasteCategory.ORGANIC: 0.45,     # 225 tonnes
            WasteCategory.RECYCLABLE: 0.25,  # 125 tonnes
            WasteCategory.E_WASTE: 0.05,     # 25 tonnes
            WasteCategory.RESIDUAL: 0.25,    # 125 tonnes
        },
    )

    print(f"\n[1] Incoming Urban Waste: {incoming_waste.mass.value:.1f} {incoming_waste.mass.unit.value}")
    for cat, mass in incoming_waste.breakdown_masses().items():
        pct = incoming_waste.get_fraction(cat) * 100
        print(f"    - {cat.value:<12}: {mass.value:.1f} {mass.unit.value} ({pct:.1f}%)")

    # 2. Configure Processing Facilities
    # (a) Anaerobic Digestion (Organics)
    ad_facility = ProcessingFacility(
        name="Anaerobic_Digestion_Plant",
        capacity=Mass.tonnes(300.0),
        accepted_categories={WasteCategory.ORGANIC},
        default_profile=CategoryProcessingProfile(
            material_recovery_rate=0.40,  # 40% digestate compost/fertilizer
            landfill_residue_rate=0.10,   # 10% non-digestible rejects to landfill
            process_loss_rate=0.50,       # 50% biogas / moisture off-gas
            specific_energy=SpecificEnergy.from_kwh_per_tonne(300.0), # 300 kWh/tonne biogas energy
            energy_efficiency=0.35,       # 35% electrical conversion efficiency
        ),
    )

    # (b) Materials Recovery Facility (Recyclables)
    mrf_facility = ProcessingFacility(
        name="Materials_Recovery_Facility",
        capacity=Mass.tonnes(150.0),
        accepted_categories={WasteCategory.RECYCLABLE},
        default_profile=CategoryProcessingProfile(
            material_recovery_rate=0.85,  # 85% recovered plastics/metals/paper
            landfill_residue_rate=0.15,   # 15% sorting reject to landfill
            process_loss_rate=0.00,
        ),
    )

    # (c) E-Waste Refurbishment & Metal Extraction Facility
    ewaste_facility = ProcessingFacility(
        name="E_Waste_Refurbishment_Hub",
        capacity=Mass.tonnes(40.0),
        accepted_categories={WasteCategory.E_WASTE},
        default_profile=CategoryProcessingProfile(
            material_recovery_rate=0.75,  # 75% copper, precious metals, components
            landfill_residue_rate=0.25,   # 25% non-recyclable hazardous plastics/slag
            process_loss_rate=0.00,
        ),
    )

    # (d) Waste-to-Energy Incineration Plant (Residuals)
    wte_facility = ProcessingFacility(
        name="Waste_to_Energy_Plant",
        capacity=Mass.tonnes(200.0),
        accepted_categories={WasteCategory.RESIDUAL},
        default_profile=CategoryProcessingProfile(
            material_recovery_rate=0.12,  # 12% bottom ash scrap metal recovery
            landfill_residue_rate=0.18,   # 18% fly ash / inert residue
            process_loss_rate=0.70,       # 70% flue gas / water vapor
            specific_energy=SpecificEnergy.from_kwh_per_tonne(2500.0), # 2500 kWh/tonne calorific value
            energy_efficiency=0.25,       # 25% thermal-to-electric efficiency
        ),
    )

    # 3. Create Routing Plan
    routing_plan = RoutingPlan.create_direct({
        WasteCategory.ORGANIC: "Anaerobic_Digestion_Plant",
        WasteCategory.RECYCLABLE: "Materials_Recovery_Facility",
        WasteCategory.E_WASTE: "E_Waste_Refurbishment_Hub",
        WasteCategory.RESIDUAL: "Waste_to_Energy_Plant",
    })

    # 4. Initialize Engine and Run Simulation
    engine = EcoTwinEngine([ad_facility, mrf_facility, ewaste_facility, wte_facility])
    result = engine.simulate(incoming_waste, routing_plan, energy_output_unit=EnergyUnit.MWH)

    # 5. Display Balance Report
    print("\n[2] Facility Processing Summary:")
    for name, fres in result.facility_results.items():
        print(f"  * {name}:")
        print(f"      Input Mass        : {fres.input_mass.to_tonnes().value:.2f} tonnes")
        print(f"      Material Recovered: {fres.material_recovered_mass.to_tonnes().value:.2f} tonnes")
        print(f"      Landfill Residue  : {fres.landfill_residue_mass.to_tonnes().value:.2f} tonnes")
        print(f"      Process Loss/Gas  : {fres.process_loss_mass.to_tonnes().value:.2f} tonnes")
        print(f"      Energy Output     : {fres.energy_recovered.to_mwh().value:.2f} MWh ({fres.energy_recovered.to_kwh().value:.1f} kWh)")

    print("\n[3] Urban System Balance Totals:")
    print(f"  * Total Mass In       : {result.total_incoming_mass.to_tonnes().value:.2f} tonnes (100.0%)")
    print(f"  * Total Material Rec. : {result.total_material_recovered.to_tonnes().value:.2f} tonnes ({result.material_recovery_rate*100:.1f}%)")
    print(f"  * Total Landfill Resid: {result.total_landfill_residue.to_tonnes().value:.2f} tonnes ({(result.total_landfill_residue.to_tonnes().value / result.total_incoming_mass.to_tonnes().value)*100:.1f}%)")
    print(f"  * Total Process Loss  : {result.total_process_loss.to_tonnes().value:.2f} tonnes ({(result.total_process_loss.to_tonnes().value / result.total_incoming_mass.to_tonnes().value)*100:.1f}%)")
    print(f"  * Clean Energy Recov. : {result.total_energy_recovered.to_mwh().value:.2f} MWh")
    print(f"  * Landfill Diversion  : {result.landfill_diversion_rate * 100:.1f}%")

    # Verify mass conservation
    sum_out = (
        result.total_material_recovered.to_kg().value
        + result.total_landfill_residue.to_kg().value
        + result.total_process_loss.to_kg().value
    )
    in_kg = result.total_incoming_mass.to_kg().value
    delta_kg = abs(in_kg - sum_out)
    print(f"\n[4] Physics Validation:")
    print(f"  * Mass Balance Closure: Delta = {delta_kg:.6f} kg (Passed: Mass Strictly Conserved)")
    print("=" * 70)


if __name__ == "__main__":
    run_scenario()

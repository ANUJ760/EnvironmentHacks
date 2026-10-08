"""
Phase 2 Baseline Urban Scenario Runner for EcoTwin.

Demonstrates:
- Instantiating and validating the deterministic synthetic baseline scenario.
- Simulating urban waste flow through EcoTwinEngine.
- Generating a structured system-level execution result.
- Reporting recovery rates, diversion rates, facility utilization, and physics mass-balance closure.
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecotwin import (

    EnergyUnit,
    generate_baseline_scenario,
    generate_synthetic_city_scenario,
)


def main() -> None:
    print("=" * 72)
    print(" EcoTwin Phase 2: Urban Scenario & Baseline Data Layer")
    print("=" * 72)

    # 1. Generate the synthetic metropolis baseline scenario
    scenario = generate_baseline_scenario()
    print(f"\n[1] Loaded Scenario: '{scenario.name}'")
    print(f"    - Description       : {scenario.description}")
    print(f"    - Daily Generation  : {scenario.daily_waste_generation.value:.1f} {scenario.daily_waste_generation.unit.value}")
    print(f"    - Population        : {scenario.metadata.get('population', 'N/A'):,}")
    print("    - Composition Breakdown:")
    for cat, frac in scenario.composition.items():
        mass = scenario.daily_waste_generation * frac
        print(f"        * {cat.value:<12}: {mass.value:.1f} tonnes ({frac * 100:.1f}%)")

    print("\n    - Configured Facilities:")
    for fac_name, fac in scenario.facilities.items():
        accepted = [c.value for c in fac.accepted_categories] if fac.accepted_categories else "all"
        print(f"        * {fac_name:<28} (Cap: {fac.capacity.to_tonnes().value:.1f} t, Accepts: {accepted})")

    # 2. Execute scenario simulation
    print("\n[2] Executing Simulation Run via EcoTwinEngine...")
    result = scenario.run(energy_output_unit=EnergyUnit.MWH)

    # 3. Print formatted human-readable report
    print(result.format_report())


if __name__ == "__main__":
    main()

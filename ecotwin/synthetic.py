"""Deterministic synthetic urban waste scenarios and baseline generator for EcoTwin.

All synthetic values, compositions, and facility parameters in this module are clearly
identified as benchmark modeling assumptions and do not represent empirical real-world city data.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from ecotwin.categories import WasteCategory
from ecotwin.facility import CategoryProcessingProfile, ProcessingFacility
from ecotwin.routing import RoutingPlan
from ecotwin.scenario import UrbanScenario
from ecotwin.units import Mass, SpecificEnergy


# Benchmark assumptions notice attached to all synthetic scenarios
SYNTHETIC_ASSUMPTION_NOTICE = (
    "ASSUMPTION: Synthetic urban waste configuration modeled for simulation benchmarking. "
    "All generation rates, category fractions, and facility conversion efficiencies are "
    "engineering assumptions and do not represent empirical municipal data."
)


def generate_baseline_scenario(
    name: str = "Metropolis_Baseline_2026",
    daily_waste_generation: Optional[Mass] = None,
    population: int = 1_000_000,
) -> UrbanScenario:
    """
    Generates a deterministic baseline synthetic scenario for a mid-to-large metropolis.

    System Configuration:
    - Daily generation: 1,000 tonnes/day (~1.0 kg/capita/day for 1,000,000 inhabitants)
    - Composition:
        * Organic:    45% (450 tonnes/day) -> Anaerobic Digestion Plant
        * Recyclable: 25% (250 tonnes/day) -> Materials Recovery Facility
        * E-Waste:     5% ( 50 tonnes/day) -> E-Waste Refurbishment Hub
        * Residual:   25% (250 tonnes/day) -> Waste-to-Energy Plant
    - Facilities configured with adequate reserve capacity:
        * Anaerobic Digestion Plant: 500 tonnes/day capacity
        * Materials Recovery Facility: 300 tonnes/day capacity
        * E-Waste Refurbishment Hub: 65 tonnes/day capacity
        * Waste-to-Energy Plant: 300 tonnes/day capacity
    """
    total_waste = daily_waste_generation if daily_waste_generation is not None else Mass.tonnes(1000.0)

    # 1. Processing facilities with realistic conversion physics
    ad_facility = ProcessingFacility(
        name="Anaerobic_Digestion_Plant",
        capacity=Mass.tonnes(500.0),
        accepted_categories={WasteCategory.ORGANIC},
        default_profile=CategoryProcessingProfile(
            material_recovery_rate=0.45,  # 45% digestate compost/soil conditioner
            landfill_residue_rate=0.10,   # 10% non-digestible sorting reject
            process_loss_rate=0.45,       # 45% biogas/moisture loss
            specific_energy=SpecificEnergy.from_kwh_per_tonne(320.0), # 320 kWh/t biogas yield
            energy_efficiency=0.38,       # 38% electrical generation efficiency
        ),
    )

    mrf_facility = ProcessingFacility(
        name="Materials_Recovery_Facility",
        capacity=Mass.tonnes(300.0),
        accepted_categories={WasteCategory.RECYCLABLE},
        default_profile=CategoryProcessingProfile(
            material_recovery_rate=0.82,  # 82% recovered high-grade plastics/paper/metals
            landfill_residue_rate=0.18,   # 18% contaminated sorting residue to landfill
            process_loss_rate=0.00,
        ),
    )

    ewaste_facility = ProcessingFacility(
        name="E_Waste_Refurbishment_Hub",
        capacity=Mass.tonnes(65.0),
        accepted_categories={WasteCategory.E_WASTE},
        default_profile=CategoryProcessingProfile(
            material_recovery_rate=0.72,  # 72% recovered circuit components, copper, precious metals
            landfill_residue_rate=0.28,   # 28% non-recoverable hazardous residue/slag
            process_loss_rate=0.00,
        ),
    )

    wte_facility = ProcessingFacility(
        name="Waste_to_Energy_Plant",
        capacity=Mass.tonnes(300.0),
        accepted_categories={WasteCategory.RESIDUAL},
        default_profile=CategoryProcessingProfile(
            material_recovery_rate=0.12,  # 12% bottom ash ferrous/non-ferrous metals
            landfill_residue_rate=0.18,   # 18% fly ash / inert vitrified residue
            process_loss_rate=0.70,       # 70% thermal combustion off-gas / flue vapor
            specific_energy=SpecificEnergy.from_kwh_per_tonne(2400.0), # 2400 kWh/t calorific value
            energy_efficiency=0.25,       # 25% net steam-to-electricity efficiency
        ),
    )

    # 2. Direct 100% routing to respective specialized facilities
    routing_plan = RoutingPlan.create_direct({
        WasteCategory.ORGANIC: "Anaerobic_Digestion_Plant",
        WasteCategory.RECYCLABLE: "Materials_Recovery_Facility",
        WasteCategory.E_WASTE: "E_Waste_Refurbishment_Hub",
        WasteCategory.RESIDUAL: "Waste_to_Energy_Plant",
    })

    metadata: Dict[str, Any] = {
        "is_synthetic": True,
        "population": population,
        "per_capita_daily_kg": round(total_waste.to_kg().value / population, 2) if population > 0 else 0.0,
        "assumptions": {
            "notice": SYNTHETIC_ASSUMPTION_NOTICE,
            "organic_biogas_yield": "320 kWh/tonne biogas potential, 38% electrical efficiency",
            "mrf_sorting_efficiency": "82% recovery, 18% contamination reject",
            "ewaste_recovery": "72% precious metal/parts recovery, 28% hazardous residue",
            "wte_thermal_efficiency": "2400 kWh/tonne LHV, 25% net electric efficiency, 12% ash scrap recovery",
        },
    }

    return UrbanScenario.create(
        name=name,
        daily_waste_generation=total_waste,
        composition={
            WasteCategory.ORGANIC: 0.45,
            WasteCategory.RECYCLABLE: 0.25,
            WasteCategory.E_WASTE: 0.05,
            WasteCategory.RESIDUAL: 0.25,
        },
        facilities=[ad_facility, mrf_facility, ewaste_facility, wte_facility],
        routing_plan=routing_plan,
        metadata=metadata,
        description="Synthetic metropolis baseline scenario representing a modern integrated urban waste network.",
    )


def generate_synthetic_city_scenario(
    preset: str = "metropolis",
    name: Optional[str] = None,
    daily_waste_generation: Optional[Mass] = None,
    population: int = 1_000_000,
) -> UrbanScenario:
    """
    Generates synthetic city scenarios based on predefined archetype presets.

    Available presets:
    - 'metropolis': Standard integrated urban waste system (1000 t/day baseline).
    - 'high_diversion': Advanced source separation and high-capacity organics/recycling.
    - 'eco_district': Compact urban district with 200 t/day decentralized recovery.
    """
    preset_lower = preset.strip().lower()

    if preset_lower in ("metropolis", "baseline"):
        scenario_name = name or "Synthetic_Metropolis_Baseline"
        return generate_baseline_scenario(
            name=scenario_name,
            daily_waste_generation=daily_waste_generation,
            population=population,
        )

    elif preset_lower in ("high_diversion", "green_city"):
        scenario_name = name or "Synthetic_High_Diversion_City"
        total_waste = daily_waste_generation if daily_waste_generation is not None else Mass.tonnes(800.0)

        compost_fac = ProcessingFacility(
            name="Advanced_Composting_Center",
            capacity=Mass.tonnes(500.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.55,  # High compost yield
                landfill_residue_rate=0.05,   # Low reject due to high source segregation
                process_loss_rate=0.40,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(200.0),
                energy_efficiency=0.35,
            ),
        )

        mrf_fac = ProcessingFacility(
            name="Automated_Optical_MRF",
            capacity=Mass.tonnes(300.0),
            accepted_categories={WasteCategory.RECYCLABLE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.90,  # 90% optical recovery
                landfill_residue_rate=0.10,
                process_loss_rate=0.00,
            ),
        )

        ewaste_fac = ProcessingFacility(
            name="Circular_Electronics_Hub",
            capacity=Mass.tonnes(50.0),
            accepted_categories={WasteCategory.E_WASTE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.80,
                landfill_residue_rate=0.20,
                process_loss_rate=0.00,
            ),
        )

        wte_fac = ProcessingFacility(
            name="Residual_Gasification_Plant",
            capacity=Mass.tonnes(150.0),
            accepted_categories={WasteCategory.RESIDUAL},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.10,
                landfill_residue_rate=0.15,
                process_loss_rate=0.75,
                specific_energy=SpecificEnergy.from_kwh_per_tonne(2600.0),
                energy_efficiency=0.30,
            ),
        )

        routing = RoutingPlan.create_direct({
            WasteCategory.ORGANIC: "Advanced_Composting_Center",
            WasteCategory.RECYCLABLE: "Automated_Optical_MRF",
            WasteCategory.E_WASTE: "Circular_Electronics_Hub",
            WasteCategory.RESIDUAL: "Residual_Gasification_Plant",
        })

        metadata = {
            "is_synthetic": True,
            "preset": "high_diversion",
            "population": population,
            "assumptions": {
                "notice": SYNTHETIC_ASSUMPTION_NOTICE,
                "strategy": "High source segregation with advanced automated sorting and composting.",
            },
        }

        return UrbanScenario.create(
            name=scenario_name,
            daily_waste_generation=total_waste,
            composition={
                WasteCategory.ORGANIC: 0.50,     # 400 t
                WasteCategory.RECYCLABLE: 0.30,  # 240 t
                WasteCategory.E_WASTE: 0.05,     # 40 t
                WasteCategory.RESIDUAL: 0.15,    # 120 t
            },
            facilities=[compost_fac, mrf_fac, ewaste_fac, wte_fac],
            routing_plan=routing,
            metadata=metadata,
            description="Synthetic high-diversion scenario with intensive recycling and organics composting.",
        )

    elif preset_lower in ("eco_district", "district"):
        scenario_name = name or "Synthetic_Eco_District"
        total_waste = daily_waste_generation if daily_waste_generation is not None else Mass.tonnes(200.0)

        compost_fac = ProcessingFacility(
            name="Community_Composter",
            capacity=Mass.tonnes(120.0),
            accepted_categories={WasteCategory.ORGANIC},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.50,
                landfill_residue_rate=0.10,
                process_loss_rate=0.40,
            ),
        )

        mrf_fac = ProcessingFacility(
            name="District_Recycling_Depot",
            capacity=Mass.tonnes(80.0),
            accepted_categories={WasteCategory.RECYCLABLE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.85,
                landfill_residue_rate=0.15,
                process_loss_rate=0.00,
            ),
        )

        residual_fac = ProcessingFacility(
            name="Municipal_Landfill_Transfer",
            capacity=Mass.tonnes(80.0),
            accepted_categories={WasteCategory.RESIDUAL, WasteCategory.E_WASTE},
            default_profile=CategoryProcessingProfile(
                material_recovery_rate=0.00,
                landfill_residue_rate=1.00,
                process_loss_rate=0.00,
            ),
        )

        routing = RoutingPlan.create_direct({
            WasteCategory.ORGANIC: "Community_Composter",
            WasteCategory.RECYCLABLE: "District_Recycling_Depot",
            WasteCategory.E_WASTE: "Municipal_Landfill_Transfer",
            WasteCategory.RESIDUAL: "Municipal_Landfill_Transfer",
        })

        metadata = {
            "is_synthetic": True,
            "preset": "eco_district",
            "assumptions": {
                "notice": SYNTHETIC_ASSUMPTION_NOTICE,
                "strategy": "Decentralized community composting and recycling with transfer for residual/e-waste.",
            },
        }

        return UrbanScenario.create(
            name=scenario_name,
            daily_waste_generation=total_waste,
            composition={
                WasteCategory.ORGANIC: 0.45,
                WasteCategory.RECYCLABLE: 0.30,
                WasteCategory.E_WASTE: 0.05,
                WasteCategory.RESIDUAL: 0.20,
            },
            facilities=[compost_fac, mrf_fac, residual_fac],
            routing_plan=routing,
            metadata=metadata,
            description="Synthetic compact eco-district scenario with localized composting and recycling.",
        )

    else:
        raise ValueError(f"Unknown synthetic scenario preset: '{preset}'. Available: ['metropolis', 'high_diversion', 'eco_district']")

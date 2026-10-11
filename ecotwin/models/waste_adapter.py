from ecotwin.categories import WasteCategory
from ecotwin.errors import TwinError
from ecotwin.facility import CategoryProcessingProfile, ProcessingFacility
from ecotwin.ingestion.waste_import import validate_waste
from ecotwin.scenario import UrbanScenario
from ecotwin.units import Mass, SpecificEnergy


def build_scenario(document, routes=None):
    validate_waste(document)
    facilities = []
    for row in document["facilities"]:
        profiles = {}
        for name, profile in row["profiles"].items():
            profiles[WasteCategory.from_str(name)] = CategoryProcessingProfile(
                material_recovery_rate=profile["material_recovery_rate"],
                landfill_residue_rate=profile["landfill_residue_rate"],
                process_loss_rate=profile["process_loss_rate"],
                specific_energy=SpecificEnergy.from_kwh_per_tonne(
                    profile["specific_energy_kwh_per_tonne"]
                ),
                energy_efficiency=profile["energy_efficiency"],
            )
        if not profiles:
            raise TwinError("INSUFFICIENT_INPUT_DATA", "Facility processing profiles required")
        facilities.append(
            ProcessingFacility(
                name=row["facility_id"],
                capacity=Mass.tonnes(row["capacity_tpd"]),
                default_profile=next(iter(profiles.values())),
                category_profiles=profiles,
                accepted_categories={WasteCategory.from_str(c) for c in row["accepted_categories"]},
            )
        )
    return UrbanScenario.create(
        name="city-waste-scenario",
        daily_waste_generation=Mass.tonnes(document["daily_waste_tonnes"]),
        composition=document["composition"],
        facilities=facilities,
        routing_plan=routes or document["routing"],
        metadata={
            "measurement_type": document["measurement_type"],
            "source_url": document["source_url"],
        },
    )


def waste_metrics(scenario):
    result = scenario.run()
    return {
        "waste_processed_kg": result.total_waste_processed.to_kg().value,
        "material_recovered_kg": result.total_material_recovered.to_kg().value,
        "landfill_residue_kg": result.total_landfill_residue.to_kg().value,
        "process_loss_kg": result.total_process_loss.to_kg().value,
        "energy_recovered_kwh": result.total_energy_recovered.to_kwh().value,
        "mass_balance_error_kg": result.mass_balance_error_kg,
    }

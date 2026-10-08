"""System-level mass and energy balance calculation engine."""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Dict, Mapping, Sequence

from ecotwin.categories import WasteCategory
from ecotwin.exceptions import CapacityExceededError, PhysicsViolationError
from ecotwin.facility import FacilityResult, ProcessingFacility
from ecotwin.routing import RoutingPlan
from ecotwin.stream import WasteStream
from ecotwin.units import Energy, EnergyUnit, Mass, MassUnit


@dataclass(frozen=True)
class SystemBalanceResult:
    """
    Complete deterministic mass and energy balance report for the urban system.
    
    Invariants:
    1. Total mass input == Material Recovered + Landfill Residue + Process Loss.
    2. Facility capacities respected.
    3. Energy outputs derived deterministically from processed mass * specific energy * efficiency.
    """

    incoming_stream: WasteStream
    facility_results: Dict[str, FacilityResult]
    total_material_recovered: Mass
    total_landfill_residue: Mass
    total_process_loss: Mass
    total_energy_recovered: Energy

    def __post_init__(self) -> None:
        in_kg = self.incoming_stream.mass.to_kg().value
        out_kg = (
            self.total_material_recovered.to_kg().value
            + self.total_landfill_residue.to_kg().value
            + self.total_process_loss.to_kg().value
        )
        if not math.isclose(in_kg, out_kg, rel_tol=1e-5, abs_tol=1e-5):
            raise PhysicsViolationError(
                f"Global system mass balance violation: Total incoming mass ({in_kg:.4f} kg) "
                f"does not equal total outputs ({out_kg:.4f} kg = "
                f"{self.total_material_recovered.to_kg().value:.4f} kg recovered + "
                f"{self.total_landfill_residue.to_kg().value:.4f} kg landfill + "
                f"{self.total_process_loss.to_kg().value:.4f} kg loss)."
            )

    @property
    def total_incoming_mass(self) -> Mass:
        return self.incoming_stream.mass

    @property
    def material_recovery_rate(self) -> float:
        """Fraction of total waste mass recovered as usable materials."""
        in_kg = self.incoming_stream.mass.to_kg().value
        if in_kg == 0.0:
            return 0.0
        return self.total_material_recovered.to_kg().value / in_kg

    @property
    def landfill_diversion_rate(self) -> float:
        """Fraction of total waste mass diverted from landfill."""
        in_kg = self.incoming_stream.mass.to_kg().value
        if in_kg == 0.0:
            return 0.0
        landfill_kg = self.total_landfill_residue.to_kg().value
        return max(0.0, 1.0 - (landfill_kg / in_kg))

    def category_recovery_summary(self) -> Dict[WasteCategory, Mass]:
        """Aggregate material recovered by waste category across all facilities."""
        cat_recovered: Dict[WasteCategory, Mass] = {
            cat: Mass.zero(self.incoming_stream.mass.unit) for cat in WasteCategory
        }
        for res in self.facility_results.values():
            for cat, m in res.category_material_recovered.items():
                cat_recovered[cat] = cat_recovered[cat] + m
        return cat_recovered

    def summary(self) -> Dict[str, float | str | dict]:
        """Returns a clean structured dictionary summarizing the simulation run."""
        unit_m = self.incoming_stream.mass.unit.value
        unit_e = self.total_energy_recovered.unit.value
        return {
            "incoming_mass": f"{self.incoming_stream.mass.value:.2f} {unit_m}",
            "material_recovered_mass": f"{self.total_material_recovered.as_unit(self.incoming_stream.mass.unit).value:.2f} {unit_m}",
            "landfill_residue_mass": f"{self.total_landfill_residue.as_unit(self.incoming_stream.mass.unit).value:.2f} {unit_m}",
            "process_loss_mass": f"{self.total_process_loss.as_unit(self.incoming_stream.mass.unit).value:.2f} {unit_m}",
            "energy_recovered": f"{self.total_energy_recovered.value:.2f} {unit_e}",
            "material_recovery_rate_pct": round(self.material_recovery_rate * 100.0, 2),
            "landfill_diversion_rate_pct": round(self.landfill_diversion_rate * 100.0, 2),
            "facilities": {
                name: {
                    "input_mass": f"{res.input_mass.as_unit(self.incoming_stream.mass.unit).value:.2f} {unit_m}",
                    "material_recovered": f"{res.material_recovered_mass.as_unit(self.incoming_stream.mass.unit).value:.2f} {unit_m}",
                    "landfill_residue": f"{res.landfill_residue_mass.as_unit(self.incoming_stream.mass.unit).value:.2f} {unit_m}",
                    "process_loss": f"{res.process_loss_mass.as_unit(self.incoming_stream.mass.unit).value:.2f} {unit_m}",
                    "energy_recovered": f"{res.energy_recovered.value:.2f} {res.energy_recovered.unit.value}",
                }
                for name, res in self.facility_results.items()
            },
        }


class EcoTwinEngine:
    """
    Deterministic mass and energy balance execution engine.
    """

    def __init__(self, facilities: Sequence[ProcessingFacility] | Mapping[str, ProcessingFacility]):
        if isinstance(facilities, Mapping):
            self._facilities = dict(facilities)
        else:
            self._facilities = {f.name: f for f in facilities}

    @property
    def facilities(self) -> Dict[str, ProcessingFacility]:
        return dict(self._facilities)

    def get_facility(self, name: str) -> ProcessingFacility:
        if name not in self._facilities:
            raise KeyError(f"Facility '{name}' not found in engine.")
        return self._facilities[name]

    def simulate(
        self,
        incoming_stream: WasteStream,
        routing_plan: RoutingPlan,
        energy_output_unit: EnergyUnit = EnergyUnit.MWH,
    ) -> SystemBalanceResult:
        """
        Executes routing and facility processing, verifying global mass/energy balance.
        """
        # Route waste stream to facilities
        routed_streams = routing_plan.route_stream(incoming_stream, self._facilities)

        facility_results: Dict[str, FacilityResult] = {}
        total_mat = Mass.zero(incoming_stream.mass.unit)
        total_landfill = Mass.zero(incoming_stream.mass.unit)
        total_loss = Mass.zero(incoming_stream.mass.unit)
        total_energy = Energy.zero(energy_output_unit)

        for fac_name, fac in self._facilities.items():
            fac_stream = routed_streams.get(fac_name)
            if fac_stream is None:
                fac_stream = WasteStream(
                    mass=Mass.zero(incoming_stream.mass.unit),
                    composition={c: 0.25 for c in WasteCategory},
                )
            res = fac.process(fac_stream, energy_output_unit=energy_output_unit)
            facility_results[fac_name] = res

            total_mat = total_mat + res.material_recovered_mass
            total_landfill = total_landfill + res.landfill_residue_mass
            total_loss = total_loss + res.process_loss_mass
            total_energy = total_energy + res.energy_recovered

        return SystemBalanceResult(
            incoming_stream=incoming_stream,
            facility_results=facility_results,
            total_material_recovered=total_mat,
            total_landfill_residue=total_landfill,
            total_process_loss=total_loss,
            total_energy_recovered=total_energy,
        )

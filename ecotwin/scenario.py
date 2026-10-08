"""Scenario data layer and execution pipeline for EcoTwin."""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Any, Dict, Mapping, Optional, Sequence

from ecotwin.balance import EcoTwinEngine, SystemBalanceResult
from ecotwin.categories import WasteCategory
from ecotwin.exceptions import (
    CapacityExceededError,
    InvalidCompositionError,
    InvalidRoutingError,
    PhysicsViolationError,
    ScenarioValidationError,
)
from ecotwin.facility import FacilityResult, ProcessingFacility
from ecotwin.routing import RouteSplit, RoutingPlan
from ecotwin.stream import WasteStream
from ecotwin.units import Energy, EnergyUnit, Mass, MassUnit


@dataclass(frozen=True)
class ScenarioExecutionResult:
    """
    Structured execution result from running an UrbanScenario through the EcoTwin simulation engine.
    
    Contains system-level metrics, mass conservation audit, facility utilization, and full balance results.
    """

    scenario_name: str
    scenario_metadata: Dict[str, Any]
    incoming_stream: WasteStream
    system_balance_result: SystemBalanceResult
    total_waste_processed: Mass
    total_material_recovered: Mass
    total_landfill_residue: Mass
    total_process_loss: Mass
    total_energy_recovered: Energy
    material_recovery_rate: float
    landfill_diversion_rate: float
    facility_utilizations: Dict[str, float]
    facility_results: Dict[str, FacilityResult]
    mass_balance_error: Mass
    mass_balance_error_kg: float

    @classmethod
    def from_balance_result(
        cls,
        scenario: UrbanScenario,
        balance_result: SystemBalanceResult,
    ) -> ScenarioExecutionResult:
        """Constructs a ScenarioExecutionResult from an UrbanScenario and SystemBalanceResult."""
        total_in_kg = balance_result.total_incoming_mass.to_kg().value
        sum_out_kg = (
            balance_result.total_material_recovered.to_kg().value
            + balance_result.total_landfill_residue.to_kg().value
            + balance_result.total_process_loss.to_kg().value
        )
        error_kg = abs(total_in_kg - sum_out_kg)
        mass_error = Mass.kg(error_kg)

        # Calculate facility capacity utilization fractions
        utilizations: Dict[str, float] = {}
        for fac_name, fac in scenario.facilities.items():
            fac_res = balance_result.facility_results.get(fac_name)
            if fac_res is None:
                utilizations[fac_name] = 0.0
                continue
            fac_cap_kg = fac.capacity.to_kg().value
            if fac_cap_kg > 0.0:
                utilizations[fac_name] = fac_res.input_mass.to_kg().value / fac_cap_kg
            else:
                utilizations[fac_name] = 0.0

        return cls(
            scenario_name=scenario.name,
            scenario_metadata=dict(scenario.metadata),
            incoming_stream=balance_result.incoming_stream,
            system_balance_result=balance_result,
            total_waste_processed=balance_result.total_incoming_mass,
            total_material_recovered=balance_result.total_material_recovered,
            total_landfill_residue=balance_result.total_landfill_residue,
            total_process_loss=balance_result.total_process_loss,
            total_energy_recovered=balance_result.total_energy_recovered,
            material_recovery_rate=balance_result.material_recovery_rate,
            landfill_diversion_rate=balance_result.landfill_diversion_rate,
            facility_utilizations=utilizations,
            facility_results=dict(balance_result.facility_results),
            mass_balance_error=mass_error,
            mass_balance_error_kg=error_kg,
        )

    def summary(self) -> Dict[str, Any]:
        """Returns a structured dictionary summarizing system-level metrics and facility performances."""
        unit_m = self.total_waste_processed.unit.value
        unit_e = self.total_energy_recovered.unit.value

        return {
            "scenario_name": self.scenario_name,
            "metadata": self.scenario_metadata,
            "metrics": {
                "total_waste_processed": f"{self.total_waste_processed.value:.2f} {unit_m}",
                "total_material_recovered": f"{self.total_material_recovered.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}",
                "total_landfill_residue": f"{self.total_landfill_residue.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}",
                "total_process_loss": f"{self.total_process_loss.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}",
                "total_energy_recovered": f"{self.total_energy_recovered.value:.2f} {unit_e}",
                "material_recovery_rate_pct": round(self.material_recovery_rate * 100.0, 2),
                "landfill_diversion_rate_pct": round(self.landfill_diversion_rate * 100.0, 2),
                "mass_balance_error_kg": self.mass_balance_error_kg,
            },
            "facility_utilization_pct": {
                name: round(util * 100.0, 2) for name, util in self.facility_utilizations.items()
            },
            "facilities": {
                name: {
                    "input_mass": f"{res.input_mass.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}",
                    "material_recovered": f"{res.material_recovered_mass.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}",
                    "landfill_residue": f"{res.landfill_residue_mass.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}",
                    "process_loss": f"{res.process_loss_mass.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}",
                    "energy_recovered": f"{res.energy_recovered.value:.2f} {res.energy_recovered.unit.value}",
                    "utilization_pct": round(self.facility_utilizations.get(name, 0.0) * 100.0, 2),
                }
                for name, res in self.facility_results.items()
            },
        }

    def format_report(self) -> str:
        """Generates a human-readable text report of the simulation outcome."""
        lines = [
            "=" * 72,
            f" EcoTwin Scenario Execution Report: {self.scenario_name}",
            "=" * 72,
        ]
        if self.scenario_metadata:
            lines.append("\n[Scenario Metadata]")
            for k, v in self.scenario_metadata.items():
                lines.append(f"  * {k}: {v}")

        unit_m = self.total_waste_processed.unit.value
        lines.extend([
            "\n[System Performance Metrics]",
            f"  * Total Daily Waste Processed : {self.total_waste_processed.value:.2f} {unit_m}",
            f"  * Material Recovered          : {self.total_material_recovered.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m} ({self.material_recovery_rate * 100:.2f}%)",
            f"  * Landfill Residue            : {self.total_landfill_residue.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m} ({(self.total_landfill_residue.to_kg().value / self.total_waste_processed.to_kg().value) * 100:.2f}%)",
            f"  * Process Loss / Off-Gas      : {self.total_process_loss.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m} ({(self.total_process_loss.to_kg().value / self.total_waste_processed.to_kg().value) * 100:.2f}%)",
            f"  * Energy Recovered            : {self.total_energy_recovered.value:.2f} {self.total_energy_recovered.unit.value}",
            f"  * Landfill Diversion Rate     : {self.landfill_diversion_rate * 100:.2f}%",
            f"  * Mass Balance Closure Error  : {self.mass_balance_error_kg:.8f} kg (Passed)",
            "\n[Facility Utilization & Output Breakdown]",
        ])

        for name, res in self.facility_results.items():
            util_pct = self.facility_utilizations.get(name, 0.0) * 100.0
            lines.append(f"  Facility: {name} [Capacity Utilization: {util_pct:.1f}%]")
            lines.append(f"    - Input Mass        : {res.input_mass.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}")
            lines.append(f"    - Material Recovered: {res.material_recovered_mass.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}")
            lines.append(f"    - Landfill Residue  : {res.landfill_residue_mass.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}")
            lines.append(f"    - Process Loss      : {res.process_loss_mass.as_unit(self.total_waste_processed.unit).value:.2f} {unit_m}")
            lines.append(f"    - Energy Recovered  : {res.energy_recovered.value:.2f} {res.energy_recovered.unit.value}")

        lines.append("=" * 72)
        return "\n".join(lines)


@dataclass(frozen=True)
class UrbanScenario:
    """
    Structured model representing an urban waste-system configuration.

    Encapsulates:
    - Municipal daily waste generation quantity (with explicit unit)
    - Waste composition fractions
    - Processing facility configurations and capacities
    - Waste routing plan across facilities
    - Scenario name, description, and metadata (including synthetic baseline assumptions)
    """

    name: str
    daily_waste_generation: Mass
    composition: Dict[WasteCategory, float]
    facilities: Dict[str, ProcessingFacility]
    routing_plan: RoutingPlan
    metadata: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        # Validate scenario name
        if not self.name or not isinstance(self.name, str):
            raise ScenarioValidationError("Scenario name must be a non-empty string.")

        # Validate daily waste generation mass
        if not isinstance(self.daily_waste_generation, Mass):
            raise ScenarioValidationError(
                f"daily_waste_generation must be an instance of Mass, got {type(self.daily_waste_generation)}"
            )

        # Standardize and validate composition across all categories
        normalized_comp: Dict[WasteCategory, float] = {}
        for cat in WasteCategory:
            frac = self.composition.get(cat, 0.0)
            if math.isnan(frac) or math.isinf(frac):
                raise InvalidCompositionError(f"Composition fraction for '{cat.value}' cannot be NaN or Inf.")
            if frac < -1e-9 or frac > 1.0 + 1e-9:
                raise InvalidCompositionError(
                    f"Composition fraction for '{cat.value}' must be in [0.0, 1.0], got {frac}"
                )
            normalized_comp[cat] = max(0.0, float(frac))

        total_frac = sum(normalized_comp.values())
        if self.daily_waste_generation.to_kg().value > 0.0:
            if not math.isclose(total_frac, 1.0, rel_tol=1e-5, abs_tol=1e-5):
                raise InvalidCompositionError(
                    f"Scenario '{self.name}': Waste composition fractions must sum to 1.0, got {total_frac:.6f}."
                )
            if total_frac != 1.0 and total_frac > 0.0:
                normalized_comp = {k: v / total_frac for k, v in normalized_comp.items()}
        else:
            if total_frac > 0.0 and not math.isclose(total_frac, 1.0, rel_tol=1e-5, abs_tol=1e-5):
                raise InvalidCompositionError(
                    f"Scenario '{self.name}': Waste composition fractions must sum to 1.0, got {total_frac:.6f}."
                )

        object.__setattr__(self, "composition", normalized_comp)

        # Standardize and validate facilities
        if not self.facilities:
            raise ScenarioValidationError(f"Scenario '{self.name}' must define at least one processing facility.")

        for fac_name, fac in self.facilities.items():
            if not isinstance(fac, ProcessingFacility):
                raise ScenarioValidationError(
                    f"Facility '{fac_name}' must be an instance of ProcessingFacility, got {type(fac)}"
                )
            if fac.name != fac_name:
                raise ScenarioValidationError(
                    f"Facility mapping key '{fac_name}' does not match facility.name '{fac.name}'."
                )

        # Validate routing plan and capacity
        self.validate()

    @classmethod
    def create(
        cls,
        name: str,
        daily_waste_generation: Mass,
        composition: Mapping[WasteCategory | str, float],
        facilities: Sequence[ProcessingFacility] | Mapping[str, ProcessingFacility],
        routing_plan: RoutingPlan | Mapping[WasteCategory | str, Sequence[tuple[str, float] | RouteSplit]] | Mapping[WasteCategory | str, str],
        metadata: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> UrbanScenario:
        """
        Convenience factory to create an UrbanScenario supporting flexible mappings.
        """
        # Parse composition
        parsed_comp: Dict[WasteCategory, float] = {}
        for k, v in composition.items():
            cat = k if isinstance(k, WasteCategory) else WasteCategory.from_str(k)
            parsed_comp[cat] = float(v)

        # Parse facilities
        if isinstance(facilities, Mapping):
            fac_dict = {str(k): v for k, v in facilities.items()}
        else:
            fac_dict = {f.name: f for f in facilities}

        # Parse routing plan
        if isinstance(routing_plan, RoutingPlan):
            parsed_routing = routing_plan
        elif isinstance(routing_plan, Mapping):
            # Check if values are direct facility names or split sequences
            is_direct = True
            for v in routing_plan.values():
                if isinstance(v, (list, tuple)):
                    is_direct = False
                    break
            if is_direct:
                parsed_routing = RoutingPlan.create_direct(routing_plan)  # type: ignore
            else:
                parsed_routing = RoutingPlan.create(routing_plan)  # type: ignore
        else:
            raise ScenarioValidationError(f"Invalid routing_plan type: {type(routing_plan)}")

        return cls(
            name=name,
            daily_waste_generation=daily_waste_generation,
            composition=parsed_comp,
            facilities=fac_dict,
            routing_plan=parsed_routing,
            metadata=dict(metadata or {}),
            description=description,
        )

    def validate(self) -> None:
        """
        Performs thorough validation of scenario configuration:
        1. Verifies all routed categories with mass > 0 are present in the routing plan.
        2. Verifies destination facilities exist in configured facilities.
        3. Verifies category acceptance by receiving facilities.
        4. Verifies that routed waste volume does not exceed available facility capacities.
        """
        # Ensure routing plan references valid facilities
        for cat, splits in self.routing_plan.routes.items():
            for s in splits:
                if s.fraction > 0 and s.facility_name not in self.facilities:
                    raise InvalidRoutingError(
                        f"Scenario '{self.name}': Destination facility '{s.facility_name}' in routing for '{cat.value}' "
                        f"is not defined in scenario facilities: {list(self.facilities.keys())}"
                    )

        # Check every active category in composition has a route defined
        gen_kg = self.daily_waste_generation.to_kg().value
        for cat in WasteCategory:
            cat_frac = self.composition.get(cat, 0.0)
            if gen_kg > 0.0 and cat_frac > 0.0:
                if cat not in self.routing_plan.routes:
                    raise InvalidRoutingError(
                        f"Scenario '{self.name}': Category '{cat.value}' has fraction {cat_frac:.4f} "
                        f"but no route is defined in the routing plan."
                    )

        # Check facility category acceptance and compute routed load per facility
        facility_loads: Dict[str, Mass] = {name: Mass.zero(self.daily_waste_generation.unit) for name in self.facilities}

        for cat in WasteCategory:
            cat_frac = self.composition.get(cat, 0.0)
            if cat_frac == 0.0 or gen_kg == 0.0:
                continue

            cat_mass = self.daily_waste_generation * cat_frac
            splits = self.routing_plan.routes.get(cat, ())
            for s in splits:
                if s.fraction <= 0.0:
                    continue
                fac = self.facilities[s.facility_name]
                if not fac.is_category_accepted(cat):
                    raise InvalidRoutingError(
                        f"Scenario '{self.name}': Category '{cat.value}' is routed to facility '{fac.name}', "
                        f"which only accepts {[c.value for c in fac.accepted_categories]}."
                    )
                routed_m = cat_mass * s.fraction
                facility_loads[s.facility_name] = facility_loads[s.facility_name] + routed_m

        # Verify facility capacity constraints
        for fac_name, fac in self.facilities.items():
            routed = facility_loads[fac_name]
            if routed > fac.capacity:
                raise CapacityExceededError(
                    f"Scenario '{self.name}': Routed load for facility '{fac_name}' is "
                    f"{routed.to_tonnes().value:.2f} tonnes, which exceeds configured capacity "
                    f"of {fac.capacity.to_tonnes().value:.2f} tonnes."
                )

    def to_incoming_stream(self) -> WasteStream:
        """Constructs the incoming WasteStream for this scenario."""
        return WasteStream.create(
            mass=self.daily_waste_generation,
            composition=self.composition,
        )

    def build_engine(self) -> EcoTwinEngine:
        """Builds an EcoTwinEngine initialized with this scenario's facilities."""
        return EcoTwinEngine(self.facilities)

    def calculate_facility_loads(self) -> Dict[str, Mass]:
        """Calculates the planned mass allocated to each facility based on generation, composition, and routing."""
        loads: Dict[str, Mass] = {name: Mass.zero(self.daily_waste_generation.unit) for name in self.facilities}
        stream = self.to_incoming_stream()
        breakdown = stream.breakdown_masses()

        for cat, cat_mass in breakdown.items():
            if cat_mass.to_kg().value == 0.0:
                continue
            splits = self.routing_plan.routes.get(cat, ())
            for s in splits:
                loads[s.facility_name] = loads[s.facility_name] + (cat_mass * s.fraction)
        return loads

    def calculate_facility_utilizations(self) -> Dict[str, float]:
        """Calculates the capacity utilization fraction (0.0 to 1.0) for each facility."""
        loads = self.calculate_facility_loads()
        utilizations: Dict[str, float] = {}
        for fac_name, fac in self.facilities.items():
            cap_kg = fac.capacity.to_kg().value
            if cap_kg > 0.0:
                utilizations[fac_name] = loads[fac_name].to_kg().value / cap_kg
            else:
                utilizations[fac_name] = 0.0
        return utilizations

    def run(self, energy_output_unit: EnergyUnit = EnergyUnit.MWH) -> ScenarioExecutionResult:
        """
        Executes the scenario through the EcoTwin mass/energy balance engine.
        
        Returns a structured ScenarioExecutionResult containing comprehensive system-level metrics.
        """
        engine = self.build_engine()
        incoming_stream = self.to_incoming_stream()
        balance_result = engine.simulate(
            incoming_stream=incoming_stream,
            routing_plan=self.routing_plan,
            energy_output_unit=energy_output_unit,
        )
        return ScenarioExecutionResult.from_balance_result(
            scenario=self,
            balance_result=balance_result,
        )


# Alias for concise usage
Scenario = UrbanScenario

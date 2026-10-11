"""Processing facility models enforcing mass/energy balances and capacity constraints."""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Dict, Optional, Set, Tuple, Union

from ecotwin.categories import WasteCategory
from ecotwin.exceptions import CapacityExceededError, PhysicsViolationError
from ecotwin.stream import WasteStream
from ecotwin.units import Distance, Energy, EnergyUnit, Mass, MassUnit, SpecificEnergy


@dataclass(frozen=True)
class CategoryProcessingProfile:
    """
    Physical partitioning and energy parameters for a specific waste category within a facility.
    
    Mass conservation invariant:
    material_recovery_rate + landfill_residue_rate + process_loss_rate == 1.0
    """

    material_recovery_rate: float
    landfill_residue_rate: float
    process_loss_rate: float = 0.0
    specific_energy: SpecificEnergy = field(default_factory=SpecificEnergy.zero)
    energy_efficiency: float = 1.0

    def __post_init__(self) -> None:
        rates = [self.material_recovery_rate, self.landfill_residue_rate, self.process_loss_rate]
        for r in rates:
            if math.isnan(r) or math.isinf(r):
                raise PhysicsViolationError("Processing rates cannot be NaN or Inf.")
            if r < -1e-9 or r > 1.0 + 1e-9:
                raise PhysicsViolationError(f"Processing rates must be in [0, 1], got {r}")

        total_rate = sum(rates)
        if not math.isclose(total_rate, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            raise PhysicsViolationError(
                f"Mass conservation violation: sum of material recovery ({self.material_recovery_rate:.4f}), "
                f"landfill residue ({self.landfill_residue_rate:.4f}), and process loss ({self.process_loss_rate:.4f}) "
                f"must equal 1.0, but got {total_rate:.6f}."
            )

        if not (0.0 <= self.energy_efficiency <= 1.0):
            raise PhysicsViolationError(
                f"Energy conversion efficiency must be between 0.0 and 1.0, got {self.energy_efficiency}"
            )


@dataclass(frozen=True)
class FacilityResult:
    """
    Deterministic output report from processing a waste stream through a facility.
    All outputs strictly conserve mass and calculate energy output.
    """

    facility_name: str
    input_mass: Mass
    material_recovered_mass: Mass
    landfill_residue_mass: Mass
    process_loss_mass: Mass
    energy_recovered: Energy
    category_inputs: Dict[WasteCategory, Mass]
    category_material_recovered: Dict[WasteCategory, Mass]
    category_landfill_residue: Dict[WasteCategory, Mass]
    category_process_loss: Dict[WasteCategory, Mass]
    category_energy_recovered: Dict[WasteCategory, Energy]

    def __post_init__(self) -> None:
        # Enforce mass balance conservation verification on result
        sum_outputs_kg = (
            self.material_recovered_mass.to_kg().value
            + self.landfill_residue_mass.to_kg().value
            + self.process_loss_mass.to_kg().value
        )
        input_kg = self.input_mass.to_kg().value

        if not math.isclose(sum_outputs_kg, input_kg, rel_tol=1e-5, abs_tol=1e-5):
            raise PhysicsViolationError(
                f"Mass balance violation in facility '{self.facility_name}': "
                f"Input ({input_kg:.4f} kg) != Output ({sum_outputs_kg:.4f} kg)."
            )


@dataclass(frozen=True)
class ProcessingFacility:
    """
    A facility or processing path with defined capacity, accepted categories, conversion physics,
    and optional location/distance parameters.
    """

    name: str
    capacity: Mass
    default_profile: CategoryProcessingProfile
    category_profiles: Dict[WasteCategory, CategoryProcessingProfile] = field(default_factory=dict)
    accepted_categories: Optional[Set[WasteCategory]] = None
    distance: Optional[Union[Distance, float]] = None
    location: Optional[Tuple[float, float]] = None

    def __post_init__(self) -> None:
        if self.capacity.to_kg().value < 0:
            raise PhysicsViolationError(f"Facility capacity cannot be negative: {self.capacity}")
        if self.distance is not None:
            if isinstance(self.distance, (int, float)):
                object.__setattr__(self, "distance", Distance.km(float(self.distance)))
            elif not isinstance(self.distance, Distance):
                raise TypeError(f"distance must be a Distance or float, got {type(self.distance)}")
        if self.location is not None:
            if not (isinstance(self.location, (tuple, list)) and len(self.location) == 2):
                raise ValueError(f"Facility location must be a 2-tuple (x, y), got {self.location}")
            x, y = self.location
            if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
                raise ValueError(f"Facility location coordinates cannot be NaN or Inf: {self.location}")

    @property
    def distance_km(self) -> float:
        """Returns distance in km from source/collection centroid."""
        if self.distance is not None and isinstance(self.distance, Distance):
            return self.distance.to_km().value
        if self.location is not None:
            return float(math.hypot(self.location[0], self.location[1]))
        return 0.0

    @property
    def distance_quantity(self) -> Distance:
        """Returns distance as a typed Distance unit."""
        return Distance.km(self.distance_km)

    def get_profile_for_category(self, category: WasteCategory) -> CategoryProcessingProfile:
        return self.category_profiles.get(category, self.default_profile)

    def is_category_accepted(self, category: WasteCategory) -> bool:
        if self.accepted_categories is None:
            return True
        return category in self.accepted_categories

    def process(
        self,
        stream: WasteStream,
        energy_output_unit: EnergyUnit = EnergyUnit.KWH,
    ) -> FacilityResult:
        """
        Processes an incoming WasteStream deterministically.
        
        Enforces:
        1. Input mass <= facility capacity.
        2. Category acceptance verification.
        3. Strict conservation of mass.
        4. Energy calculation: mass * specific_energy * efficiency.
        """
        input_mass = stream.mass
        if input_mass > self.capacity:
            raise CapacityExceededError(
                f"Facility '{self.name}' capacity exceeded: incoming mass is "
                f"{input_mass.to_tonnes().value:.2f} tonnes, but capacity is {self.capacity.to_tonnes().value:.2f} tonnes."
            )

        cat_inputs: Dict[WasteCategory, Mass] = {}
        cat_mat: Dict[WasteCategory, Mass] = {}
        cat_landfill: Dict[WasteCategory, Mass] = {}
        cat_loss: Dict[WasteCategory, Mass] = {}
        cat_energy: Dict[WasteCategory, Energy] = {}

        total_mat = Mass.zero(input_mass.unit)
        total_landfill = Mass.zero(input_mass.unit)
        total_loss = Mass.zero(input_mass.unit)
        total_energy = Energy.zero(energy_output_unit)

        breakdown = stream.breakdown_masses()

        for cat, cat_mass in breakdown.items():
            if cat_mass.to_kg().value > 0.0 and not self.is_category_accepted(cat):
                raise PhysicsViolationError(
                    f"Facility '{self.name}' does not accept category '{cat.value}'."
                )

            cat_inputs[cat] = cat_mass
            if cat_mass.to_kg().value == 0.0:
                cat_mat[cat] = Mass.zero(input_mass.unit)
                cat_landfill[cat] = Mass.zero(input_mass.unit)
                cat_loss[cat] = Mass.zero(input_mass.unit)
                cat_energy[cat] = Energy.zero(energy_output_unit)
                continue

            profile = self.get_profile_for_category(cat)

            m_mat = cat_mass * profile.material_recovery_rate
            m_landfill = cat_mass * profile.landfill_residue_rate
            m_loss = cat_mass * profile.process_loss_rate

            # Check precision closure for this category
            m_sum_kg = m_mat.to_kg().value + m_landfill.to_kg().value + m_loss.to_kg().value
            if not math.isclose(m_sum_kg, cat_mass.to_kg().value, rel_tol=1e-6, abs_tol=1e-6):
                # Adjust rounding delta to process loss or landfill
                diff_kg = cat_mass.to_kg().value - m_sum_kg
                m_loss = m_loss + Mass.kg(diff_kg).as_unit(input_mass.unit)

            e_rec = profile.specific_energy.calculate_energy(
                mass=cat_mass,
                efficiency=profile.energy_efficiency,
                output_unit=energy_output_unit,
            )

            cat_mat[cat] = m_mat
            cat_landfill[cat] = m_landfill
            cat_loss[cat] = m_loss
            cat_energy[cat] = e_rec

            total_mat = total_mat + m_mat
            total_landfill = total_landfill + m_landfill
            total_loss = total_loss + m_loss
            total_energy = total_energy + e_rec

        return FacilityResult(
            facility_name=self.name,
            input_mass=input_mass,
            material_recovered_mass=total_mat,
            landfill_residue_mass=total_landfill,
            process_loss_mass=total_loss,
            energy_recovered=total_energy,
            category_inputs=cat_inputs,
            category_material_recovered=cat_mat,
            category_landfill_residue=cat_landfill,
            category_process_loss=cat_loss,
            category_energy_recovered=cat_energy,
        )

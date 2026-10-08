"""Waste stream modeling with composition fractions and mass distribution."""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Dict, Mapping

from ecotwin.categories import WasteCategory
from ecotwin.exceptions import InvalidCompositionError, PhysicsViolationError
from ecotwin.units import Mass, MassUnit


@dataclass(frozen=True)
class WasteStream:
    """
    Represents an incoming or circulating waste stream with total mass and category composition fractions.
    
    Physics invariants enforced:
    1. Total mass >= 0.
    2. Each category fraction >= 0.
    3. Sum of all category fractions == 1.0 (if mass > 0).
    """

    mass: Mass
    composition: Dict[WasteCategory, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Standardize composition to contain all categories
        normalized_comp: Dict[WasteCategory, float] = {}
        for cat in WasteCategory:
            frac = self.composition.get(cat, 0.0)
            if math.isnan(frac) or math.isinf(frac):
                raise InvalidCompositionError(f"Composition fraction for {cat.value} cannot be NaN or Inf.")
            if frac < -1e-9:
                raise InvalidCompositionError(
                    f"Composition fraction for {cat.value} cannot be negative: {frac}"
                )
            # Clip floating point micro-negatives
            normalized_comp[cat] = max(0.0, float(frac))

        total_frac = sum(normalized_comp.values())

        if self.mass.to_kg().value > 0.0:
            if not math.isclose(total_frac, 1.0, rel_tol=1e-5, abs_tol=1e-5):
                raise InvalidCompositionError(
                    f"Waste composition fractions must sum to 1.0, but got {total_frac:.6f} "
                    f"(details: { {k.value: v for k, v in normalized_comp.items()} })"
                )
            # Normalize slight floating precision deviation so exact sum is 1.0
            if total_frac != 1.0 and total_frac > 0.0:
                normalized_comp = {k: v / total_frac for k, v in normalized_comp.items()}
        else:
            # For 0 mass stream, if total_frac is 0, distribute evenly or keep 0
            if total_frac > 0.0 and not math.isclose(total_frac, 1.0, rel_tol=1e-5, abs_tol=1e-5):
                raise InvalidCompositionError(
                    f"Waste composition fractions must sum to 1.0, got {total_frac:.6f}"
                )

        object.__setattr__(self, "composition", normalized_comp)

    @classmethod
    def create(
        cls,
        mass: Mass,
        composition: Mapping[WasteCategory | str, float],
    ) -> WasteStream:
        """Factory method to construct a WasteStream supporting string keys or WasteCategory keys."""
        parsed_comp: Dict[WasteCategory, float] = {}
        for k, v in composition.items():
            cat = k if isinstance(k, WasteCategory) else WasteCategory.from_str(k)
            parsed_comp[cat] = float(v)
        return cls(mass=mass, composition=parsed_comp)

    @classmethod
    def single_category(cls, mass: Mass, category: WasteCategory | str) -> WasteStream:
        """Creates a stream consisting of 100% of a single waste category."""
        cat = category if isinstance(category, WasteCategory) else WasteCategory.from_str(category)
        return cls(mass=mass, composition={cat: 1.0})

    def get_fraction(self, category: WasteCategory | str) -> float:
        cat = category if isinstance(category, WasteCategory) else WasteCategory.from_str(category)
        return self.composition.get(cat, 0.0)

    def get_category_mass(self, category: WasteCategory | str) -> Mass:
        """Returns the mass of a specific category in this stream."""
        cat = category if isinstance(category, WasteCategory) else WasteCategory.from_str(category)
        frac = self.get_fraction(cat)
        return self.mass * frac

    def breakdown_masses(self) -> Dict[WasteCategory, Mass]:
        """Returns a mapping of each WasteCategory to its physical mass in the stream."""
        return {cat: self.get_category_mass(cat) for cat in WasteCategory}

    def split(self, fraction: float) -> WasteStream:
        """Splits off a portion of the stream (0.0 <= fraction <= 1.0)."""
        if not (0.0 <= fraction <= 1.0):
            raise PhysicsViolationError(f"Split fraction must be between 0.0 and 1.0, got {fraction}")
        return WasteStream(mass=self.mass * fraction, composition=dict(self.composition))

    def combine(self, other: WasteStream) -> WasteStream:
        """Combines two waste streams with conservation of total mass and mass-weighted composition."""
        if not isinstance(other, WasteStream):
            raise TypeError(f"Cannot combine WasteStream with {type(other)}")
        total_mass = self.mass + other.mass
        if total_mass.to_kg().value == 0.0:
            return WasteStream(mass=total_mass, composition={c: 0.25 for c in WasteCategory})

        self_kg = self.mass.to_kg().value
        other_kg = other.mass.to_kg().value
        total_kg = total_mass.to_kg().value

        combined_comp: Dict[WasteCategory, float] = {}
        for cat in WasteCategory:
            cat_kg = (self.get_fraction(cat) * self_kg) + (other.get_fraction(cat) * other_kg)
            combined_comp[cat] = cat_kg / total_kg

        return WasteStream(mass=total_mass, composition=combined_comp)

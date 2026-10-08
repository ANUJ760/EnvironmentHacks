"""Routing plan and waste stream distribution logic."""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Dict, Mapping, Optional, Sequence

from ecotwin.categories import WasteCategory
from ecotwin.exceptions import InvalidRoutingError, PhysicsViolationError
from ecotwin.facility import ProcessingFacility
from ecotwin.stream import WasteStream
from ecotwin.units import Mass


@dataclass(frozen=True)
class RouteSplit:
    """Designates a fraction of a waste category routed to a destination facility."""

    facility_name: str
    fraction: float

    def __post_init__(self) -> None:
        if math.isnan(self.fraction) or math.isinf(self.fraction):
            raise InvalidRoutingError("Routing fraction cannot be NaN or Inf.")
        if self.fraction < -1e-9 or self.fraction > 1.0 + 1e-9:
            raise InvalidRoutingError(f"Routing fraction must be in [0, 1], got {self.fraction}")


@dataclass(frozen=True)
class RoutingPlan:
    """
    Defines how each waste category is distributed across processing facilities.
    
    Invariants:
    1. For each mapped category, sum of routing split fractions must equal 1.0.
    2. All split fractions >= 0.0.
    """

    routes: Dict[WasteCategory, tuple[RouteSplit, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for cat, splits in self.routes.items():
            if not splits:
                continue
            total_split = sum(s.fraction for s in splits)
            if not math.isclose(total_split, 1.0, rel_tol=1e-5, abs_tol=1e-5):
                raise InvalidRoutingError(
                    f"Routing fractions for category '{cat.value}' must sum to 1.0, but got {total_split:.6f}."
                )

    @classmethod
    def create_direct(cls, mapping: Mapping[WasteCategory | str, str]) -> RoutingPlan:
        """Convenience factory: maps 100% of each specified category directly to named facility."""
        routes: Dict[WasteCategory, tuple[RouteSplit, ...]] = {}
        for k, facility_name in mapping.items():
            cat = k if isinstance(k, WasteCategory) else WasteCategory.from_str(k)
            routes[cat] = (RouteSplit(facility_name=facility_name, fraction=1.0),)
        return cls(routes=routes)

    @classmethod
    def create(cls, mapping: Mapping[WasteCategory | str, Sequence[tuple[str, float] | RouteSplit]]) -> RoutingPlan:
        """Flexible factory to construct a routing plan with split distributions."""
        routes: Dict[WasteCategory, tuple[RouteSplit, ...]] = {}
        for k, split_list in mapping.items():
            cat = k if isinstance(k, WasteCategory) else WasteCategory.from_str(k)
            parsed_splits = []
            for item in split_list:
                if isinstance(item, RouteSplit):
                    parsed_splits.append(item)
                else:
                    fac_name, frac = item
                    parsed_splits.append(RouteSplit(facility_name=fac_name, fraction=float(frac)))
            routes[cat] = tuple(parsed_splits)
        return cls(routes=routes)

    def route_stream(
        self,
        stream: WasteStream,
        facilities: Mapping[str, ProcessingFacility],
    ) -> Dict[str, WasteStream]:
        """
        Splits an incoming stream across destination facilities according to the routing plan.
        Returns a mapping of facility_name -> WasteStream allocated to that facility.
        """
        # Verify all destination facilities exist
        for cat, splits in self.routes.items():
            for s in splits:
                if s.fraction > 0 and s.facility_name not in facilities:
                    raise InvalidRoutingError(
                        f"Facility '{s.facility_name}' referenced in route for '{cat.value}' does not exist in system."
                    )

        # Ensure every category present in incoming stream with mass > 0 is routed
        cat_breakdown = stream.breakdown_masses()
        for cat, mass in cat_breakdown.items():
            if mass.to_kg().value > 0.0 and cat not in self.routes:
                raise InvalidRoutingError(
                    f"Waste stream contains category '{cat.value}' ({mass.to_tonnes().value:.2f} tonnes), "
                    f"but no routing rule is defined for this category in the routing plan."
                )

        facility_masses: Dict[str, Dict[WasteCategory, Mass]] = {fac_name: {} for fac_name in facilities}
        for fac_name in facilities:
            for cat in WasteCategory:
                facility_masses[fac_name][cat] = Mass.zero(stream.mass.unit)

        for cat, cat_mass in cat_breakdown.items():
            if cat_mass.to_kg().value == 0.0:
                continue
            splits = self.routes.get(cat, ())
            for s in splits:
                routed_mass = cat_mass * s.fraction
                facility_masses[s.facility_name][cat] = facility_masses[s.facility_name][cat] + routed_mass

        # Construct destination streams
        facility_streams: Dict[str, WasteStream] = {}
        for fac_name, cat_dict in facility_masses.items():
            fac_total_mass = sum((m for m in cat_dict.values()), Mass.zero(stream.mass.unit))
            if fac_total_mass.to_kg().value == 0.0:
                facility_streams[fac_name] = WasteStream(
                    mass=fac_total_mass,
                    composition={c: 0.25 for c in WasteCategory},
                )
            else:
                fac_comp: Dict[WasteCategory, float] = {}
                for cat, m in cat_dict.items():
                    fac_comp[cat] = m.to_kg().value / fac_total_mass.to_kg().value
                facility_streams[fac_name] = WasteStream(
                    mass=fac_total_mass,
                    composition=fac_comp,
                )

        # Physical mass conservation check across routed streams
        routed_total_kg = sum(s.mass.to_kg().value for s in facility_streams.values())
        incoming_total_kg = stream.mass.to_kg().value
        if not math.isclose(routed_total_kg, incoming_total_kg, rel_tol=1e-5, abs_tol=1e-5):
            raise PhysicsViolationError(
                f"Mass conservation violation during routing: Incoming ({incoming_total_kg:.4f} kg) "
                f"!= Total Routed ({routed_total_kg:.4f} kg)."
            )

        return facility_streams

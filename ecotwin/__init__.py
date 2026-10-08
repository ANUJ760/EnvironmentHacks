"""EcoTwin: Physics-Informed AI Digital Twin for Urban Waste & Energy Systems.

Phase 1: Core deterministic waste-flow and mass/energy balance model.
"""

from ecotwin.categories import WasteCategory
from ecotwin.exceptions import (
    CapacityExceededError,
    EcoTwinError,
    InvalidCompositionError,
    InvalidRoutingError,
    PhysicsViolationError,
)
from ecotwin.facility import (
    CategoryProcessingProfile,
    FacilityResult,
    ProcessingFacility,
)
from ecotwin.routing import RouteSplit, RoutingPlan
from ecotwin.stream import WasteStream
from ecotwin.units import (
    Energy,
    EnergyUnit,
    Mass,
    MassUnit,
    SpecificEnergy,
)
from ecotwin.balance import EcoTwinEngine, SystemBalanceResult

__all__ = [
    "WasteCategory",
    "Mass",
    "MassUnit",
    "Energy",
    "EnergyUnit",
    "SpecificEnergy",
    "WasteStream",
    "CategoryProcessingProfile",
    "ProcessingFacility",
    "FacilityResult",
    "RouteSplit",
    "RoutingPlan",
    "EcoTwinEngine",
    "SystemBalanceResult",
    "EcoTwinError",
    "PhysicsViolationError",
    "InvalidCompositionError",
    "CapacityExceededError",
    "InvalidRoutingError",
]

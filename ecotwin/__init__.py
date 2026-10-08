"""EcoTwin: Physics-Informed AI Digital Twin for Urban Waste & Energy Systems.

Phase 1: Core deterministic waste-flow and mass/energy balance model.
Phase 2: Scenario and data layer with validation, synthetic baselines, and structured execution.
"""

from ecotwin.balance import EcoTwinEngine, SystemBalanceResult
from ecotwin.categories import WasteCategory
from ecotwin.exceptions import (
    CapacityExceededError,
    EcoTwinError,
    InvalidCompositionError,
    InvalidRoutingError,
    PhysicsViolationError,
    ScenarioValidationError,
)
from ecotwin.facility import (
    CategoryProcessingProfile,
    FacilityResult,
    ProcessingFacility,
)
from ecotwin.routing import RouteSplit, RoutingPlan
from ecotwin.scenario import (
    Scenario,
    ScenarioExecutionResult,
    UrbanScenario,
)
from ecotwin.stream import WasteStream
from ecotwin.synthetic import (
    SYNTHETIC_ASSUMPTION_NOTICE,
    generate_baseline_scenario,
    generate_synthetic_city_scenario,
)
from ecotwin.units import (
    Energy,
    EnergyUnit,
    Mass,
    MassUnit,
    SpecificEnergy,
)

__all__ = [
    # Domain categories & units
    "WasteCategory",
    "Mass",
    "MassUnit",
    "Energy",
    "EnergyUnit",
    "SpecificEnergy",
    # Stream & facilities
    "WasteStream",
    "CategoryProcessingProfile",
    "ProcessingFacility",
    "FacilityResult",
    # Routing & balance engine
    "RouteSplit",
    "RoutingPlan",
    "EcoTwinEngine",
    "SystemBalanceResult",
    # Scenario data layer (Phase 2)
    "UrbanScenario",
    "Scenario",
    "ScenarioExecutionResult",
    "generate_baseline_scenario",
    "generate_synthetic_city_scenario",
    "SYNTHETIC_ASSUMPTION_NOTICE",
    # Exceptions
    "EcoTwinError",
    "PhysicsViolationError",
    "InvalidCompositionError",
    "CapacityExceededError",
    "InvalidRoutingError",
    "ScenarioValidationError",
]

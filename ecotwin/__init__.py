"""EcoTwin: Physics-Informed AI Digital Twin for Urban Waste & Energy Systems.

Phase 1: Core deterministic waste-flow and mass/energy balance model.
Phase 2: Scenario and data layer with validation, synthetic baselines, and structured execution.
Phase 3: AI forecasting module for waste generation and composition with physics constraints.
Phase 4: Waste-routing optimization layer for constrained multi-criteria decision making.
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
from ecotwin.forecasting import (
    FORECASTING_BENCHMARK_NOTICE,
    HistoricalWasteDataset,
    RidgeLinearRegressor,
    WasteForecastResult,
    WasteForecaster,
    WasteObservation,
    forecast_to_scenario,
    generate_synthetic_history,
)
from ecotwin.optimization import (
    LinearProgramSolver,
    OptimizationResult,
    OptimizationWeights,
    WasteRoutingOptimizer,
    optimize_scenario_routing,
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
    # Forecasting AI layer (Phase 3)
    "WasteObservation",
    "HistoricalWasteDataset",
    "generate_synthetic_history",
    "RidgeLinearRegressor",
    "WasteForecaster",
    "WasteForecastResult",
    "forecast_to_scenario",
    "FORECASTING_BENCHMARK_NOTICE",
    # Optimization decision layer (Phase 4)
    "OptimizationWeights",
    "OptimizationResult",
    "WasteRoutingOptimizer",
    "optimize_scenario_routing",
    "LinearProgramSolver",
    # Exceptions
    "EcoTwinError",
    "PhysicsViolationError",
    "InvalidCompositionError",
    "CapacityExceededError",
    "InvalidRoutingError",
    "ScenarioValidationError",
]

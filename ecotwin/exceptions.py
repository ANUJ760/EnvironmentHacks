"""Domain exceptions for EcoTwin mass and energy balance modeling."""


class EcoTwinError(Exception):
    """Base class for all EcoTwin domain exceptions."""
    pass


class PhysicsViolationError(EcoTwinError):
    """Raised when physical consistency laws (e.g., mass conservation, fraction bounds) are violated."""
    pass


class InvalidCompositionError(PhysicsViolationError):
    """Raised when waste composition fractions do not sum to 1.0 or are out of bounds."""
    pass


class CapacityExceededError(EcoTwinError):
    """Raised when waste routed to a facility exceeds its configured processing capacity."""
    pass


class InvalidRoutingError(EcoTwinError):
    """Raised when routing fractions are invalid or point to incompatible/missing facilities."""
    pass


class ScenarioValidationError(EcoTwinError):
    """Raised when a scenario configuration fails structural, capacity, or physical validation."""
    pass


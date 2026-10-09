"""Explicit physical units for mass, energy, and specific energy in EcoTwin."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
from typing import Union

from ecotwin.exceptions import PhysicsViolationError


class MassUnit(str, Enum):
    KG = "kg"
    TONNES = "tonnes"


class EnergyUnit(str, Enum):
    KWH = "kWh"
    MWH = "MWh"


class DistanceUnit(str, Enum):
    KM = "km"
    M = "m"


@dataclass(frozen=True)
class Distance:
    """Represents a physical distance quantity with explicit units."""

    value: float
    unit: DistanceUnit = DistanceUnit.KM

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value):
            raise PhysicsViolationError(f"Distance value cannot be NaN or Inf: {self.value}")
        if self.value < -1e-9:
            raise PhysicsViolationError(f"Distance cannot be negative: {self.value} {self.unit.value}")
        if -1e-9 <= self.value < 0.0:
            object.__setattr__(self, "value", 0.0)

    @classmethod
    def km(cls, value: float) -> Distance:
        return cls(value=float(value), unit=DistanceUnit.KM)

    @classmethod
    def meters(cls, value: float) -> Distance:
        return cls(value=float(value), unit=DistanceUnit.M)

    @classmethod
    def zero(cls, unit: DistanceUnit = DistanceUnit.KM) -> Distance:
        return cls(value=0.0, unit=unit)

    def to_km(self) -> Distance:
        if self.unit == DistanceUnit.KM:
            return self
        return Distance(value=self.value / 1000.0, unit=DistanceUnit.KM)

    def to_meters(self) -> Distance:
        if self.unit == DistanceUnit.M:
            return self
        return Distance(value=self.value * 1000.0, unit=DistanceUnit.M)

    def as_unit(self, unit: DistanceUnit) -> Distance:
        if unit == DistanceUnit.KM:
            return self.to_km()
        elif unit == DistanceUnit.M:
            return self.to_meters()
        raise ValueError(f"Unsupported distance unit: {unit}")

    def __add__(self, other: Distance) -> Distance:
        if not isinstance(other, Distance):
            return NotImplemented
        other_in_unit = other.as_unit(self.unit)
        return Distance(value=self.value + other_in_unit.value, unit=self.unit)

    def __sub__(self, other: Distance) -> Distance:
        if not isinstance(other, Distance):
            return NotImplemented
        other_in_unit = other.as_unit(self.unit)
        diff = self.value - other_in_unit.value
        return Distance(value=diff, unit=self.unit)

    def __mul__(self, factor: float) -> Distance:
        if not isinstance(factor, (int, float)):
            return NotImplemented
        if factor < 0:
            raise PhysicsViolationError(f"Cannot multiply distance by negative factor: {factor}")
        return Distance(value=self.value * factor, unit=self.unit)

    def __rmul__(self, factor: float) -> Distance:
        return self.__mul__(factor)

    def __truediv__(self, other: Union[float, Distance]) -> Union[Distance, float]:
        if isinstance(other, (int, float)):
            if other <= 0:
                raise PhysicsViolationError(f"Cannot divide distance by non-positive divisor: {other}")
            return Distance(value=self.value / other, unit=self.unit)
        elif isinstance(other, Distance):
            other_in_unit = other.as_unit(self.unit)
            if other_in_unit.value == 0:
                raise ZeroDivisionError("Cannot divide by zero distance.")
            return self.value / other_in_unit.value
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Distance):
            return False
        return math.isclose(self.to_km().value, other.to_km().value, rel_tol=1e-7, abs_tol=1e-7)

    def __lt__(self, other: Distance) -> bool:
        if not isinstance(other, Distance):
            return NotImplemented
        return self.to_km().value < other.to_km().value - 1e-7

    def __le__(self, other: Distance) -> bool:
        if not isinstance(other, Distance):
            return NotImplemented
        return self.to_km().value <= other.to_km().value + 1e-7

    def __gt__(self, other: Distance) -> bool:
        if not isinstance(other, Distance):
            return NotImplemented
        return self.to_km().value > other.to_km().value + 1e-7

    def __ge__(self, other: Distance) -> bool:
        if not isinstance(other, Distance):
            return NotImplemented
        return self.to_km().value >= other.to_km().value - 1e-7

    def __repr__(self) -> str:
        return f"Distance({self.value:.4f} {self.unit.value})"



@dataclass(frozen=True)
class Mass:
    """Represents a physical mass quantity with explicit units."""

    value: float
    unit: MassUnit = MassUnit.TONNES

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value):
            raise PhysicsViolationError(f"Mass value cannot be NaN or Inf: {self.value}")
        if self.value < -1e-9:
            raise PhysicsViolationError(f"Mass cannot be negative: {self.value} {self.unit.value}")
        # Clean up very tiny negative floats due to floating-point rounding
        if -1e-9 <= self.value < 0.0:
            object.__setattr__(self, "value", 0.0)

    @classmethod
    def kg(cls, value: float) -> Mass:
        return cls(value=float(value), unit=MassUnit.KG)

    @classmethod
    def tonnes(cls, value: float) -> Mass:
        return cls(value=float(value), unit=MassUnit.TONNES)

    @classmethod
    def zero(cls, unit: MassUnit = MassUnit.TONNES) -> Mass:
        return cls(value=0.0, unit=unit)

    def to_kg(self) -> Mass:
        if self.unit == MassUnit.KG:
            return self
        return Mass(value=self.value * 1000.0, unit=MassUnit.KG)

    def to_tonnes(self) -> Mass:
        if self.unit == MassUnit.TONNES:
            return self
        return Mass(value=self.value / 1000.0, unit=MassUnit.TONNES)

    def as_unit(self, unit: MassUnit) -> Mass:
        if unit == MassUnit.KG:
            return self.to_kg()
        elif unit == MassUnit.TONNES:
            return self.to_tonnes()
        raise ValueError(f"Unsupported mass unit: {unit}")

    def __add__(self, other: Mass) -> Mass:
        if not isinstance(other, Mass):
            return NotImplemented
        # Convert other to self's unit
        other_in_unit = other.as_unit(self.unit)
        return Mass(value=self.value + other_in_unit.value, unit=self.unit)

    def __sub__(self, other: Mass) -> Mass:
        if not isinstance(other, Mass):
            return NotImplemented
        other_in_unit = other.as_unit(self.unit)
        diff = self.value - other_in_unit.value
        return Mass(value=diff, unit=self.unit)

    def __mul__(self, factor: float) -> Mass:
        if not isinstance(factor, (int, float)):
            return NotImplemented
        if factor < 0:
            raise PhysicsViolationError(f"Cannot multiply mass by negative factor: {factor}")
        return Mass(value=self.value * factor, unit=self.unit)

    def __rmul__(self, factor: float) -> Mass:
        return self.__mul__(factor)

    def __truediv__(self, other: Union[float, Mass]) -> Union[Mass, float]:
        if isinstance(other, (int, float)):
            if other <= 0:
                raise PhysicsViolationError(f"Cannot divide mass by non-positive divisor: {other}")
            return Mass(value=self.value / other, unit=self.unit)
        elif isinstance(other, Mass):
            other_in_unit = other.as_unit(self.unit)
            if other_in_unit.value == 0:
                raise ZeroDivisionError("Cannot divide by zero mass.")
            return self.value / other_in_unit.value
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mass):
            return False
        return math.isclose(self.to_kg().value, other.to_kg().value, rel_tol=1e-7, abs_tol=1e-7)

    def __lt__(self, other: Mass) -> bool:
        if not isinstance(other, Mass):
            return NotImplemented
        return self.to_kg().value < other.to_kg().value - 1e-7

    def __le__(self, other: Mass) -> bool:
        if not isinstance(other, Mass):
            return NotImplemented
        return self.to_kg().value <= other.to_kg().value + 1e-7

    def __gt__(self, other: Mass) -> bool:
        if not isinstance(other, Mass):
            return NotImplemented
        return self.to_kg().value > other.to_kg().value + 1e-7

    def __ge__(self, other: Mass) -> bool:
        if not isinstance(other, Mass):
            return NotImplemented
        return self.to_kg().value >= other.to_kg().value - 1e-7

    def __repr__(self) -> str:
        return f"Mass({self.value:.4f} {self.unit.value})"


@dataclass(frozen=True)
class Energy:
    """Represents a physical energy quantity with explicit units."""

    value: float
    unit: EnergyUnit = EnergyUnit.KWH

    def __post_init__(self) -> None:
        if math.isnan(self.value) or math.isinf(self.value):
            raise PhysicsViolationError(f"Energy value cannot be NaN or Inf: {self.value}")
        if self.value < -1e-9:
            raise PhysicsViolationError(f"Energy cannot be negative: {self.value} {self.unit.value}")
        if -1e-9 <= self.value < 0.0:
            object.__setattr__(self, "value", 0.0)

    @classmethod
    def kwh(cls, value: float) -> Energy:
        return cls(value=float(value), unit=EnergyUnit.KWH)

    @classmethod
    def mwh(cls, value: float) -> Energy:
        return cls(value=float(value), unit=EnergyUnit.MWH)

    @classmethod
    def zero(cls, unit: EnergyUnit = EnergyUnit.KWH) -> Energy:
        return cls(value=0.0, unit=unit)

    def to_kwh(self) -> Energy:
        if self.unit == EnergyUnit.KWH:
            return self
        return Energy(value=self.value * 1000.0, unit=EnergyUnit.KWH)

    def to_mwh(self) -> Energy:
        if self.unit == EnergyUnit.MWH:
            return self
        return Energy(value=self.value / 1000.0, unit=EnergyUnit.MWH)

    def as_unit(self, unit: EnergyUnit) -> Energy:
        if unit == EnergyUnit.KWH:
            return self.to_kwh()
        elif unit == EnergyUnit.MWH:
            return self.to_mwh()
        raise ValueError(f"Unsupported energy unit: {unit}")

    def __add__(self, other: Energy) -> Energy:
        if not isinstance(other, Energy):
            return NotImplemented
        other_in_unit = other.as_unit(self.unit)
        return Energy(value=self.value + other_in_unit.value, unit=self.unit)

    def __sub__(self, other: Energy) -> Energy:
        if not isinstance(other, Energy):
            return NotImplemented
        other_in_unit = other.as_unit(self.unit)
        diff = self.value - other_in_unit.value
        return Energy(value=diff, unit=self.unit)

    def __mul__(self, factor: float) -> Energy:
        if not isinstance(factor, (int, float)):
            return NotImplemented
        if factor < 0:
            raise PhysicsViolationError(f"Cannot multiply energy by negative factor: {factor}")
        return Energy(value=self.value * factor, unit=self.unit)

    def __rmul__(self, factor: float) -> Energy:
        return self.__mul__(factor)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Energy):
            return False
        return math.isclose(self.to_kwh().value, other.to_kwh().value, rel_tol=1e-7, abs_tol=1e-7)

    def __lt__(self, other: Energy) -> bool:
        if not isinstance(other, Energy):
            return NotImplemented
        return self.to_kwh().value < other.to_kwh().value - 1e-7

    def __le__(self, other: Energy) -> bool:
        if not isinstance(other, Energy):
            return NotImplemented
        return self.to_kwh().value <= other.to_kwh().value + 1e-7

    def __gt__(self, other: Energy) -> bool:
        if not isinstance(other, Energy):
            return NotImplemented
        return self.to_kwh().value > other.to_kwh().value + 1e-7

    def __ge__(self, other: Energy) -> bool:
        if not isinstance(other, Energy):
            return NotImplemented
        return self.to_kwh().value >= other.to_kwh().value - 1e-7

    def __repr__(self) -> str:
        return f"Energy({self.value:.4f} {self.unit.value})"


@dataclass(frozen=True)
class SpecificEnergy:
    """
    Specific energy content per mass unit (e.g., Lower Heating Value / usable thermal or electrical energy content).
    Default unit basis: kWh / tonne.
    """

    kwh_per_tonne: float

    def __post_init__(self) -> None:
        if self.kwh_per_tonne < 0.0:
            raise PhysicsViolationError(f"Specific energy content cannot be negative: {self.kwh_per_tonne}")

    @classmethod
    def from_kwh_per_tonne(cls, value: float) -> SpecificEnergy:
        return cls(kwh_per_tonne=float(value))

    @classmethod
    def from_kwh_per_kg(cls, value: float) -> SpecificEnergy:
        return cls(kwh_per_tonne=float(value) * 1000.0)

    @classmethod
    def from_mj_per_kg(cls, value: float) -> SpecificEnergy:
        # 1 MJ = 1/3.6 kWh = 0.2777777... kWh
        # MJ/kg = (value / 3.6) kWh/kg = (value / 3.6 * 1000) kWh/tonne
        return cls(kwh_per_tonne=(float(value) / 3.6) * 1000.0)

    @classmethod
    def zero(cls) -> SpecificEnergy:
        return cls(kwh_per_tonne=0.0)

    def calculate_energy(
        self,
        mass: Mass,
        efficiency: float = 1.0,
        output_unit: EnergyUnit = EnergyUnit.KWH,
    ) -> Energy:
        """
        Calculates recovered energy: Mass (tonnes) * Specific Energy (kWh/tonne) * Efficiency.
        """
        if not (0.0 <= efficiency <= 1.0):
            raise PhysicsViolationError(f"Conversion efficiency must be between 0 and 1, got {efficiency}")
        
        mass_tonnes = mass.to_tonnes().value
        raw_kwh = mass_tonnes * self.kwh_per_tonne * efficiency
        energy_kwh = Energy.kwh(raw_kwh)
        return energy_kwh.as_unit(output_unit)

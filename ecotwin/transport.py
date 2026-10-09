"""Waste transportation and emissions model for EcoTwin (Phase 5).

Deterministic physical model calculating:
- Number of required vehicle trips: trips = ceil(M / vehicle_payload)
- Total transport distance: total_distance = trips * D
- Total transport energy/fuel: transport_energy = total_distance * vehicle_energy_per_km
- Estimated transport CO2 emissions: transport_emissions = transport_energy * emissions_factor

All calculations enforce explicit physical units and strict determinism.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union

from ecotwin.exceptions import PhysicsViolationError
from ecotwin.facility import ProcessingFacility
from ecotwin.routing import RoutingPlan
from ecotwin.units import Distance, DistanceUnit, Energy, EnergyUnit, Mass, MassUnit

# Standard benchmark assumptions notice for transport parameters
TRANSPORT_BENCHMARK_NOTICE = (
    "ASSUMPTION: Transport network distances, vehicle payload capacities (10.0 tonnes), "
    "energy consumption (3.5 kWh/km), and emissions factors (0.27 kg CO2/kWh) are benchmark modeling "
    "assumptions for urban waste logistics simulation and do not represent empirical fleet telematics."
)


@dataclass(frozen=True)
class TransportConfig:
    """
    Fleet and logistical configuration parameters for waste transportation.

    Benchmark assumptions:
    - vehicle_payload: 10.0 tonnes (standard municipal compactor truck payload)
    - vehicle_energy_per_km: 3.5 kWh / km (diesel-equivalent heavy collection vehicle energy consumption)
    - emissions_factor: 0.27 kg CO2 / kWh (direct combustion emissions factor)
    """

    vehicle_payload: Mass = field(default_factory=lambda: Mass.tonnes(10.0))
    vehicle_energy_per_km: Energy = field(default_factory=lambda: Energy.kwh(3.5))
    emissions_factor: float = 0.27  # kg CO2 per kWh
    source_location: Tuple[float, float] = (0.0, 0.0)
    name: str = "Benchmark_Fleet_Config"

    def __post_init__(self) -> None:
        if not isinstance(self.vehicle_payload, Mass):
            raise PhysicsViolationError(f"vehicle_payload must be an instance of Mass, got {type(self.vehicle_payload)}")
        if self.vehicle_payload.to_kg().value <= 0.0:
            raise PhysicsViolationError(f"vehicle_payload must be positive, got {self.vehicle_payload}")

        if not isinstance(self.vehicle_energy_per_km, Energy):
            raise PhysicsViolationError(
                f"vehicle_energy_per_km must be an instance of Energy, got {type(self.vehicle_energy_per_km)}"
            )
        if self.vehicle_energy_per_km.to_kwh().value < 0.0:
            raise PhysicsViolationError(
                f"vehicle_energy_per_km cannot be negative, got {self.vehicle_energy_per_km}"
            )

        if math.isnan(self.emissions_factor) or math.isinf(self.emissions_factor):
            raise PhysicsViolationError(f"emissions_factor cannot be NaN or Inf, got {self.emissions_factor}")
        if self.emissions_factor < 0.0:
            raise PhysicsViolationError(f"emissions_factor cannot be negative, got {self.emissions_factor}")


@dataclass(frozen=True)
class RouteTransportResult:
    """
    Evaluated transportation metrics for waste dispatched along a specific facility route.
    """

    facility_name: str
    waste_transported: Mass
    distance: Distance
    trips: int
    total_distance: Distance
    transport_energy: Energy
    transport_emissions: Mass  # in kg CO2 (represented as physical Mass unit)

    def __post_init__(self) -> None:
        if self.trips < 0:
            raise PhysicsViolationError(f"trips cannot be negative: {self.trips}")


@dataclass(frozen=True)
class TransportEvaluationResult:
    """
    System-wide transportation and emissions evaluation summary across all active routes.
    """

    route_results: Dict[str, RouteTransportResult]
    total_waste_transported: Mass
    total_trips: int
    total_distance: Distance
    total_transport_energy: Energy
    total_transport_emissions: Mass
    transport_config: TransportConfig

    @property
    def total_transport_emissions_tonnes(self) -> float:
        return self.total_transport_emissions.to_tonnes().value

    @property
    def total_transport_emissions_kg(self) -> float:
        return self.total_transport_emissions.to_kg().value

    def summary(self) -> Dict[str, Any]:
        """Returns a structured dictionary summarizing transportation metrics."""
        return {
            "total_waste_transported": f"{self.total_waste_transported.value:.2f} {self.total_waste_transported.unit.value}",
            "total_vehicle_trips": self.total_trips,
            "total_distance_km": round(self.total_distance.to_km().value, 2),
            "total_transport_energy_kwh": round(self.total_transport_energy.to_kwh().value, 2),
            "total_transport_energy_mwh": round(self.total_transport_energy.to_mwh().value, 4),
            "total_transport_emissions_kg_co2": round(self.total_transport_emissions.to_kg().value, 2),
            "total_transport_emissions_tonnes_co2": round(self.total_transport_emissions.to_tonnes().value, 4),
            "routes": {
                fac_name: {
                    "waste_transported": f"{r.waste_transported.value:.2f} {r.waste_transported.unit.value}",
                    "one_way_distance_km": round(r.distance.to_km().value, 2),
                    "trips": r.trips,
                    "total_distance_km": round(r.total_distance.to_km().value, 2),
                    "transport_energy_kwh": round(r.transport_energy.to_kwh().value, 2),
                    "transport_emissions_kg_co2": round(r.transport_emissions.to_kg().value, 2),
                }
                for fac_name, r in self.route_results.items()
            },
        }

    def format_report(self) -> str:
        """Generates a formatted text summary of transportation and emissions."""
        lines = [
            "-" * 72,
            " EcoTwin Waste Transportation & Emissions Evaluation Report",
            "-" * 72,
            f"  * Total Waste Transported    : {self.total_waste_transported.value:.2f} {self.total_waste_transported.unit.value}",
            f"  * Total Vehicle Trips        : {self.total_trips} trips (payload: {self.transport_config.vehicle_payload.value:.1f} {self.transport_config.vehicle_payload.unit.value})",
            f"  * Total Fleet Distance       : {self.total_distance.to_km().value:.2f} km",
            f"  * Total Transport Energy     : {self.total_transport_energy.to_kwh().value:.2f} kWh ({self.total_transport_energy.to_mwh().value:.4f} MWh)",
            f"  * Total Transport CO2        : {self.total_transport_emissions.to_kg().value:.2f} kg CO2 ({self.total_transport_emissions.to_tonnes().value:.4f} t CO2)",
            "\n[Per-Facility Route Logistics Breakdown]",
            f"  {'Facility':<30} | {'Waste (t)':<10} | {'Dist (km)':<10} | {'Trips':<6} | {'Tot km':<10} | {'CO2 (kg)':<10}",
            f"  {'-'*30}-|-{'-'*10}-|-{'-'*10}-|-{'-'*6}-|-{'-'*10}-|-{'-'*10}",
        ]
        for fac_name, r in self.route_results.items():
            w_t = r.waste_transported.to_tonnes().value
            d_km = r.distance.to_km().value
            tot_km = r.total_distance.to_km().value
            co2_kg = r.transport_emissions.to_kg().value
            lines.append(
                f"  {fac_name:<30} | {w_t:>8.2f} t | {d_km:>8.2f} km | {r.trips:>6} | {tot_km:>8.2f} km | {co2_kg:>8.2f} kg"
            )
        lines.append("-" * 72)
        return "\n".join(lines)


class TransportModel:
    """
    Deterministic waste transportation and emissions evaluation engine.
    """

    @classmethod
    def calculate_route_transport(
        cls,
        facility_name: str,
        waste_mass: Mass,
        distance: Distance,
        config: TransportConfig,
    ) -> RouteTransportResult:
        """
        Calculates logistics and emissions for transport of mass M over distance D:
        
        trips = ceil(M / vehicle_payload)
        total_distance = trips * D
        transport_energy = total_distance * vehicle_energy_per_km
        transport_emissions = transport_energy * emissions_factor
        """
        m_tonnes = waste_mass.to_tonnes().value
        payload_tonnes = config.vehicle_payload.to_tonnes().value
        d_km = distance.to_km().value

        if m_tonnes <= 1e-9 or d_km <= 1e-9:
            if m_tonnes <= 1e-9:
                trips = 0
            else:
                trips = math.ceil(m_tonnes / payload_tonnes)
            
            total_dist = Distance.km(trips * d_km)
            transport_energy = Energy.kwh(total_dist.to_km().value * config.vehicle_energy_per_km.to_kwh().value)
            transport_emissions = Mass.kg(transport_energy.to_kwh().value * config.emissions_factor)

            return RouteTransportResult(
                facility_name=facility_name,
                waste_transported=waste_mass,
                distance=distance,
                trips=trips,
                total_distance=total_dist,
                transport_energy=transport_energy,
                transport_emissions=transport_emissions,
            )

        trips = math.ceil(m_tonnes / payload_tonnes)
        total_dist_km = trips * d_km
        total_dist = Distance.km(total_dist_km)
        energy_kwh = total_dist_km * config.vehicle_energy_per_km.to_kwh().value
        transport_energy = Energy.kwh(energy_kwh)
        emissions_kg = energy_kwh * config.emissions_factor
        transport_emissions = Mass.kg(emissions_kg)

        return RouteTransportResult(
            facility_name=facility_name,
            waste_transported=waste_mass,
            distance=distance,
            trips=trips,
            total_distance=total_dist,
            transport_energy=transport_energy,
            transport_emissions=transport_emissions,
        )

    @classmethod
    def evaluate_loads(
        cls,
        facility_loads: Mapping[str, Mass],
        facilities: Mapping[str, ProcessingFacility],
        config: Optional[TransportConfig] = None,
    ) -> TransportEvaluationResult:
        """
        Evaluates system transport metrics from a mapping of facility_name -> routed Mass.
        """
        active_config = config or TransportConfig()
        route_results: Dict[str, RouteTransportResult] = {}

        total_mass = Mass.zero()
        total_trips = 0
        total_distance = Distance.zero()
        total_energy = Energy.zero()
        total_emissions = Mass.zero(MassUnit.KG)

        for fac_name, fac in facilities.items():
            routed_mass = facility_loads.get(fac_name, Mass.zero())
            dist = fac.distance_quantity

            # Calculate route metrics
            r_res = cls.calculate_route_transport(
                facility_name=fac_name,
                waste_mass=routed_mass,
                distance=dist,
                config=active_config,
            )
            route_results[fac_name] = r_res

            total_mass = total_mass + routed_mass
            total_trips += r_res.trips
            total_distance = total_distance + r_res.total_distance
            total_energy = total_energy + r_res.transport_energy
            total_emissions = total_emissions + r_res.transport_emissions

        return TransportEvaluationResult(
            route_results=route_results,
            total_waste_transported=total_mass,
            total_trips=total_trips,
            total_distance=total_distance,
            total_transport_energy=total_energy,
            total_transport_emissions=total_emissions,
            transport_config=active_config,
        )


def evaluate_transport(
    facility_loads: Mapping[str, Mass],
    facilities: Mapping[str, ProcessingFacility],
    config: Optional[TransportConfig] = None,
) -> TransportEvaluationResult:
    """Convenience functional interface to evaluate waste transportation metrics."""
    return TransportModel.evaluate_loads(facility_loads=facility_loads, facilities=facilities, config=config)

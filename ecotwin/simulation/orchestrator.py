"""Reconstruct immutable inputs; no remote weather lookup during simulation."""

import json
import math
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from ecotwin.config import get_settings
from ecotwin.db.models import City, CitySnapshot, WeatherHour
from ecotwin.errors import TwinError
from ecotwin.models.landcover import apply_edits, class_areas
from ecotwin.models.registry import MODELS
from ecotwin.models.runoff import runoff_volume
from ecotwin.models.solar_pv import solar_energy
from ecotwin.models.waste_adapter import build_scenario, waste_metrics
from ecotwin.simulation.command import canonical_digest
from ecotwin.simulation.comparison import metric
from ecotwin.spatial.spatial_queries import load_cover, snapshot_inputs
from ecotwin.storage.factory import object_store


def execute(session, frozen, checkpoint=lambda progress: None):
    snapshot = session.get(CitySnapshot, UUID(frozen["snapshot_id"]))
    if not snapshot:
        raise TwinError("DATASET_NOT_READY", "Frozen snapshot missing")
    city = session.get(City, snapshot.city_id)
    revisions = snapshot_inputs(session, snapshot)
    store = object_store(get_settings(), {r.object_key: r.sha256 for r in revisions})
    objects = {r.kind: store.materialize(r.object_key, r.sha256) for r in revisions}
    checkpoint(15)
    edits, request = frozen["edits"], frozen["request"]
    requested = request["requested_models"]
    if any(model not in MODELS for model in requested):
        raise TwinError("MODEL_NOT_AVAILABLE", "A requested model is unavailable")
    parameters = snapshot.baseline_summary["parameters"]
    if canonical_digest(parameters) != snapshot.model_config_sha256:
        raise TwinError("DATASET_CHECKSUM_MISMATCH", "Snapshot model parameter digest changed")
    sources = [str(r.id) for r in revisions]
    digest = canonical_digest(
        {
            "snapshot": snapshot.composite_input_sha256,
            "parameters": parameters,
            "scenario": frozen["scenario_digest"],
            "request": request,
        }
    )
    metrics = []
    warnings = []
    unavailable = []
    realized = []
    weather = []
    if (
        "solar_pv" in requested
        or "runoff_screen" in requested
        and request.get("event_rainfall_mm") is None
    ):
        rev = next((r for r in revisions if r.kind == "weather"), None)
        if not rev:
            raise TwinError("INSUFFICIENT_INPUT_DATA", "Pinned weather required")
        weather = list(
            session.scalars(
                select(WeatherHour)
                .where(WeatherHour.revision_id == rev.id)
                .order_by(WeatherHour.valid_at)
            )
        )
        if request.get("start_at"):
            start = datetime.fromisoformat(request["start_at"])
            end = datetime.fromisoformat(request["end_at"])
            weather = [w for w in weather if start <= w.valid_at < end]
            if (
                not weather
                or weather[0].valid_at != start
                or weather[-1].valid_at + timedelta(hours=1) != end
            ):
                raise TwinError(
                    "INSUFFICIENT_INPUT_DATA", "Weather must cover every requested hour"
                )
        if not weather or any(
            b.valid_at - a.valid_at != timedelta(hours=1) for a, b in zip(weather, weather[1:])
        ):
            raise TwinError("INSUFFICIENT_INPUT_DATA", "Contiguous weather required")
        warnings.append(
            "PINNED_FORECAST: issue time is preserved; this simulation does not claim current weather"
        )
    checkpoint(30)
    if {"landcover_summary", "runoff_screen"} & set(requested):
        baseline = load_cover(session, snapshot, city)
        changed, realized = apply_edits(baseline, edits, city.analysis_srid)
        areas, modified = class_areas(baseline), class_areas(changed)
        if "landcover_summary" in requested:
            for code in sorted(areas.keys() | modified.keys()):
                metrics.append(
                    metric(
                        f"class_{code}_area",
                        areas.get(code, 0),
                        modified.get(code, 0),
                        "m2",
                        "landcover_summary",
                        "landcover-v1",
                        sources,
                        snapshot.model_config_sha256,
                        city.slug,
                        ["WorldCover_2021_reference", "area_not_individual_tree_count"],
                        "DETERMINISTIC_CALCULATION",
                    )
                )
        if "runoff_screen" in requested:
            config = parameters["runoff_coefficients.v1.yaml"]
            coefficients = {int(k): float(v) for k, v in config["coefficients"].items()}
            precipitation = request.get("event_rainfall_mm")
            if precipitation is None:
                if not request.get("start_at") or any(w.rain_mm is None for w in weather):
                    raise TwinError(
                        "INSUFFICIENT_INPUT_DATA",
                        "Supply rainfall depth or a complete explicit weather interval",
                    )
                precipitation = math.fsum(w.rain_mm for w in weather)
            from shapely.ops import unary_union

            from ecotwin.spatial.geometry import geometry, project

            targets = [
                project(geometry(e["polygon_geojson"]), city.analysis_srid)
                for e in edits
                if e["edit_type"] == "LAND_COVER_RECLASSIFY"
            ]
            if targets:
                target = unary_union(targets)
                excluded = math.fsum(
                    p.geom.intersection(target).area * p.fraction
                    for p in changed
                    if p.class_code not in coefficients
                )
                if excluded / target.area > 0.1:
                    raise TwinError(
                        "INCOMPLETE_COVERAGE",
                        "Excluded runoff classes exceed 10% of intervention area",
                    )
            if any(k not in coefficients and a > 0 for k, a in areas.items()):
                warnings.append(
                    "INCOMPLETE_COVERAGE: excluded snow/water/wetland/mangrove/moss cells are not terrestrial runoff"
                )
            metrics.append(
                metric(
                    "event_runoff_volume",
                    runoff_volume(areas, precipitation, coefficients),
                    runoff_volume(modified, precipitation, coefficients),
                    "m3",
                    "runoff_screen",
                    config["model_version"],
                    sources,
                    canonical_digest(config),
                    city.slug,
                    config["limitations"],
                )
            )
    checkpoint(60)
    if "solar_pv" in requested:
        installations = [e for e in edits if e["edit_type"] == "SOLAR_PV_INSTALL"]
        if not installations:
            raise TwinError("INSUFFICIENT_INPUT_DATA", "Add at least one PV installation")
        if any(w.ghi_w_m2 is None for w in weather):
            raise TwinError("INSUFFICIENT_INPUT_DATA", "Missing pinned irradiance")
        config = parameters["solar_defaults.v1.yaml"]
        value = math.fsum(
            solar_energy(
                e["installed_kwp"],
                [w.ghi_w_m2 for w in weather],
                e["performance_ratio"],
                e["panel_tilt_deg"],
            )
            for e in installations
        )
        metrics.append(
            metric(
                "pv_indicative_energy",
                0,
                value,
                "kWh",
                "solar_pv",
                config["model_version"],
                sources,
                canonical_digest(installations),
                city.slug,
                config["limitations"],
                start=weather[0].valid_at.isoformat(),
                end=(weather[-1].valid_at + timedelta(hours=1)).isoformat(),
            )
        )
        unavailable.append(
            {
                "name": "emissions_delta",
                "reason_code": "INSUFFICIENT_INPUT_DATA",
                "missing_inputs": ["verified_grid_emission_factor"],
            }
        )
    if "waste_balance" in requested:
        if "waste" not in objects:
            raise TwinError(
                "INSUFFICIENT_INPUT_DATA", "City waste records and explicit profiles required"
            )
        document = json.loads(objects["waste"].read_text())
        base = build_scenario(document)
        overrides = [e for e in edits if e["edit_type"] == "WASTE_ROUTING_OVERRIDE"]
        routes = {k: list(v) if isinstance(v, list) else v for k, v in document["routing"].items()}
        for category in {e["stream_category"] for e in overrides}:
            rows = [e for e in overrides if e["stream_category"] == category]
            if any(e["origin_id"] != document["origin_id"] for e in rows):
                raise TwinError(
                    "MODEL_INPUT_UNSUPPORTED", "Waste origin does not match pinned source"
                )
            routes[category] = [(e["facility_id"], e["allocation_fraction"]) for e in rows]
        scenario = build_scenario(document, routes)
        optimization = None
        if request.get("optimize_waste"):
            from ecotwin.optimization import OptimizationWeights, WasteRoutingOptimizer

            weights = OptimizationWeights(**document["optimization_weights"])
            result = WasteRoutingOptimizer(weights).optimize(scenario)
            if result.status != "OPTIMAL":
                raise TwinError(
                    "OPTIMIZATION_INFEASIBLE", "Optimizer did not find an optimal feasible solution"
                )
            scenario = result.optimized_scenario
            optimization = {
                "status": result.status,
                "weights": document["optimization_weights"],
                "solver_metadata": result.solver_metadata,
            }
        old, new = waste_metrics(base), waste_metrics(scenario)
        for name in old:
            metrics.append(
                metric(
                    name,
                    old[name],
                    new[name],
                    "kWh" if "energy" in name else "kg",
                    "waste_balance",
                    "legacy-waste-v1",
                    sources,
                    canonical_digest(document),
                    city.slug,
                    ["capacity_and_efficiency_from_declared_profiles"],
                    "DETERMINISTIC_CALCULATION",
                )
            )
    else:
        optimization = None
    checkpoint(90)
    return {
        "input_digest": digest,
        "model_versions": {model: MODELS[model]["version"] for model in requested},
        "metrics": metrics,
        "warnings": warnings,
        "evidence": {
            "schema_version": 1,
            "snapshot_id": str(snapshot.id),
            "scenario_revision": frozen["scenario_revision"],
            "data_provenance": [
                {
                    "id": str(r.id),
                    "source_url": r.source_url,
                    "sha256": r.sha256,
                    "license": r.source_license,
                    "attribution": r.attribution,
                    "acquired_at": r.acquired_at.isoformat(),
                    "quality": r.quality_json,
                }
                for r in revisions
            ],
            "model_parameters": parameters,
            "realized_edits": realized,
            "unavailable_metrics": unavailable,
            "optimization": optimization,
            "data_served_from": getattr(
                store, "data_served_from", get_settings().ecotwin_storage_mode
            ),
        },
    }

"""Verify an exported planning report and replay its metrics offline."""

import argparse
import json
import math
from pathlib import Path

from ecotwin.errors import TwinError
from ecotwin.models.planning import PlanningReport, PlanningRequest, calculate_planning
from ecotwin.models.planning import planning_digest as canonical_digest


def replay(document):
    report = PlanningReport.model_validate(document)
    if report.model_version != "planning-screen-v1":
        raise TwinError("MODEL_INPUT_UNSUPPORTED", "Install the report's pinned model version")
    if canonical_digest(report.model_dump(exclude={"result_sha256"})) != report.result_sha256:
        raise TwinError("DATASET_CHECKSUM_MISMATCH", "Report content was changed")
    cover = {row["class_code"]: row["area_m2"] for row in report.landcover}
    inputs = {
        "inputs": report.inputs,
        "inventory": report.inventory,
        "cover": cover,
        "provenance": report.provenance,
    }
    if canonical_digest(inputs) != report.input_sha256:
        raise TwinError("DATASET_CHECKSUM_MISMATCH", "Report inputs were changed")
    metrics, _, _, _ = calculate_planning(
        PlanningRequest.model_validate(report.inputs),
        report.inventory,
        cover,
        report.area_m2,
        report.provenance["weather_samples"],
        report.provenance["air_samples"],
        report.coverage_fraction,
    )

    def same_metric(expected, actual):
        left, right = expected.model_dump(), actual.model_dump()
        return all(
            math.isclose(value, right[key], rel_tol=1e-12, abs_tol=1e-9)
            if isinstance(value, float) and isinstance(right[key], float)
            else value == right[key]
            for key, value in left.items()
        )

    if len(metrics) != len(report.metrics) or not all(
        same_metric(expected, actual)
        for expected, actual in zip(metrics, report.metrics, strict=True)
    ):
        raise TwinError("DATASET_CHECKSUM_MISMATCH", "Replayed metrics do not match the export")
    return {
        "verified": True,
        "metrics_match": True,
        "model_version": report.model_version,
        "floating_point_tolerance": {"relative": 1e-12, "absolute": 1e-9},
        "input_sha256": report.input_sha256,
        "result_sha256": report.result_sha256,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(json.loads(args.report.read_text()))))

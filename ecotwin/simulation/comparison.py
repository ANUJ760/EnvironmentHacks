from ecotwin.models.types import Metric


def metric(
    name,
    baseline,
    scenario,
    unit,
    model_id,
    version,
    source_ids,
    parameter_digest,
    scope,
    limitations,
    evidence="SCREENING_ESTIMATE",
    start=None,
    end=None,
):
    delta = scenario - baseline
    return Metric(
        name=name,
        baseline_value=baseline,
        scenario_value=scenario,
        absolute_delta=delta,
        percentage_delta=delta / baseline * 100 if baseline else None,
        unit=unit,
        spatial_scope=scope,
        start_at=start,
        end_at=end,
        evidence_class=evidence,
        model_id=model_id,
        model_version=version,
        source_revision_ids=source_ids,
        parameter_digest=parameter_digest,
        limitations=limitations,
    ).model_dump(mode="json")

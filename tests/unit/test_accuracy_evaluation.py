import math

import pytest

from scripts.evaluate_planning_accuracy import evaluate


def rows():
    return [
        {
            "site": "A",
            "date": "2026-01-01",
            "metric": "runoff",
            "unit": "m³/event",
            "predicted": "12",
            "observed": "10",
            "low": "9",
            "high": "14",
        },
        {
            "site": "B",
            "date": "2026-01-01",
            "metric": "runoff",
            "unit": "m³/event",
            "predicted": "17",
            "observed": "20",
            "low": "16",
            "high": "19",
        },
    ]


def test_accuracy_metrics_use_independent_observations_not_replay_agreement():
    result = evaluate(rows())["runoff"]
    assert result["mae"] == 2.5
    assert result["bias"] == -0.5
    assert result["rmse"] == math.sqrt(6.5)
    assert result["interval_coverage"] == 0.5


@pytest.mark.parametrize(
    "field,value",
    [("unit", "litres"), ("predicted", "nan"), ("low", "30"), ("high", ""), ("site", "")],
)
def test_bad_validation_data_is_rejected(field, value):
    data = rows()
    data[1][field] = value
    with pytest.raises(ValueError):
        evaluate(data)


def test_duplicates_and_empty_validation_sets_are_rejected():
    with pytest.raises(ValueError):
        evaluate([rows()[0], rows()[0]])
    with pytest.raises(ValueError):
        evaluate([])

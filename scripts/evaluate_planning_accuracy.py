"""Score held-out observations supplied as CSV; never treat model replay as accuracy.

Columns: site,date,metric,unit,predicted,observed[,low,high]. Predictions and
observations must describe the same quantity, boundary, time window and units.
Do not include calibration/training sites. Prints JSON; does not modify inputs.
"""

import argparse
import csv
import json
import math
from pathlib import Path


def evaluate(rows):
    groups, seen = {}, set()
    for row in rows:
        key = (row["site"], row["date"], row["metric"])
        if not all(key) or key in seen or not row["unit"]:
            raise ValueError("Unique site/date/metric and explicit units required")
        seen.add(key)
        predicted, observed = float(row["predicted"]), float(row["observed"])
        if not math.isfinite(predicted) or not math.isfinite(observed):
            raise ValueError("Finite observed and predicted values required")
        group = groups.setdefault(row["metric"], {"unit": row["unit"], "errors": [], "covered": []})
        if group["unit"] != row["unit"]:
            raise ValueError("Do not mix units within a metric")
        group["errors"].append(predicted - observed)
        low, high = row.get("low", ""), row.get("high", "")
        if bool(low) != bool(high):
            raise ValueError("Both interval bounds required")
        if low and high:
            low, high = float(low), float(high)
            if not math.isfinite(low + high) or not low <= predicted <= high:
                raise ValueError("Finite interval must enclose its prediction")
            group["covered"].append(low <= observed <= high)
    if not groups:
        raise ValueError("Independent validation observations required")
    return {
        metric: {
            "unit": group["unit"],
            "n": len(group["errors"]),
            "mae": sum(abs(e) for e in group["errors"]) / len(group["errors"]),
            "rmse": math.sqrt(sum(e * e for e in group["errors"]) / len(group["errors"])),
            "bias": sum(group["errors"]) / len(group["errors"]),
            "interval_n": len(group["covered"]),
            "interval_coverage": sum(group["covered"]) / len(group["covered"])
            if group["covered"]
            else None,
        }
        for metric, group in groups.items()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations", type=Path)
    args = parser.parse_args()
    with args.observations.open(newline="") as file:
        results = evaluate(csv.DictReader(file))
    print(
        json.dumps(
            {
                "metrics": results,
                "note": "Scores depend on genuinely independent, matched observations; independence is not verified by this tool.",
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()

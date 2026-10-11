# Accuracy: what is improved, and how to evaluate it

This is a screening planner, not a validated city-scale predictor. Passing tests or
replaying an export proves consistency, **not** agreement with the real world.
No independent local energy, waste, runoff or tree-carbon validation set is bundled.
Consequently no measured prediction-accuracy percentage is claimed.

## Implemented improvements

- Zürich's [CC0 municipal tree register](https://data.stadt-zuerich.ch/dataset/geo_baumkataster)
  adds actual locations and species: 81,142 records in the downloaded WFS response;
  4,398 lie inside the published study. The provider describes crown diameters as
  estimated, incompletely updated, and sometimes an 8 m default. They are not
  measured dimensions; trunk size is still a scenario assumption.
- A fixed nine-pixel nearest-tree hit test and hover ring improve selection in both
  map modes. Clicking a low-zoom cluster zooms in; it never removes a cluster as
  though it were one tree. The selected tree's actual coordinate anchors calculations.
- Municipal records are preferred over OSM records within 2 m, using a spatial
  grid. Distinct municipal trees are never merged. This identity-matching heuristic
  can still suppress separate trees or miss displaced duplicates. Matching metadata
  is exported; counts remain an incomplete mapped inventory, not forest-tree counts.
- Import validation rejects non-point/wrong-region coordinates and duplicate IDs;
  unusable crowns remain missing. Source bytes, CC0 license and SHA256 are retained
  in the same local/S3 revision system as the other scientific datasets.
- Same-weather before/after comparisons, bounded geographic coverage, conservation
  tests, visible assumptions and reproducible exports prevent unsupported precision.

## Independent evaluation protocol

1. Freeze a dataset snapshot and parameter version before evaluating. Use new
   sites and later dates that were not used for calibration; retain measurement
   uncertainty, units, area boundaries and observation periods.
2. Trees: survey random street/park/forest strata. Compare one-to-one tree identities
   and positions within a predefined tolerance. Report precision, recall, F1,
   location RMSE and errors by stratum. Score the 2 m duplicate policy separately.
   Comparing the merged asset against its own municipal input is **not** validation.
3. Energy/waste: obtain matched building meter/occupancy and weighed waste records.
   Use local building-use intensities instead of the generic default. Report MAE,
   RMSE and bias. Track relocated activity; demolition is a separate one-time flow.
4. Runoff: use event rainfall, measured outflow and observed soils/drainage on the
   same catchment. Calibrate on some events and test on withheld events. Do not
   compare a tiny selected polygon directly against a whole-river gauge.
5. Carbon: measure species and DBH, use locally applicable allometry and its error.
   Crown estimates alone cannot establish carbon stock or an annual CO₂ flux.
6. Air: validate the regional baseline against independent monitors using matched
   timestamps. Street-level removal effects require a calibrated transport/dispersion
   model; a deposition-capacity proxy is not a concentration prediction.

The lightweight evaluator accepts a CSV with columns
`site,date,metric,unit,predicted,observed,low,high`; interval bounds are optional.

```bash
.venv/bin/python scripts/evaluate_planning_accuracy.py YOUR_HELD_OUT_OBSERVATIONS.csv
```

It reports count, MAE, RMSE, signed bias and interval coverage, rejects duplicate
site/date/metric rows, non-finite values and mixed units. It cannot verify field
independence automatically. Model sensitivity ranges are not probabilistic
confidence intervals; empirical coverage does not change that interpretation.

Before research or planning decisions, publish the held-out sample sizes and scores,
site-specific errors, measurement uncertainty, missing coverage and failure cases.

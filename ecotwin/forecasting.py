"""Waste-generation and composition forecasting module for EcoTwin (Phase 3).

Provides:
1. Synthetic historical waste dataset generator with realistic temporal dynamics (trend, weekly, seasonal, noise).
2. Interpretable multi-output autoregressive / ridge regression baseline forecasting model.
3. Physics-based constraint enforcement (non-negativity, composition simplex sum-to-1, mass conservation).
4. Forecast result structures with full provenance metadata.
5. Integration pipeline converting forecasts into validated UrbanScenario instances.

Core Principle:
"AI predicts the uncertain future; the physics engine determines what is physically possible."
"""

from __future__ import annotations
from dataclasses import dataclass, field
import datetime as dt
import math
import random
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from ecotwin.categories import WasteCategory
from ecotwin.scenario import Scenario, UrbanScenario
from ecotwin.units import Mass, MassUnit


# Synthetic dataset notice
FORECASTING_BENCHMARK_NOTICE = (
    "ASSUMPTION: Synthetic benchmark historical time series. Generated with deterministic "
    "trend, seasonal, and weekly dynamics for model validation. Not empirical municipal records."
)


@dataclass(frozen=True)
class WasteObservation:
    """A single daily historical observation of urban waste generation and composition."""

    date: dt.date
    total_waste: Mass
    composition: Dict[WasteCategory, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.total_waste.to_kg().value < 0:
            raise ValueError("Observation total waste cannot be negative.")
        total_frac = sum(self.composition.values())
        if not math.isclose(total_frac, 1.0, rel_tol=1e-4, abs_tol=1e-4):
            raise ValueError(f"Observation composition fractions must sum to 1.0, got {total_frac:.6f}")

    @property
    def category_masses(self) -> Dict[WasteCategory, Mass]:
        """Calculates mass for each waste category in this observation."""
        return {cat: self.total_waste * frac for cat, frac in self.composition.items()}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "total_waste_tonnes": self.total_waste.to_tonnes().value,
            "composition": {c.value: frac for c, frac in self.composition.items()},
            "category_masses_tonnes": {c.value: m.to_tonnes().value for c, m in self.category_masses.items()},
        }


@dataclass(frozen=True)
class HistoricalWasteDataset:
    """A reproducible historical sequence of daily urban waste observations."""

    observations: Tuple[WasteObservation, ...]
    city_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.observations)

    def __getitem__(self, idx: int) -> WasteObservation:
        return self.observations[idx]

    @property
    def start_date(self) -> dt.date:
        return self.observations[0].date if self.observations else dt.date.today()

    @property
    def end_date(self) -> dt.date:
        return self.observations[-1].date if self.observations else dt.date.today()

    def get_total_waste_series(self) -> List[float]:
        """Returns sequence of daily total waste in tonnes."""
        return [obs.total_waste.to_tonnes().value for obs in self.observations]

    def get_composition_series(self) -> Dict[WasteCategory, List[float]]:
        """Returns sequence of daily category fractions."""
        result: Dict[WasteCategory, List[float]] = {cat: [] for cat in WasteCategory}
        for obs in self.observations:
            for cat in WasteCategory:
                result[cat].append(obs.composition.get(cat, 0.0))
        return result


def generate_synthetic_history(
    days: int = 365,
    start_date: Optional[dt.date] = None,
    base_generation_tonnes: float = 1000.0,
    annual_growth_rate: float = 0.02,  # +2% per year
    base_composition: Optional[Mapping[WasteCategory, float]] = None,
    city_name: str = "Synthetic Metropolis",
    random_seed: int = 42,
) -> HistoricalWasteDataset:
    """
    Generates a deterministic synthetic historical waste dataset with realistic temporal dynamics:
    - Long-term growth trend
    - Weekly seasonality (weekday commercial activity vs weekend residential peaks)
    - Annual seasonality (higher organics in summer/autumn, e-waste holiday surge in winter)
    - Bounded stochastic noise
    """
    rng = random.Random(random_seed)
    start = start_date or dt.date(2025, 1, 1)

    default_comp = {
        WasteCategory.ORGANIC: 0.45,
        WasteCategory.RECYCLABLE: 0.25,
        WasteCategory.E_WASTE: 0.05,
        WasteCategory.RESIDUAL: 0.25,
    }
    base_comp = dict(base_composition or default_comp)

    observations: List[WasteObservation] = []

    for i in range(days):
        current_date = start + dt.timedelta(days=i)
        day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday
        day_of_year = current_date.timetuple().tm_yday

        # 1. Long-term trend component
        trend_factor = 1.0 + (annual_growth_rate * (i / 365.25))

        # 2. Weekly cycle component
        # Weekdays slightly above average, Sundays slightly lower
        weekly_factors = [1.02, 1.01, 1.02, 1.01, 1.03, 0.98, 0.93]
        weekly_factor = weekly_factors[day_of_week]

        # 3. Seasonal cycle component (sine wave peaked around day 200 / July-August)
        seasonal_angle = 2.0 * math.pi * (day_of_year - 80) / 365.25
        seasonal_factor = 1.0 + 0.07 * math.sin(seasonal_angle)

        # 4. Bounded noise component (+/- 3%)
        noise_factor = 1.0 + rng.uniform(-0.03, 0.03)

        # Total daily waste mass
        daily_mass_tonnes = base_generation_tonnes * trend_factor * weekly_factor * seasonal_factor * noise_factor
        daily_mass_tonnes = max(10.0, daily_mass_tonnes)

        # 5. Composition dynamics with seasonal & weekly variations
        # Organics peak in summer/autumn (+4%)
        org_delta = 0.04 * math.sin(seasonal_angle)
        # Recyclables peak on weekends (+2%)
        rec_delta = 0.02 if day_of_week in (5, 6) else -0.008
        # E-waste peaks in winter / holiday season (days 340-365 & 1-15)
        is_holiday = day_of_year > 340 or day_of_year < 15
        ewaste_delta = 0.015 if is_holiday else -0.002

        # Raw category fractions with noise
        raw_org = max(0.10, base_comp[WasteCategory.ORGANIC] + org_delta + rng.uniform(-0.01, 0.01))
        raw_rec = max(0.10, base_comp[WasteCategory.RECYCLABLE] + rec_delta + rng.uniform(-0.01, 0.01))
        raw_ewaste = max(0.01, base_comp[WasteCategory.E_WASTE] + ewaste_delta + rng.uniform(-0.005, 0.005))
        raw_res = max(0.10, base_comp[WasteCategory.RESIDUAL] - (org_delta + rec_delta + ewaste_delta) + rng.uniform(-0.01, 0.01))

        # Enforce exact simplex sum to 1.0
        raw_sum = raw_org + raw_rec + raw_ewaste + raw_res
        comp = {
            WasteCategory.ORGANIC: raw_org / raw_sum,
            WasteCategory.RECYCLABLE: raw_rec / raw_sum,
            WasteCategory.E_WASTE: raw_ewaste / raw_sum,
            WasteCategory.RESIDUAL: raw_res / raw_sum,
        }

        observations.append(
            WasteObservation(
                date=current_date,
                total_waste=Mass.tonnes(round(daily_mass_tonnes, 4)),
                composition=comp,
                metadata={"day_index": i, "is_synthetic": True},
            )
        )

    metadata = {
        "city_name": city_name,
        "sample_count": days,
        "start_date": start.isoformat(),
        "end_date": (start + dt.timedelta(days=days - 1)).isoformat(),
        "is_synthetic": True,
        "assumptions": {
            "notice": FORECASTING_BENCHMARK_NOTICE,
            "base_generation_tonnes": base_generation_tonnes,
            "annual_growth_rate": annual_growth_rate,
            "random_seed": random_seed,
        },
    }

    return HistoricalWasteDataset(
        observations=tuple(observations),
        city_name=city_name,
        metadata=metadata,
    )


# -----------------------------------------------------------------------------
# Interpretable Ridge / Linear Autoregressive Forecaster (Pure Python + OLS)
# -----------------------------------------------------------------------------

def _solve_linear_system(A: List[List[float]], b: List[float]) -> List[float]:
    """Solves A x = b using Gaussian elimination with partial pivoting."""
    n = len(A)
    # Augmented matrix
    M = [A[i][:] + [b[i]] for i in range(n)]

    for i in range(n):
        # Pivot
        max_row = i
        for k in range(i + 1, n):
            if abs(M[k][i]) > abs(M[max_row][i]):
                max_row = k
        M[i], M[max_row] = M[max_row], M[i]

        pivot = M[i][i]
        if abs(pivot) < 1e-12:
            pivot = 1e-12

        # Normalize pivot row
        for j in range(i, n + 1):
            M[i][j] /= pivot

        # Eliminate column entries
        for k in range(n):
            if k != i:
                factor = M[k][i]
                for j in range(i, n + 1):
                    M[k][j] -= factor * M[i][j]

    return [M[i][n] for i in range(n)]


class RidgeLinearRegressor:
    """
    Lightweight, interpretable Ridge Linear Regression estimator.
    Solves (X^T X + alpha * I) w = X^T y deterministically with zero external dependencies.
    """

    def __init__(self, alpha: float = 1.0, fit_intercept: bool = True):
        self.alpha = float(alpha)
        self.fit_intercept = fit_intercept
        self.weights: Optional[List[float]] = None
        self.intercept: float = 0.0

    def fit(self, X: List[List[float]], y: List[float]) -> RidgeLinearRegressor:
        n_samples = len(X)
        if n_samples == 0:
            raise ValueError("Cannot fit on empty dataset.")
        n_features = len(X[0])

        # Add bias feature if fit_intercept
        if self.fit_intercept:
            X_aug = [[1.0] + row for row in X]
            d = n_features + 1
        else:
            X_aug = [row[:] for row in X]
            d = n_features

        # Compute X^T X + alpha * I
        XtX = [[0.0 for _ in range(d)] for _ in range(d)]
        Xty = [0.0 for _ in range(d)]

        for row, y_val in zip(X_aug, y):
            for i in range(d):
                Xty[i] += row[i] * y_val
                for j in range(d):
                    XtX[i][j] += row[i] * row[j]

        # Add Ridge penalty (do not penalize intercept at index 0)
        start_idx = 1 if self.fit_intercept else 0
        for i in range(start_idx, d):
            XtX[i][i] += self.alpha

        w_aug = _solve_linear_system(XtX, Xty)

        if self.fit_intercept:
            self.intercept = w_aug[0]
            self.weights = w_aug[1:]
        else:
            self.intercept = 0.0
            self.weights = w_aug

        return self

    def predict_single(self, x: List[float]) -> float:
        if self.weights is None:
            raise RuntimeError("Model is not fitted.")
        pred = self.intercept
        for w, xi in zip(self.weights, x):
            pred += w * xi
        return pred

    def predict(self, X: List[List[float]]) -> List[float]:
        return [self.predict_single(row) for row in X]


@dataclass(frozen=True)
class WasteForecastResult:
    """
    Physical output from the AI forecasting layer.
    
    Guarantees:
    - predicted_total_waste is non-negative Mass.
    - predicted_composition fractions are non-negative and sum to 1.0.
    - sum of predicted_category_masses strictly equals predicted_total_waste.
    """

    forecast_date: dt.date
    predicted_total_waste: Mass
    predicted_composition: Dict[WasteCategory, float]
    predicted_category_masses: Dict[WasteCategory, Mass]
    model_metadata: Dict[str, Any]
    raw_unconstrained_prediction: Dict[str, float]
    timestamp: str = field(default_factory=lambda: dt.datetime.now().isoformat())

    def to_urban_scenario(
        self,
        base_scenario: UrbanScenario,
        scenario_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> UrbanScenario:
        """
        Converts this forecast into an executable UrbanScenario by binding forecasted demand
        with base scenario facility configurations and routing rules.
        """
        return forecast_to_scenario(
            forecast=self,
            base_scenario=base_scenario,
            scenario_name=scenario_name,
            description=description,
        )

    def summary(self) -> Dict[str, Any]:
        """Structured summary of forecasted quantities and physical balance."""
        return {
            "forecast_date": self.forecast_date.isoformat(),
            "predicted_total_waste_tonnes": self.predicted_total_waste.to_tonnes().value,
            "predicted_composition": {c.value: round(f, 4) for c, f in self.predicted_composition.items()},
            "predicted_category_masses_tonnes": {
                c.value: round(m.to_tonnes().value, 2) for c, m in self.predicted_category_masses.items()
            },
            "model_metadata": self.model_metadata,
            "timestamp": self.timestamp,
        }

    def format_report(self) -> str:
        """Human-readable text report of the forecast."""
        lines = [
            "=" * 72,
            f" EcoTwin AI Waste Forecast Report for {self.forecast_date.isoformat()}",
            "=" * 72,
            f"  * Model Architecture     : {self.model_metadata.get('model_type', 'ML Forecaster')}",
            f"  * Training Window        : {self.model_metadata.get('training_samples', 0)} historical days",
            f"  * Predicted Total Waste  : {self.predicted_total_waste.value:.2f} {self.predicted_total_waste.unit.value}",
            "\n[Forecasted Category Breakdown]",
        ]
        for cat in WasteCategory:
            frac = self.predicted_composition.get(cat, 0.0)
            m = self.predicted_category_masses.get(cat, Mass.zero())
            lines.append(f"  * {cat.value:<14}: {m.value:>8.2f} tonnes ({frac * 100:>5.2f}%)")

        lines.extend([
            "\n[Physical Constraint Normalization]",
            f"  * Composition Simplex Sum: {sum(self.predicted_composition.values()):.6f} (Strictly 1.0)",
            f"  * Mass Conservation Sum  : {sum((m.to_tonnes().value for m in self.predicted_category_masses.values())):.2f} tonnes",
            "=" * 72,
        ])
        return "\n".join(lines)


class WasteForecaster:
    """
    Interpretable Autoregressive Ridge Regression Forecaster for municipal waste streams.

    Features used:
    - Autoregressive lag features (t-1, t-2, t-7)
    - 7-day rolling moving averages
    - Cyclical calendar features (Day of Week sine/cosine, Day of Year sine/cosine)
    - Linear trend indicator
    """

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.mass_model: Optional[RidgeLinearRegressor] = None
        self.comp_models: Dict[WasteCategory, RidgeLinearRegressor] = {}
        self.training_history: Optional[HistoricalWasteDataset] = None
        self.feature_names: List[str] = []

    def _extract_features(
        self,
        history: Sequence[WasteObservation],
        idx: int,
    ) -> List[float]:
        """Extracts engineered features for observation at index `idx` using preceding history."""
        # Requires at least 7 preceding days
        obs_t = history[idx]
        d_obj = obs_t.date
        dow = d_obj.weekday()
        doy = d_obj.timetuple().tm_yday

        # Cyclical calendar features
        dow_sin = math.sin(2.0 * math.pi * dow / 7.0)
        dow_cos = math.cos(2.0 * math.pi * dow / 7.0)
        doy_sin = math.sin(2.0 * math.pi * doy / 365.25)
        doy_cos = math.cos(2.0 * math.pi * doy / 365.25)
        trend = float(idx) / 365.25

        # Lags
        mass_lag1 = history[idx - 1].total_waste.to_tonnes().value
        mass_lag2 = history[idx - 2].total_waste.to_tonnes().value
        mass_lag7 = history[idx - 7].total_waste.to_tonnes().value
        mass_roll7 = sum(history[idx - k].total_waste.to_tonnes().value for k in range(1, 8)) / 7.0

        features = [
            dow_sin,
            dow_cos,
            doy_sin,
            doy_cos,
            trend,
            mass_lag1,
            mass_lag2,
            mass_lag7,
            mass_roll7,
        ]

        # Category fraction lags
        for cat in WasteCategory:
            cat_lag1 = history[idx - 1].composition.get(cat, 0.0)
            cat_lag7 = history[idx - 7].composition.get(cat, 0.0)
            features.extend([cat_lag1, cat_lag7])

        return features

    def train(self, dataset: HistoricalWasteDataset) -> WasteForecaster:
        """Trains autoregressive multi-output models on the historical dataset."""
        if len(dataset) < 14:
            raise ValueError(f"Dataset too short for training: need at least 14 days, got {len(dataset)}")

        self.training_history = dataset

        X: List[List[float]] = []
        y_mass: List[float] = []
        y_comp: Dict[WasteCategory, List[float]] = {cat: [] for cat in WasteCategory}

        # Train on indices 7 to len(dataset)-1
        for i in range(7, len(dataset)):
            feats = self._extract_features(dataset.observations, i)
            X.append(feats)
            y_mass.append(dataset.observations[i].total_waste.to_tonnes().value)
            for cat in WasteCategory:
                y_comp[cat].append(dataset.observations[i].composition.get(cat, 0.0))

        self.mass_model = RidgeLinearRegressor(alpha=self.alpha).fit(X, y_mass)
        for cat in WasteCategory:
            self.comp_models[cat] = RidgeLinearRegressor(alpha=self.alpha).fit(X, y_comp[cat])

        return self

    def predict_next_day(
        self,
        recent_history: Optional[HistoricalWasteDataset | Sequence[WasteObservation]] = None,
    ) -> WasteForecastResult:
        """
        Generates physical next-day waste generation and composition forecast.

        Applies explicit deterministic post-processing:
        1. Clamps total waste mass to non-negative (>= 0).
        2. Clamps raw category fractions to non-negative (>= 0).
        3. Projects fractions onto the probability simplex (sums strictly to 1.0).
        4. Calculates category masses strictly conserving total predicted mass.
        """
        if self.mass_model is None or not self.comp_models:
            raise RuntimeError("WasteForecaster must be trained before predicting.")

        history_seq: Sequence[WasteObservation]
        if recent_history is None:
            if self.training_history is None:
                raise ValueError("No historical observations provided for prediction.")
            history_seq = self.training_history.observations
        elif isinstance(recent_history, HistoricalWasteDataset):
            history_seq = recent_history.observations
        else:
            history_seq = recent_history

        if len(history_seq) < 7:
            raise ValueError(f"Need at least 7 recent observations to construct features, got {len(history_seq)}")

        last_obs = history_seq[-1]
        forecast_date = last_obs.date + dt.timedelta(days=1)

        # Build feature vector for the target day
        dummy_next_obs = WasteObservation(
            date=forecast_date,
            total_waste=last_obs.total_waste,
            composition=dict(last_obs.composition),
        )
        extended_history = list(history_seq) + [dummy_next_obs]
        target_idx = len(extended_history) - 1
        X_next = self._extract_features(extended_history, target_idx)

        # 1. Raw ML model predictions
        raw_mass_tonnes = self.mass_model.predict_single(X_next)
        raw_fractions: Dict[WasteCategory, float] = {
            cat: self.comp_models[cat].predict_single(X_next) for cat in WasteCategory
        }

        raw_unconstrained = {
            "total_waste_tonnes": raw_mass_tonnes,
            **{f"frac_{cat.value}": raw_fractions[cat] for cat in WasteCategory},
        }

        # 2. Enforce physical constraints: Non-negative Mass
        constrained_mass_tonnes = max(0.0, float(raw_mass_tonnes))
        constrained_mass = Mass.tonnes(constrained_mass_tonnes)

        # 3. Enforce physical constraints: Composition Simplex (non-negative, sum == 1.0)
        clamped_fractions: Dict[WasteCategory, float] = {
            cat: max(0.0, float(raw_fractions[cat])) for cat in WasteCategory
        }
        frac_sum = sum(clamped_fractions.values())

        if frac_sum > 0.0:
            normalized_comp = {cat: clamped_fractions[cat] / frac_sum for cat in WasteCategory}
        else:
            # Fallback to uniform if all predictions are zero
            normalized_comp = {cat: 1.0 / len(WasteCategory) for cat in WasteCategory}

        # 4. Enforce mass conservation across category masses
        category_masses = {cat: constrained_mass * normalized_comp[cat] for cat in WasteCategory}

        model_meta = {
            "model_type": "Autoregressive Ridge Linear Forecaster",
            "alpha": self.alpha,
            "training_samples": len(self.training_history) if self.training_history else 0,
            "features": [
                "dow_sin", "dow_cos", "doy_sin", "doy_cos", "trend",
                "mass_lag1", "mass_lag2", "mass_lag7", "mass_roll7",
                "cat_lags",
            ],
            "physics_normalization": (
                "Clamped mass >= 0, clamped category fractions >= 0, "
                "normalized composition to simplex sum=1.0, derived category masses strictly conserving total mass."
            ),
        }

        return WasteForecastResult(
            forecast_date=forecast_date,
            predicted_total_waste=constrained_mass,
            predicted_composition=normalized_comp,
            predicted_category_masses=category_masses,
            model_metadata=model_meta,
            raw_unconstrained_prediction=raw_unconstrained,
        )


def forecast_to_scenario(
    forecast: WasteForecastResult,
    base_scenario: UrbanScenario,
    scenario_name: Optional[str] = None,
    description: Optional[str] = None,
) -> UrbanScenario:
    """
    Architectural boundary function: Converts a constrained ML forecast into a validated UrbanScenario.

    Pipeline:
    Historical Data -> ML Forecaster -> Constrained Forecast -> UrbanScenario -> EcoTwin Physics Engine
    """
    name = scenario_name or f"{base_scenario.name}_Forecast_{forecast.forecast_date.isoformat()}"
    desc = description or f"Scenario driven by AI waste forecast for {forecast.forecast_date.isoformat()}."

    updated_metadata = dict(base_scenario.metadata)
    updated_metadata["forecast_metadata"] = {
        "forecast_date": forecast.forecast_date.isoformat(),
        "model_type": forecast.model_metadata.get("model_type"),
        "predicted_total_tonnes": forecast.predicted_total_waste.to_tonnes().value,
        "timestamp": forecast.timestamp,
    }

    return UrbanScenario.create(
        name=name,
        daily_waste_generation=forecast.predicted_total_waste,
        composition=forecast.predicted_composition,
        facilities=base_scenario.facilities,
        routing_plan=base_scenario.routing_plan,
        metadata=updated_metadata,
        description=desc,
    )

# EcoTwin Data & Evidence Policy

## 1. Scientific Integrity Principles
EcoTwin adheres strictly to verifiable empirical data and validated formulas. The application never manufactures artificial results, placeholder numbers, or optimistic climate predictions without an underlying model.

### 1.1 Separation of Evidence Tiers
Every reported indicator in EcoTwin belongs to an explicit evidence category:
- **`OBSERVED`**: Direct recorded observations (e.g., ground monitoring stations, weather stations). Baseline context only; never labeled as an intervention effect unless causality is proven.
- **`DETERMINISTIC_CALCULATION`**: Exact mathematical or geometric calculation directly derived from inputs (e.g., area recalculation, mass balance).
- **`SCREENING_ESTIMATE`**: Coarse approximation intended for initial comparison (e.g., composite runoff coefficient volume screening). Disclaimers and limitations are displayed adjacent to the metric.
- **`CALIBRATED_PREDICTION`**: Statistically or physically calibrated model against local measurements.
- **`ASSUMED_INPUT`**: User-selected parameter or documented engineering assumption (e.g., solar PV default performance ratio of 0.75).
- **`UNAVAILABLE`**: Explicit acknowledgment that a model or prerequisite dataset is absent. Displayed as *Not Simulated* with scientific explanation rather than numeric zero.

## 2. Inadmissible Mock Data & Illustrative Artifacts
- The conceptual prototype UI concept image (`assets/ecotwin-ui-concept.png`) serves solely as visual direction for color palette and map prominence.
- Numbers in that image (e.g., "+1.8 °C", "+28% PM2.5", "-35% habitat connectivity", "12,000 people") are illustrative and must never be hardcoded into the application.
- If the simulation engine does not produce a metric, the frontend presents it as unavailable.

## 3. Data Licensing and Provenance Register
- **OpenStreetMap**: Mapped civic geometry (buildings, highways, parks). Licensed under Open Database License (ODbL) 1.0. Attribution displayed on all map views.
- **ESA WorldCover (2021)**: 10-meter global land-cover raster. Licensed under Creative Commons Attribution 4.0 International (CC-BY 4.0).
- **Open-Meteo API**: Historical and forecast weather context. Open access for non-commercial and research usage.
- **OpenAQ**: Public real-time and historical air quality observation network.

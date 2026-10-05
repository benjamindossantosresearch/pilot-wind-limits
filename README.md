# Do Pilots Know Their Limits?

[![DOI](https://zenodo.org/badge/1406418904.svg)](https://doi.org/10.5281/zenodo.23173344)

Code, the dated decision log, and aggregate results for the paper "Do Pilots Know Their Limits? Comparing Revealed Wind Limits with Measured Approach Performance Using ADS-B" by Benjamin DosSantos Jr. (manuscript, 2026).

The study estimates the crosswind at which general aviation pilots stop flying (the revealed limit) from public ADS-B data, counts how often approaches are flown above the airplane's maximum demonstrated crosswind, and scores each approach against stabilized approach criteria at 300 ft. Methods were developed on seven New England airports (16 February 2023 to 30 September 2026) and then frozen and applied to 467 airports in the contiguous United States (1 October 2025 to 30 September 2026).

## What is here

- Analysis code, at the top level. The scripts import each other by name and read and write folders relative to the repository root, so run them from the root. Each script starts with a docstring that says what it does and how to run it.
- `notes/decisions.md`, the dated decision log. Every rule was entered there before the analysis it governs was run, and every later change is logged with its reason. The log calls these rules "pre-registered". The paper calls them "prespecified", since the log was kept by the author rather than deposited with a registry.
- `notes/q2_measures.md`, the definitions of the approach performance measures.
- `notes/ops_detector_*.py`, frozen versions of the approach detector. `ops_detector.py` is version 3.1, used for the US results. Version 3.0.1 is used for New England, where the two versions give identical results.
- `reference/`, the handbook (POH) values for the 20 aircraft types (sources in `notes/poh_sources/`), the candidate airports, and FAA OPSNET daily tower counts.
- Aggregate results, one folder per analysis, each with a `summary.txt`:

| Folder | Contents |
|---|---|
| `q1a/`, `q1a_us/` | Revealed limits, New England and United States, with the hourly arrival table used (`hours.csv`, gzipped for the US) |
| `q1b/` | Approaches flown above the maximum demonstrated crosswind, New England |
| `q2_wind/`, `q2_ne_locked/` | Approach performance, New England, on the original and the final scores |
| `q2_us_results_v31_cas/` | Approach performance and the demonstrated crosswind comparison, United States (primary) |
| `q2_us_results_v31_cas_exp0/`, `_exp020/`, `_exp025/` | The same with other wind profile exponents |
| `q2_us_results/`, `q2_us_results_v31/`, `q2_wind_with_inferred/` | Earlier runs kept for comparison (detector 3.0.1, inferred passes kept, or true airspeed) |
| `q2_validation/`, `q2_synthetic/`, `q2_pattern_wind/`, `q2_audit/` | Measurement checks |
| `tower_compare_full/`, `capture_weather/`, `us_tower_compare/`, `us_tower_compare_v31/` | Detected operations against FAA tower counts, and capture against weather |
| `us_parallel/` | Pattern sides at parallel runways, used by detector rule 12 |
| `paper/figures/` | Figure scripts and the aggregate data behind each figure |
| `review_2026-10-05/` | Checks run during review of the draft (sensitivities and diagnostics) |

## What is not here

There is no per-aircraft or per-approach data. Some owners limit public display of their aircraft through the FAA's LADD program, and per-approach records could identify individual flights. The detector validation labels are left out for the same reason, since they come with the tracks they label. Every input is public and can be downloaded again:

- ADS-B traces: the ADSB.lol globe history archive, https://github.com/adsblol (`fetch_days.py` for New England, `us_fetch.py` for the United States).
- Weather: METARs and one-minute ASOS wind from the Iowa Environmental Mesonet, https://mesonet.agron.iastate.edu (`fetch_metar.py`, `fetch_onemin.py`).
- Aircraft registry: FAA releasable aircraft database, https://registry.faa.gov/database/ReleasableAircraft.zip, into `reference/faa_registry/` (`faa_registry.py`).
- Airports and runways: FAA NASR 28-day subscription, APT, ATC, and AWOS CSV files, into `reference/nasr/`.
- Tower counts: FAA OPSNET Airport Operations, one facility per export (`notes/opsnet_tower_counts_how_to.md`, `opsnet_parse.py`).

The ADS-B archive is large (about 3 to 4 GB per day). The New England cache is about 25 GB and the US extracts about 40 GB.

## Order of the analysis

New England development sample:

1. `fetch_days.py`, `fetch_metar.py`, `fetch_onemin.py` fill the caches.
2. `tower_compare.py` and `capture_weather.py` compare detected operations with tower counts and set the analysis windows.
3. `q1a_counts.py` and `q1a_crosswind.py --mode window` give the revealed limits. `coverage_monthly.py` sets the windows of the non-towered airports.
4. `q1b_exceedance.py` counts approaches above the maximum demonstrated crosswind.
5. `q2_extract.py` and `q2_measures.py` measure every approach. `q2_validate.py`, `q2_synthetic.py`, `q2_pattern_wind.py`, and `q2_audit.py` check the measures.
6. `q2_wind.py` runs the original analysis, and `us_q2.py` with `US_Q2_SAMPLE=ne` runs the final scores.

United States confirmatory sample:

1. `us_candidates.py` lists the candidate airports. `us_fetch.py` and `us_pipeline.py` build the per-day extracts and counts.
2. `us_inclusion.py` admits airport-months and drops outage days. `us_q1a.py` gives the revealed limits.
3. `q2_measures.py --us --rule12` measures every approach (calibrated airspeed by default, `--profile-exp` for the wind profile). `us_q2.py` gives the demonstrated crosswind comparison and the approach performance results.
4. `us_tower_compare.py` checks detected operations against tower counts.
5. `us_exposure.py`, `us_wind_speed.py`, and `us_xw_angle.py` run the exploratory comparisons.
6. `paper/figures/make_fig_data.py` and the other figure scripts draw the figures.

## Requirements

Python 3.11 or later with numpy, pandas, and matplotlib (developed with Python 3.14, numpy 2.3, pandas 2.3, matplotlib 3.10). Everything else is the standard library.

## Licenses

The code is released under the MIT License (`LICENSE`). The aggregate results and tables are derived from ADSB.lol data and are released under the Open Database License 1.0 (`LICENSE-DATA.md`), as that license requires.

## Citation

DosSantos Jr., B., "Do Pilots Know Their Limits? Comparing Revealed Wind Limits with Measured Approach Performance Using ADS-B," manuscript, 2026.

This repository: DosSantos Jr., B., "Do Pilots Know Their Limits? Code, decision log, and aggregate results," Zenodo, doi:10.5281/zenodo.23173344 (all versions). Version 1.0.1, which matches the paper as submitted, is doi:10.5281/zenodo.23174546.

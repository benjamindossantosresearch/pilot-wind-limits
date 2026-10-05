# Methods decisions log

Dated record of analysis decisions, made before looking at outcome data where possible.

## 2026-10-01

* Unit of analysis for Q2 is the approach, regardless of outcome. Go-arounds, touch-and-goes, low approaches, and full stops are not classified. Stability and pattern-quality metrics are computed on the approach segment only. (Benjamin)
* Follow-on to the above: reword Q1b from "landings" to "approaches flown" with a crosswind component above the maximum demonstrated crosswind. For Q1a activity counts, count arrivals (first approach per visit) so repeat approaches after a go-around do not inflate windy-hour activity. (Proposed, pending Benjamin's confirmation)
* Coverage population excludes rotorcraft by ADS-B emitter category A7.
* KPYM runway 06/24 (main runway, ILS) closed from 2026-08-01 per Benjamin, before the full airport closure of 2026-09-21 to 2026-10-02. Being checked against ADS-B runway use. Natural-experiment windows: before (to 2026-07-31), single runway 15/33 (2026-08-01 to 2026-09-20), full closure (2026-09-21 to 2026-10-01).

## 2026-10-01 (later)

* Proceed without receivers for now (Benjamin). Pilot study runs on fields the ADSB.lol archive already covers to about 300 ft AGL: KLWM, KOWD, KBED (towered, ASOS, inside the Mode C veil, so FAA tower counts are available for validation), plus KPYM and KTAN for the closure natural experiment. KEWB and KBVY are deferred until a receiver exists (archive sees only 35 and 42 percent of arrivals down to 300 ft).
* Operations counting for tower validation: an approach pass counts as one operation and a climb-out pass as one operation, so a touch-and-go or low approach is two and a full stop or departure is one. No outcome classification needed. Verify against the FAA counting rules in JO 7210.3 before comparing.
* KPYM 06/24 closure dated from ADS-B: last approach to land on 06/24 was Sunday 2026-08-02 19:34 EDT. Monday 08-03 was IFR with heavy rain (no information). From Tuesday 08-04 all landings are on 15/33 regardless of wind. Benjamin's date of 08-01 (a Saturday) is probably the announcement or NOTAM date. Windows: before through 2026-08-02, single runway 15/33 from 2026-08-03 to 2026-09-20, full closure 2026-09-21 to 2026-10-01. Four low passes over 24 after the closure (lowest 270 to 395 ft AGL) are treated as overflights, not landings.
* Pilot check for Q1a (wind_activity.py), rules fixed before running it: local clock hour, 08 to 18 local. Arrivals are fixed-wing visits with at least one runway-aligned approach pass (no minimum height), counted in the hour of the first pass. Weather is the METAR closest to mid-hour (within 40 minutes). VMC means ceiling at least 3,000 ft or none, visibility at least 5 SM, no precipitation or thunderstorm at the field. Crosswind exposure is the sustained-wind crosswind on the best runway end (smallest crosswind among ends with zero or positive headwind), with a gust version. Demand baseline is mean arrivals for the same hour of day and day type (weekday or weekend) across VMC hours in the window. First run: KLWM, KOWD, KBED, March 2026. One-minute ASOS replaces METAR wind in the full analysis.
* Cache region widened to all of New England (new_england: 41.0 to 47.5 N, 73.75 to 66.9 W, below 6,000 ft MSL) and filled back to the start of the ADSB.lol archive, 2023-02-16 (Benjamin). Each archive day is streamed once for the whole project. The southern edge at 41.0 N leaves out the New York metro area. The older se_new_england cache is a strict subset and can be deleted once the new cache is complete.
* FAA registry join (faa_registry.py, registry snapshot 2026-10-01). Piston fixed-wing GA only for Q1 and Q2. Ownership: fleet means a non-individual registrant holding 3 or more aircraft. Single-aircraft LLCs count as private. Trust-company registrations are their own class. Ownership is matched to the flight date where canceled registrations allow it.
* Cape Air (registrant Hyannis Air Service) is flagged "commercial" and left out of the main analysis: go/no-go is set by company rules, so it does not reveal individual limits, and its piston twins and professional crews are a different population. Kept flagged, not deleted, for a possible professional benchmark in Q2 later. (Recommended to Benjamin 2026-10-01.)
* Hand-labeling sample for detector validation (make_labeling_set.py), fixed before any labeling: 100 visits, KLWM 35, KOWD 35, KBED 30, from 2026-07-18 to 2026-09-20. Eligible: piston GA in the FAA registry (commercial excluded), not rotorcraft, passes within 3 nm of the field below 2,000 ft AGL, 10 or more points, at most 2 hours. Simple random sample per airport, seed 20261001, at most 2 visits per aircraft per airport, shuffled into one order. Raters see anonymized tracks only (no ICAO, registration, date, or time) and never the detector output. Labels per visit: approaches and climb-outs counted per runway end, plus no-operation, not-sure, and too-little-data flags. Two raters label blind (Benjamin and a CFI). The detector output is kept in labeling/detector.csv for scoring.
* Labeling rule clarifications (2026-10-01, from Benjamin's first visit, V001): a short or curved final (power-off 180, tight base-to-final, circle to land) counts as an approach. An opposite-direction landing after pattern work counts under the end it lands toward. The last approach of a visit gets a climb-out only if the track shows the airplane leaving the runway again. Added to the labeler guide before the second rater starts.
* Detector v2 (ops_detector.py) written after scoring v1 against Benjamin's first 100 labels. v1: 87 percent visit agreement, event recall 91.4, precision 97.4. v2 on the same labels: 95 percent, recall 96.9, precision 98.1 (optimistic: those 100 are now the development set). v2 adds curved short finals, two-point passes, early-turning climb-outs, a low-start requirement for climb-outs, an inferred approach before a low climb-out by an airplane already airborne, and an approach when the data ends on final. The pilot-study score for v2 comes from a fresh held-out sample. Raw labels are frozen in labeling/export_BD_raw_2026-10-01 before any re-check, so raw and adjudicated agreement can both be reported.
* Labeling rule added: count an approach the circuit makes certain even when its final falls in a coverage gap (the airplane flew the pattern and climbed out again from that runway). Matches detector v2 rule 5. Inferred approaches count as operations but carry no performance data for Q2.
* Detector v2 frozen 2026-10-01 after adding rule 6 (converging base-to-final turn when data ends) and rule 7 (implied climb-out between two approaches to the same runway). ops_detector.py sha256 prefix 8c67bc2126102ca7, copy at notes/ops_detector_v2_frozen_2026-10-01.py. Development set results, Benjamin's labels: raw labels v1 87 percent, v2 98 percent. After Benjamin corrected V046 and V051 (his entry errors): v1 89 percent, v2 100 percent (event recall and precision both 100 percent, 164 events). These development numbers are optimistic by construction. The pilot-study figure is v2 on the held-out set.
* Held-out set: 100 visits, same three airports and quotas, drawn from March 2026 and 2026-09-21 to 09-30 (outside the development window), seed 20261002, ids T001 to T100. Labeled blind in the same tool. Scored once with the frozen v2.
* Held-out (Set 2) result, frozen v2 (sha256 8c67bc21...), Benjamin's raw labels, scored 2026-10-01: visit agreement 87 percent (87/100), below the pre-stated 90 percent visit-level criterion. Event recall 94.7 percent (266/281), precision 97.4 percent (266/273). v1 on the same labels: 75 percent, recall 80.4, precision 97.0. Raw labels frozen in labeling/export_heldout_BD. Disagreements: three opposite-end naming disputes where the track supports the detector (T011, T060, T063), one ambiguous end-of-data case (T005), three cross-runway double counts at KBED where a turn after takeoff or onto final crosses a second runway's window (T001, T056, T061), four pattern-work miscounts (T049, T067, T071, T073), and two visits Benjamin flagged unsure (T014, T038). Any adjudicated figure is reported alongside the raw 87 percent, never instead of it.
* Set 2 adjudication (Benjamin, 2026-10-01): T011, T060, T063 were his opposite-end naming slips (adjudicated agreement 90 percent, reported beside the raw 87 percent). T067: one go-around, correctly labeled as an approach plus a climb-out. The detector missed exactly that pair: a go-around begun before the threshold puts the descent and the climb in one approach window, which v2 rejects as not descending. Fix planned for v3 (split the pass at its lowest point).
* Bias check on Set 2 detector misses vs wind (nearest METAR): calm hours (<8 kt) missed 8.2 percent of labeled events, windy hours (>=8 kt) 2.7 percent. No sign misses grow with wind (weak test, 100 visits). Net event count error -2.8 percent. Go-arounds are the case to watch for Q2 selection bias.
* T067 shows -106 ft AGL on a touch-and-go (March): the hourly baro correction can be about 100 ft off. Recheck baro vs METAR for March before using heights near the ground for Q2.
* Detector v3 frozen 2026-10-01 (ops_detector.py sha256 prefix 3d63f556b315b179, copy at notes/ops_detector_v3_frozen_2026-10-01.py). New rules 8 to 11: go-around split, cross-runway merge, runway by heading when data ends, runway traversal inside a coverage gap. Development scores with Benjamin's corrected labels: Set 1 100 percent, Set 2 99 percent (only miss T014, flagged unsure). Optimistic by construction, both sets shaped v3. v2 on corrected Set 2: 91 percent.
* Set 3 (held-out for v3): 100 visits, KLWM 35, KOWD 35, KBED 30, from 2025-10-01 to 2025-12-31 (new_england cache), seed 20261003, ids W001 to W100. Labeled blind, scored once with frozen v3. The labeler gains a go-around count (subset of approaches) to measure go-around detection, and a heading readout naming the runway end the current track lines up with (geometry only).
* Height bias found (2026-10-01): the hourly GNSS/baro correction runs -59 ft vs the METAR altimeter at KOWD in March 2026 (IQR -91 to -26) against +21 ft at KPYM in September. Cause: GNSS/baro pairs come from aircraft up to 4,000 ft MSL, where the non-standard-temperature error is largest, while it shrinks to near zero at the field. One correction applied at all heights reads aircraft on short final 50 to 100 ft low in winter and slightly high in summer. Counting is barely affected. Q2 is: the 300 ft gate would shift by season, and windy months are mostly cold. Planned fix before any Q2 work: AGL from the METAR altimeter (exact at field elevation) plus the standard cold-temperature correction for height above the field, with the GNSS/baro method only as a fallback. Frozen v3 will be rescored on the labeled sets with corrected heights (labels do not depend on the height method), both scores reported.
* Stopping rule for detector validation (2026-10-01, before any Set 3 labels): Set 3 is the final held-out test of the pilot study. v3 at or above 90 percent visit agreement on Set 3 meets the criterion. Below 90 percent is reported as is, alongside event-level recall and precision and the wind-bias check, and the study decides whether the error rate is acceptable. No Set 4 to retry the same criterion. A materially different detector would get its own declared test. Remaining labeling: the second rater on Set 1 (inter-rater agreement) and optionally Set 3, and a 30 to 50 visit spot-check at differently laid-out airports during the scale-up.
* PILOT CRITERION RESULT (2026-10-01): frozen v3 (sha256 3d63f556...) on held-out Set 3, Benjamin's raw labels: 92 percent visit agreement (92/100, Wilson 95 percent CI about 85 to 96), meeting the 90 percent criterion. Event recall 97.4 percent (187/192), precision 98.4 percent (187/190), net count -1.0 percent. Errors by wind: calm (<8 kt) 7.9 percent of visits wrong, windy 8.1 percent. v2 also scored 92 percent on Set 3. Set 3 had no labeled go-arounds, so go-around detection is untested on held-out data (development case T067 only). Remaining v3 errors: five single missed events on short tracks (W001, W005, W027, W031, W034) and three extra events from pattern work sweeping a second runway's window (W063, W091, W092), noted for a future production version and not tuned against Set 3. Labels frozen in labeling/export_set3_BD_raw. Per the stopping rule, detector validation labeling is complete.
* Correction to the height-bias entry above (2026-10-01): compared against GNSS height above the field (points within 3 nm, below 1,500 ft), the old GNSS-pair method has no large average seasonal bias (medians within 25 ft at KLWM, KOWD, KPYM in March and September). Its -59 ft gap to the METAR altimeter in March was mostly the expected difference between true height and indicated height in cold air. Its real weakness is hour to hour: the correction is a median over whatever aircraft fly that hour, so an hour dominated by higher traffic in non-standard temperature shifts low aircraft by up to about 100 ft (T067, KOWD 2026-03-02 22:39 UTC: old method -106 ft at touchdown, GNSS -31 ft, METAR-based -13 ft). Adopted: METAR altimeter plus cold-temperature correction (estimate_agl method="metar", now the default), with the GNSS-pair method as fallback. Against GNSS height the METAR-based true height has medians of +26/+21 ft (KLWM Mar/Sep), +17/+10 (KOWD), +1/+4 (KPYM): no seasonal swing, small constant offsets within altimeter and geoid tolerances. Uncorrected indicated height reads +40 to +51 ft in March and near 0 in September, as expected. Both true (agl_ft) and indicated (agl_ind_ft) heights are kept.
* Frozen v3 rescored with METAR-based heights on the same visits and labels (rebuild_tracks.py; a GNSS-method rebuild reproduces the original heights exactly): Set 1 100 percent (unchanged), Set 2 98 percent (was 99), Set 3 92 percent with identical event recall 97.4 and precision 98.4 (unchanged). The pilot-criterion result does not depend on the height method. Heights changed by a median of +8 to +18 ft per set (5th to 95th percentile about -35 to +75 ft).
* Tower-count check, first pass (2026-10-02): Benjamin's OPSNET export combined LWM, OWD, BED, EWB into one daily total (2023-01-01 to 2026-08-31). Transcribed March, July, August 2026 to reference/opsnet/opsnet_combined_LWM_OWD_BED_EWB_2026-03_07_08.csv. tower_compare.py with frozen v3, METAR heights, tower hours from NASR, fixed-wing only: 93 days, detected / tower 0.738, daily correlation 0.936 (March 0.717, July 0.764, August 0.730). The level gap is expected to come mostly from EWB (archive sees about a third of its low traffic, outside the Mode C veil) and helicopters (2,760 rotorcraft visits near the fields, not counted by the runway detector). The 15 percent criterion needs per-facility counts, requested from Benjamin.
* Tower-count criterion, per airport (2026-10-02): per-facility OPSNET exports for LWM, OWD, BED, EWB (2023-01-01 to 2026-08-31) parsed by opsnet_parse.py into reference/opsnet/opsnet_daily.csv (the parsed combined file matches the hand transcription on all 93 checked days). tower_compare.py, frozen v3, METAR heights, tower hours, fixed-wing only, March + July + August 2026 (93 days): BED detected/tower 0.907 (daily r 0.93), LWM 0.789 (r 0.95), OWD 0.758 (r 0.90), EWB 0.364 (r 0.90, archive coverage gap, outside the veil). Raw, BED is within the 15 percent criterion and LWM and OWD are not. Helicopter operations are in the tower counts but not in the fixed-wing detector: rotorcraft visits near the field were 684 (BED), 628 (LWM), 1,413 (OWD). At a rough two operations per visit, LWM would be about -15 percent and OWD about -10 percent. The helicopter adjustment is an estimate, so the raw figures are the ones reported; the residual shortfall (non-equipped aircraft, circuits lost in coverage gaps) needs the full-period run.
* Towered New England airports ranked from July-August 2026 (airport_ranking_towered/ranking.csv). Recommended OPSNET exports: study candidates with good archive coverage BDR (96 percent of arrivals seen to 300 ft, 82 percent trainer types, most pattern work), ORH, HVN; training-heavy fields with poor archive coverage, to measure what the archive misses: DXR, HFD, GON, BAF, BVY. Skipped: Class C airline airports, the islands and Cape (HYA, MVY, ACK) and LEB, where the archive barely sees low traffic, and AWOS-only towered fields (ASH, OXC, OQU).
* Detector v3.0.1 (2026-10-02, sha256 prefix 88696b3679899a9a, copy notes/ops_detector_v3.0.1_2026-10-02.py): crash fix only. Rule 11 can hand rule 5 a climb-out whose start height is missing (a point with neither baro nor GNSS altitude), which raised a TypeError on production data at the new airports. Added a None guard. Scores on all three labeled sets, with both height methods, are identical to v3.
* Tower-count comparison, 12 towered airports, 93 days (March, July, August 2026), v3.0.1: detected/tower BDR 0.934, HVN 0.918, BED 0.907, LWM 0.789, OWD 0.758, BVY 0.702, DXR 0.653, BAF 0.599, ORH 0.572, HFD 0.518, GON 0.484, EWB 0.364. Daily correlations 0.77 to 0.96. The ratio follows archive low-altitude coverage (share of arrivals seen to 300 ft): the three airports where the archive sees 93 to 98 percent are within the 15 percent criterion raw (BDR -6.6, HVN -8.2, BED -9.3 percent). Where coverage is lower, the shortfall is the archive, not the detector. ORH is an outlier (86 percent coverage, 0.57), to investigate. For Q1a a constant capture fraction cancels against the demand baseline, so the open question is whether capture varies with wind or weather. Test that on the full 2023-2026 daily series when the New England fill is complete.
* ORH investigation (2026-10-02): the shortfall (detected/tower 0.57) is aircraft the archive never sees, not detector error. Day check 2026-03-27: 43 visible visits during tower hours, all detected correctly (airliners and bizjets on 29, trainers on 33, an SR22 with 8 touch-and-goes), but the tower logged 114 local operations against about 30 visible pattern operations. Daily fit: detected = 0.60 x itinerant + 0.47 x local at ORH, against about 1.0 x local at BDR and LWM. Source mix of low visits, July-August 2026 sample: UAT via ADS-R is 2 percent at ORH against 8 (BDR), 4 (LWM), 15 (HFD) percent. ORH is outside the Mode C veil, so non-equipped aircraft are legal there, and UAT aircraft only appear when ADS-R is rebroadcast. Most likely a share of the local (pattern) traffic is UAT-only or non-equipped. Lesson: cov300 measures coverage among visible aircraft only; the tower ratio is the better capture measure. ORH is not used for counts or Q2 without a 978 MHz receiver. Separate finding to follow up: itinerant capture is about 0.6 to 0.7 even at well-covered fields (helicopter air-taxi operations and departures that turn before entering the climb window are candidates).
* Weather source cross-checks (2026-10-02, check_metar_sources.py). IEM vs aviationweather.gov (only the last 30 days are served), 15 stations, 2026-09-02 to 09-30: identical report text at nearly every station. Differences are corrected (COR) reports IEM keeps and 20 truncated KBVY reports in IEM missing the altimeter. IEM vs NOAA NCEI ISD (independent federal archive, data through 2025-08-27; 2026 not yet published), PYM, LWM, OWD, BED, BDR, 2023-01 to 2025-08: about 150,000 matched reports; decoded wind direction, speed, gust, altimeter, temperature, and visibility disagree on at most 0.15 percent of reports. Text differences are cosmetic (NCEI drops AUTO). About 1.5 percent of NCEI reports at PYM have no IEM report within 3 minutes. IEM is used as the METAR source.
* New England fill complete (2026-10-02): 1,321 of 1,322 days from 2023-02-16 to 2026-09-30, 25 GB, none failed; 2026-05-06 has no archive release. Script --region defaults switched to new_england, except make_labeling_set.py, which keeps se_new_england so Set 1 reproduces exactly. The se_new_england cache (1.7 GB) is kept for the same reason.
* Capture-vs-weather test, rules fixed before running (2026-10-02). Unit: airport-day with at least 30 tower operations, 2023-02-16 to 2026-08-31, tower hours only. Capture = detected operations / tower operations (tower_compare.py, v3.0.1). Days with capture below 0.2 are counted as archive outages, reported, and excluded. Weather per day from the airport's METARs during tower hours (report nearest mid-hour): mean sustained wind, peak gust, mean best-runway crosswind, share of VMC hours (ceiling at least 3,000 ft or none, visibility at least 5 SM, no precipitation), share of hours with precipitation. Model: log(capture) on mean wind, VMC share, and precipitation share, with airport-by-quarter fixed effects (network growth, season) and weekday fixed effects, weighted by tower operations, HC1 robust standard errors. Fitted for the well-covered airports (BED, BDR, HVN, LWM, OWD) and for all 12. Pass threshold for using archive counts in Q1a without a capture correction: the effect of 10 kt more mean wind on capture is within plus or minus 5 percent, with the 95 percent interval inside plus or minus 10 percent. Repeated with mean best-runway crosswind in place of mean wind.
* No second rater (Benjamin, 2026-10-02): the labeling task is mostly geometry that can be checked against the track itself, so the CFI inter-rater plan is dropped. Label quality rests on (1) adjudication of every detector disagreement against track geometry (headings, positions, heights), as done for Sets 1 to 3, (2) the independent tower-count validation at 12 airports, and optionally (3) an intra-rater check: Benjamin re-labels a random 30 visits blind after a delay. The paper states that labels came from a single rated pilot and names this as a limitation.
* CAPTURE-VS-WEATHER RESULT (2026-10-02, pre-registered test above): full tower comparison 2023-02-16 to 2026-08-31, 12 airports, v3.0.1 (tower_compare_full/). Archive capture grew strongly as ADSB.lol feeders were added: about 0.01 at BDR and HVN in early 2023, about 0.9 from late 2024; BED 0.46 to above 0.9 by 2025; LWM and OWD solid only from the second half of 2025. Well-covered airports (BED, BDR, HVN, LWM, OWD, 5,240 airport-days): capture changes by -3.9 percent per 10 kt mean wind (95 percent CI -6.2 to -1.6), PASS; by -1.9 percent per 10 kt mean best-runway crosswind (-5.3 to +1.7), PASS. All 12 airports: -6.4 percent (-8.2 to -4.5) and -5.3 percent (-8.3 to -2.3), FAIL, driven by the poorly covered fields (BVY falls to 0.76 of calm-day capture on 14 kt-plus days). Conclusion: archive counts can be used for Q1a at the well-covered airports without a capture correction. The residual -4 percent per 10 kt is reported as a bias bound (it would make a drop-off look about 4 percent steeper per 10 kt of mean wind). Limitation: tower counts are daily, so the test is daily, while Q1a works hourly. Implication for Q1a design: demand baselines must be computed within airport-quarter because capture level changes over time.
* Q1a analysis windows, rule fixed before any crosswind results on them (Benjamin agreed 2026-10-02). For towered airports, an airport's window starts at the first month after which monthly archive capture (detected / tower operations, tower_compare_full) never drops below 0.75, or 0.65 for airports that never hold 0.75, and runs to the end of the archive (2026-09-30). Resulting windows: BDR from 2024-07 (monthly capture 87 to 101 percent), HVN from 2024-04 (82 to 98), BED from 2024-10 (82 to 98), LWM from 2025-07 (66 to 83), OWD from 2025-07 (65 to 86). Within a window, days with capture below half the airport's window median are dropped as archive outages. Untowered airports (PYM, TAN) have no tower counts: their windows will come from monthly low-altitude archive coverage, with the rule set before their analysis. Demand baselines stay seasonal (airport by season by day type by hour) because GA demand and wind are both seasonal, independent of capture.
* Backtest (sensitivity analysis): every Q1a result is also computed on the full 2023-02-16 to 2026-09-30 data with airport-by-quarter baselines, and both are reported. Agreement means the windows only remove noise. Disagreement gets explained in the paper. The paper also reports an exclusion table (per airport: days available, days used, capture that set the cutoff) and a figure of archive capture against FAA tower counts over 2023 to 2026.
* Candidate Q2 hypothesis from Benjamin (2026-10-02), to be finalized with the Q2 measure definitions before any Q2 results: crosswind direction relative to the traffic pattern matters, not just magnitude. In a left-hand pattern a crosswind from the left on final is a tailwind on base, which carries the airplane through the extended centerline (the classic overshooting base-to-final turn behind stall-spin accidents). For right traffic, the same applies to a crosswind from the right. Prediction: at equal crosswind magnitude, base-to-final overshoot and late alignment are more frequent with the crosswind from the pattern side. The side of each approach comes from the track (which side of the extended centerline base was flown), with NASR right-traffic flags as a cross-check. Calibration angle: if go/no-go depends on crosswind magnitude only while performance depends on direction, that is a specific gap between expected and actual limits.
* KPYM closure evidence (2026-10-02): no NOTAM or announcement text is on hand (Benjamin). The closure dating rests on the ADS-B record: normal 06/24 use through Sunday 2026-08-02 19:34 EDT, no landings on 06/24 from 2026-08-04 (four low passes only), and no fixed-wing operations from 2026-09-21, consistent with the runway being torn up. Claude will look for a public source (airport or town website, news) to cite alongside it. Not required for the analysis.
* Literature review saved to notes/literature_review.md (search agent, citations checked against Crossref, OpenAlex, PubMed, or source pages; Claude re-checked the four key DOIs). Corrections to the handoff: the personal-minimums study is Winter et al. (2020), N = 112 instrument-rated pilots, 96.4 percent below personal minimums (not 35 students). The TU Delft Schiphol work is a master's thesis. TrajAir is KBTP only. The closest prior work is Yoo and Garcia (2026, AIAA AVIATION, doi:10.2514/6.2026-4080), and the paper must distinguish itself from it. Novelty gaps confirmed: no study of revealed GA wind limits from traffic, of landings beyond maximum demonstrated crosswind, or of calibration between revealed limits and measured performance.
* Q2 measures fixed (Benjamin, 2026-10-02, before any Q2 result): notes/q2_measures.md. Primary gate 300 ft HAT (AFH, GA piston in a traffic pattern), secondary 500 ft. Severity is continuous, not pass or fail (Benjamin: the goal is to quantify how unsafe approaches get, not to show that crosswind makes them worse). Each criterion is a ratio of deviation to its stabilized-approach tolerance: lateral 200 ft, track 10 degrees, bank 15 degrees, vertical 100 ft from the NASR or 3 degree path, descent rate 300 fpm from the path-required rate at current ground speed, airspeed -5/+10 kt of POH approach speed plus half the gust spread, speed stability 10 kt over 30 s. Approach severity score S = the worst ratio at the gate combined with the worst C1 to C4 ratio below it. Level 1 (ratio above 1) and Level 2 (above 2) are reference marks following AC 120-82 event levels. Results are distributions (median, 90th and 99th percentiles, share above 1 and above 2) against crosswind, headwind, and gust, in knots and as a fraction of max demonstrated crosswind. Overshoot (continuous, marks at 200 and 500 ft), alignment height, variability, pattern measures, and the crosswind-direction hypothesis as in the file. Gates use indicated height, true height as sensitivity. Airspeed is estimated as ground speed plus headwind scaled to height with a 1/7 power-law profile (sensitivity 0 and 1/4). POH approach speeds and VSO are being looked up with the crosswind values.
* Q2 amendments after a critical review (Benjamin approved 2026-10-02, before any Q2 result), appended to notes/q2_measures.md: primary severity score narrowed to directly measured criteria (lateral, track, vertical path, descent rate, speed stability), with estimated airspeed and inferred bank demoted to secondary (the archive carries indicated airspeed and roll angle on 0 percent of GA points); machine-flown control group (coupled ILS approaches by airline and business jets) to estimate the measurement and physics floor; measurement validation without onboard data (Benjamin: no G1000 or AHRS logs available), using baro vs GNSS height, NACp accuracy, wind at pattern height from ground-speed variation in pattern turns (HRRR as fallback), and a synthetic noise model; practice-maneuver flagging with results reported both ways; clustered models by aircraft and day; tolerances treated as scale units with sensitivity runs.

## 2026-10-02, overnight run authorization

* Benjamin authorized Claude to fix and log the remaining analysis details itself before running them (Q1a model, PYM/TAN windows, Q1b rules), for his review afterward. Anything changed after results gets a logged reason. Q1b counts approaches flown (not landings) with the two-minute sustained crosswind as primary and the gust crosswind alongside. Fleet rule confirmed (non-individual registrant holding 3 or more aircraft; single-aircraft LLCs are private).
* Q2 overnight: per-approach measures, measurement validation, the control group, and the 30-approach review set are computed overnight. The Q2 wind analysis (severity against wind) waits until Benjamin's sanity check, so no definition can change after wind results are seen.

## Pre-registered by Claude under that authorization (2026-10-02, before results)

* Q1a analysis (q1a_counts.py, q1a_crosswind.py). Data: piston GA arrivals per local hour 08 to 18 from the frozen detector v3.0.1, five airports in their logged windows, outage days excluded (tower-count capture below half the airport's window median, tower days only). Hours: VMC only, from the METAR nearest mid-hour (ceiling at least 3,000 ft or none, visibility at least 5 SM, no precipitation or thunderstorm). Wind: one-minute ASOS within the hour. Each minute's two-minute wind picks the runway end with the smallest crosswind among ends with zero or positive headwind, giving crosswind and headwind for that minute, averaged over the hour. Gust spread = peak five-second gust in the hour minus mean sustained speed. Gust crosswind = the largest gust crosswind component in the hour. Fallback to the METAR wind if fewer than 30 valid minutes. Baseline: mean arrivals for the same airport, season-year (DJF, MAM, JJA, SON), day type (weekday or weekend), and hour, over VMC hours in the window. Cells with fewer than 8 VMC hours are dropped and counted. Summaries: arrivals over baseline (ratio of sums) by crosswind band (0-4, 5-9, 10-14, 15-19, 20+ kt), per airport and pooled, with day-cluster bootstrap 95 percent intervals (1,000 resamples). Same for gust crosswind and headwind. Model: Poisson regression of arrivals on crosswind, headwind, and gust spread with log baseline as offset, pooled and per airport, day-clustered robust standard errors, rate ratios per 5 kt. Revealed limit (the expected limit in the calibration): the crosswind at which modeled activity falls to 50 percent of normal demand (primary) and 75 percent (secondary), headwind and gust spread at their medians, with bootstrap intervals. Split by fleet and private ownership as well.
* Q1a backtest: the same on the full 2023-02-16 to 2026-09-30 data, with baselines per airport, quarter, day type, and hour, and outage days excluded against the quarter median.
* PYM and TAN windows (untowered, no tower counts): the window starts at the first month after which the monthly share of airport-traffic visits seen to 300 ft AGL never drops below 0.60. PYM Q1a excludes 2026-08-03 onward (single-runway period and closure, analyzed separately as the natural experiment). TAN days 2026-09-21 to 2026-10-01 are flagged (PYM diversions).
* Q1b: unit is the approach (v3.0.1), piston GA, VMC hours, study airports in their windows. Crosswind: one-minute ASOS two-minute sustained wind at the minute of the approach's lowest observed point, as a component on the runway end's true course. Gust version uses the five-second gust. Exceedance: crosswind above the POH maximum demonstrated crosswind for the type (variant-specific where the registry model identifies a variant with a different value). Types without a sourced value are excluded and counted. Reported: exceedance share overall and by fleet and private ownership, with aircraft and day clustering, and the distribution of crosswind as a fraction of maximum demonstrated.

### 2026-10-02 02:40, one-minute wind for the backtest period

One-minute ASOS was on disk only from 2024-04. The Q1a backtest runs from 2023-02-16, so fetching 2023-01 to 2024-03 for all seven stations (BDR, HVN, BED, LWM, OWD, PYM, TAN). The pre-registered rule is unchanged: one-minute wind where at least 30 valid minutes exist in the hour, METAR otherwise. The share of hours on each source is reported.

Pre-overnight input check, all present: regional cache complete 2023-02-16 to 2026-09-30 (1,322 days, 2026-05-06 has no release), METARs 2023-01-01 to 2026-09-30 for all seven stations, tower daily file, FAA registry with engine type, NASR glide path angle, threshold crossing height, and threshold and displaced threshold elevations for every study runway end. Ends without a PAPI or VASI (LWM 14, OWD 28, PYM 15, TAN 04, 22, 12) use the 3 degree, 50 ft default as pre-registered.

### 2026-10-02 03:00, Q1a results (windows and backtest), and a failed fit check

Run: q1a_crosswind.py --mode window and --mode backtest, rules as pre-registered above. Window run: 29,140 VMC airport-hours, 91,894 piston arrivals at BDR, HVN, BED, LWM, OWD. Wind from one-minute ASOS for 23,175 hours, METAR fallback for 5,965. Excluded: not VMC 6,965 hours, outage days 418 hours, no weather 363, thin baseline cells 228.

Implementation error, fixed before interpretation: the first run computed the revealed limit relative to calm-crosswind activity instead of normal demand at median headwind and gust spread, as pre-registered. Corrected in the code. First-run values for the record: 23.0 kt (50%) and 9.5 kt (75%).

Pre-registered results (piston, pooled):
* Arrivals over normal demand by mean best-runway crosswind: 0-4 kt 1.05 (1.04 to 1.07), 5-9 kt 0.83 (0.80 to 0.86), 10-14 kt 0.42 (0.36 to 0.49), 15-19 kt 0.13 (0.04 to 0.26, 41 hours).
* Poisson rate ratios per 5 kt: crosswind 0.860 (0.833 to 0.888), headwind 0.852 (0.832 to 0.872), gust spread 0.895 (0.880 to 0.911).
* Revealed limit as pre-registered (log-linear model, headwind 6.3 kt and gust spread 7.0 kt at their medians): 50% at 26.2 kt (21.5 to 31.1), 75% at 12.8 kt (10.8 to 14.8).

Fit check (added at the same time, not pre-registered): the log-linear model fails. Observed against modeled activity by crosswind band: 10-14 kt 0.42 against 0.64, 15-19 kt 0.13 against 0.52. The model assumes the same percentage drop for every knot. The data are flat to about 5 kt and then fall steeply. The 26 kt figure is an extrapolation of a curve that does not fit, not a property of the data.

Post-hoc estimates (labeled post-hoc everywhere they appear):
* Model-free: arrivals over normal demand in 2 kt crosswind bins, first crossing by linear interpolation, day-cluster bootstrap. This is the total effect, including the headwind and gusts that come with crosswind in practice. Piston 50% at 10.8 kt (10.3 to 11.5), 75% at 8.0 kt (7.5 to 8.6). Fleet 10.3 kt (9.9 to 11.0), private 11.7 kt (10.6 to 13.2). Gust crosswind 50% at 21.1 kt (20.2 to 21.9).
* Spline Poisson: piecewise-linear terms in crosswind, headwind and gust spread, knots at 5, 10 and 15 kt. This is the partial effect at median headwind and gust. Piston 50% at 12.6 kt (11.8 to 13.8), 75% at 10.5 kt (10.0 to 10.9). The fit check passes: 10-14 kt 0.42 against 0.42, 15-19 kt 0.13 against 0.17.
* Model-free 50% by airport: BDR 10.8, HVN 13.0, BED 11.0, LWM 6.7. OWD is not reached: its crossing runways keep best-runway crosswind below about 10 kt.

Backtest (full 2023-02-16 to 2026-09-30, quarter baselines, 54,440 hours) agrees: model-free 11.0 kt (10.5 to 11.7), fleet 10.5, private 11.7, spline 12.6 kt (12.0 to 13.7).

Proposed for Benjamin's decision:
* The paper reports the pre-registered model, its failed fit check, and both post-hoc estimates.
* The model-free curve is the primary revealed limit, with the spline model second.
* Reason: the pre-registered specification fails its own fit check, and the model-free curve needs no functional form.

Open item, LWM: the 50% point at 6.7 kt is far below the other airports. The best-runway crosswind assumes every runway is usable. If LWM traffic concentrates on 5/23, pilots face more crosswind than the best-runway value says. Check with LWM runway use by wind direction.

### 2026-10-02 03:00, POH values

The lookup agents opened POH or AFM documents for all 20 types. The raw report with sources and page references is in notes/poh_sources/. Values are transcribed into reference/poh_types.csv and read through poh.py, matched by ICAO designator, FAA registry model and year built:
* Max demonstrated crosswind: C172 15, P28A 17, SR22 20 (3400 lb) or 21 (3600 lb), S22T 21, SR20 20, C182 15, P28R 17, C150 13, C152 12, AA5 16, M20J 11, M20R 13, BE36 17, PA32 17, C72R 15, DA40 20 (NG 25), P32R 17, PA34 17 (Seneca I 13), BE58 22, PA31 20, PA44 17.
* Models whose POH publishes no figure (Cherokee 140/180, early Arrow, pre-1975 C150, early M20, AA-5) carry the family value marked "assumed". Q1b's primary count uses published values only, with assumed values as a sensitivity.
* Where a POH gives an approach speed range, the C5a target is the midpoint (C5a is secondary).
* Rows the agents flagged for a check against a physical POH are listed in the report. None changes a crosswind value for the high-volume types (C172, P28A, SR20, SR22).

### 2026-10-02 03:30, PYM and TAN windows, Q1a for them, Q1b result

PYM and TAN windows by the logged rule (coverage_monthly.py: first month after which the monthly share of fixed-wing airport-traffic visits seen to 300 ft never drops below 0.60):
* PYM from 2025-10. PYM dipped to 0.57-0.58 in June to August 2025. PYM is excluded from 2026-08-03.
* TAN from 2024-09.

The same coverage measure at the towered airports: BDR above 0.84 from mid-2023, HVN above 0.74 from 2023-08, BED below 0.35 until 2025-06 and above 0.92 from 2025-07, LWM 0.5 to 0.76, OWD 0.66 to 0.90 from 2025-07. BED's tower-count capture was already high from late 2024, so the archive saw BED arrivals but not their last 300 ft. This matters for Q2 measurability, not for Q1a counts.

Q1a at PYM and TAN (8,570 VMC hours), model-free 50% point (post-hoc method, as above):
* Pooled 7.6 kt (6.7 to 8.3), PYM 7.7 kt, TAN 6.4 kt.
* Excluding TAN 2026-09-21 to 30 (PYM diversions) changes TAN to 6.5 kt.
* Pattern across all seven airports: the busier towered fields (BDR, HVN, BED) sit at 11 to 13 kt. The smaller fields (LWM, PYM, TAN) sit at 6 to 8 kt.

Q1b result (q1b_exceedance.py, rules as logged, approaches in VMC at the seven airports in their windows):
* Primary count, published POH values only: 193,506 approaches. Sustained crosswind above max demonstrated: 0.04% (82). Gust crosswind above it: 1.22% (2,367).
* Fleet and private do not differ. Sustained: 0.04% against 0.05%. Gust: 1.21% against 1.26%.
* Crosswind as a share of max demonstrated, sustained: median 0.17, p99 0.71. Gust: median 0.23, p99 1.04. Share above half of max demonstrated: 6.3% sustained, 16.9% gust.
* Highest gust exceedance by type: M20J/M20R (11 to 13 kt demonstrated) 8.8%, PA34 4.5%, C152 4.1%, C150M 3.8%.
* The sensitivity with family values is unchanged.

### 2026-10-02 03:30, Q2 implementation details (fixed before any Q2 wind analysis)

These are measurement details the definitions left open, decided after looking only at score distributions, the machine-flown control group, and instrument checks. No piston GA result was examined against wind. Each is in the q2_measures.py docstring.

1. Below-gate criteria stop at 100 ft HAT (roundout), with 50 ft as sensitivity.
2. Descent rate is the median of reported rates within 5 s. Single reports come in 64 fpm steps. With single reports, coupled jets exceeded the C4 tolerance below the gate on 16% of approaches, against 6% with the 5 s median. Single-report values are kept as a sensitivity (s_c4raw).
3. Estimated airspeed uses the wind component against each point's own ground track. The runway-course headwind turned the ground-speed swing of a turn in wind into a false airspeed change in C5b.
4. Altimeter resolution:
   * 38% of piston aircraft (sample of 752) report barometric altitude in 100 ft steps (Gillham encoders), too coarse for the 100 ft glide-path tolerance.
   * For those visits, true height = GNSS geometric height plus the visit's mean (true - geometric) offset. Indicated height = true height divided by the cold-temperature ratio. Descent rate prefers the geometric rate.
   * Check on the 25 ft-step aircraft: calibrated GNSS height matches barometric height within 2 to 6 ft median (IQR about 17 ft) at every height band from 0 to 1,400 ft.
   * 44% of measurable piston approaches use calibrated GNSS heights.
   * Q2 results will be reported split by altimeter resolution as well. On one month at BDR, the 100 ft group shows more below-gate glide-path deviation (b_c3 above 1 on 32% against 9%). That is either a real difference between those aircraft and pilots or a residual measurement effect, and the split keeps it visible.

Instrument checks (q2_validate.py, q2_validation/summary.txt):
* Barometric against GNSS height for piston approaches on barometric heights: median absolute residual about 15 ft. It does not change with gust spread (+0.0 ft per 10 kt, CI -1.4 to +1.4) or wind speed.
* NACp 9 or better on 96% of piston approaches at the gate, the same in every crosswind band.
* Measurability at 300 ft within airport-month: -1.5 points per 10 kt crosswind, +3.4 points per 10 kt gust spread. LWM is the exception (31% overall, 15% at 10-15 kt crosswind).
* Machine-flown floor: jets on straight-in approaches (37,696):
  * S median 0.56 at 0-5 kt crosswind and 0.74 at 15 kt and above. Share above 1 rises from 12.6% to 27.1%.
  * Slope +0.077 per 10 kt crosswind, +0.093 per 10 kt gust spread.
  * The subset reporting autopilot and approach modes (576) shows no crosswind slope.
  * GA wind effects will be reported against this floor.
* The barometric and geometric vertical rates are identical in most reports (IQR 0), so that comparison is not an independent check.

Q2 population: 169,012 measurable piston approaches, VMC, seven airports in their windows. S percentiles: p25 0.85, p75 1.76, p95 4.31, p98 6.49. Distributions only. The wind analysis waits for Benjamin's review of 30 approaches (q2_review/, drawn from strata p98 and above, p75 to p95, p25 and below, seed 20261002).

### 2026-10-02 04:00, post-hoc fix: TAN best-runway crosswind; LWM runway use

TAN 04/22 is a 1,034 ft turf-gravel strip (NASR APT_RWY). Detected use in the window: 266 of 7,418 first approaches. The best-runway crosswind counted it as an option, so hours with wind along 040/220 looked like low-crosswind hours even though the fleet uses 12/30. Fix (post-hoc, after the TAN result): Q1a leaves TAN 04/22 out of the best-runway set (UNUSABLE_ENDS in q1a_crosswind.py). Every other study runway is paved and at least 3,654 ft.
* TAN model-free 50% point: 9.9 kt (8.7 to 12.5). It was 6.4 kt before the fix.
* PYM and TAN pooled: 8.7 kt (8.3 to 11.1). PYM unchanged at 7.7 kt.

LWM check: the runway actually used tracks the best runway at LWM, including the shorter 14/32 (36% of first approaches). In the 5-10 kt best-runway band, median crosswind on the runway used is 6.2 kt against 5.9 kt best. So LWM's low 50% point (6.7 kt) is not a runway-choice artifact. It reflects when LWM's traffic chooses to fly.

### 2026-10-02 04:00, pattern-height wind and synthetic noise model

Pattern-height wind (q2_pattern_wind.py): ground speed through turns at 600-1,600 ft gives the wind near pattern altitude (15,295 airport-hours with a fit, 10,267 with surface wind of 5 kt or more, mean height 946 ft).
* Pattern over surface wind speed: median 1.98 (IQR 1.56 to 2.51). The 1/7 power law predicts 1.62. The implied exponent is median 0.20 (IQR 0.13 to 0.28).
* The exponent is larger in light wind (0.22 at 5-10 kt) than in strong wind (0.15 at 15 kt and above), and larger morning and evening (0.24) than midday (0.18), as boundary-layer physics expects.
* Direction veers +4 degrees with height (median).
* Implication: the primary 1/7 exponent understates headwind at height in light wind. Estimated airspeed (C5a, C5b) is the only measure affected. The pre-registered sensitivity range (0 and 1/4) brackets the observed median. Proposed: keep 1/7 as registered and add the observed 0.20 as a further sensitivity.

Synthetic noise model (q2_synthetic.py): 432 scenarios (straight-in and pattern, 65 and 90 kt, injected lateral, glide-path, descent-rate and speed deviations, calm and 15 kt crosswind), each degraded 20 times per sensor case.

| Sensor case | S bias | S spread (half the 5-95% range) | Agreement on S above 1 |
|---|---|---|---|
| 25 ft altimeter, NACp 10 | +0.02 | 0.31 | 99.0% |
| 100 ft altimeter with calibrated GNSS heights | +0.03 | 0.34 | 98.6% |
| NACp 9 | about +0.05 | about 0.46 | about 96% |

* Descent rate is the noisiest criterion. Gate C4 spread is 0.51. The 5 s median understates large swings by about 12% (true 0.89, measured 0.78), so C4 errs on the conservative side.
* Speed stability C5b has a noise floor of about +0.13 (about 1.3 kt of range).
* Lateral below the gate is reliable at NACp 10 (bias +0.11) but not at NACp 9 (bias +0.35, 76% agreement). Proposed: report C1 results with NACp 9 approaches left out as a sensitivity. NACp 10 covers 70% of piston approaches.
* Steady 15 kt crosswind with constant airspeed: C5b 0.21 in wind against 0.21 calm (straight-in), and 0.26 against 0.20 (pattern). The track-headwind correction works.
* Resolution, straight-in, calm: lateral 150 ft reads 0.74 (true 0.75), glide path 150 ft reads 1.78 (true 1.78), speed swing 6 kt reads 1.24 (true 1.20).

### 2026-10-02, Q2 sanity review by Benjamin (30 approaches) and the fixes it led to

Review page: q2_review/, version 2 (replay with severity zones). Benjamin's answers were exported to q2_review/answers/. The design was blind: he rated each approach before seeing its score.

Results, scored against the measures as they stood before the fixes below:
* The score ranks approaches the way a pilot does. Spearman correlation between S and the blind 4-level rating is 0.73.
  * Rated stabilized (9): S 0.43 to 0.79, apart from R24 (1.96, speed only) and R27 (7.55, choppy data).
  * Rated minor deviations (11): median S 2.04.
  * Rated not stabilized (8): S 2.98 to 10.05.
  * Rated far off (2): S 7.48 and 10.89.
* "Does the score match what you see?": yes on 29 of 30. The exception is R27, where the score was too harsh and he noted choppy data on final.
* Calibration: approaches with S between about 2 and 4 look like minor deviations to a pilot, most of them late turns to final. Every approach he called not stabilized had S of 3 or more. The AC 120-82 style marks (above 1 and above 2) are therefore stricter than a pilot's eye. This is kept as a finding. The marks stay as pre-registered.
* The element that set S was among the problems he picked on 19 of 30 approaches. On every approach with S above 1 it matched, except R24 (speed), R27 (track, data problem) and R30 (track at 2.0x, he saw nothing wrong).
* The practice-maneuver flag fails. He identified 3 possible practice approaches (R01 power-off, R02, R05 short or soft field), and the automatic flag caught none of them. The flag fired on 9 others, all of which he rated as genuinely not stabilized or minor, none as practice. The P1 rule (late, close-in turn to final) picks up tight patterns, not practice. Decision: the flag is reported only as a descriptor ("late close-in turn to final", "steep descent"), not as practice. The with-and-without sensitivity is kept for transparency, with this validation result next to it.

Measurement problems found (R27, R02, R01, R11, R29):
1. Frozen velocity. Some aircraft stop sending velocity while position updates continue, and the trace repeats the last ground speed and track. On R27 the repeated track put the airplane 75 degrees off the runway at 300 ft when its positions show it finishing the turn. In a sample, 3.0% of points carry the same (ground speed, track) for more than 5 s.
   * Fix: those points get track and ground speed from positions, and their vertical rates are dropped.
2. Height glitches. GNSS heights with single or double-point jumps of about 100 ft (R02, R01).
   * Fix: a Hampel filter on a symmetric window (up to 3 points each side within 12 s, point included, 50 ft threshold). It never trips on a steady climb or descent.
   * Frozen heights (same value for more than 8 s while the reported rate is 300 fpm or more) are dropped.
   * A first version with an asymmetric window dropped real points on descents with uneven sampling. It was caught on R28 and replaced before any use.

Effect of the fixes:
* Measurable approaches go from 308,500 to 299,930 (-2.8%). The cleaner filters leave approaches like R21 without valid heights at the gate.
* R27 S goes from 7.55 to 4.23. It still turns final at about 300 ft, and its positions confirm that.
* R09 2.98 to 2.90, R05 2.38 to 2.50, R26 0.64 to 0.72. All other reviewed approaches are unchanged.
* Spearman with the blind ratings after the fixes: 0.74 (29 measurable).

### 2026-10-02, Q2 wind analysis plan (set before the run)

Script q2_wind.py, input q2/approaches.csv after the fixes above.

Population (primary, as pre-registered in q2_measures.md): piston GA, VMC at the gate, measurable at 300 ft, the seven airports inside their Q1a windows (PYM to 2026-08-02).

Wind at the gate: one-minute ASOS two-minute wind as a crosswind and headwind component on the runway used, gust spread = five-second gust minus sustained. Crosswind is also expressed as a fraction of the aircraft's POH max demonstrated crosswind (published and family values).

Outcomes: S (primary), each criterion ratio at the gate and below it, M3 alignment below 300 ft, M2 overshoot past the centerline, M4 variability.

Reporting:
1. Distributions by crosswind band (0-4, 5-9, 10-14, 15 kt and above), by fraction of max demonstrated (0-0.25, 0.25-0.5, 0.5-0.75, 0.75 and above), by gust spread band (0, 1-4, 5-9, 10 kt and above) and by headwind band.
   * Statistics: median, p90 and p99 of S, and the share above 1 and above 2.
   * 95% intervals by cluster bootstrap over aircraft and, separately, over days, 500 resamples each. The wider is reported.
2. Models: logistic regressions for S above 1 and S above 2.
   * Wind terms: piecewise-linear crosswind (knots 5, 10, 15), linear headwind and gust spread.
   * Controls: airport-runway, aircraft type (C172, P28A, SR20, SR22 and S22T, C182, P28R, other), ownership (fleet, private, other), season, straight-in or pattern, and height source.
   * Predictions are average predicted shares at crosswind 0, 5, 10, 15 and 20 kt, with an aircraft-cluster bootstrap (200 resamples).
   * The same logistic model on log S, by OLS with aircraft-clustered standard errors, gives the shift of the whole distribution.
3. Machine-flown floor: the same distributions and models for jets on straight-in approaches. GA effects are reported next to the jet effects and as the difference.
4. Calibration against Q1: S at calm (0-4 kt), at the revealed limit (10 to 12 kt band, around the 10.8 kt model-free 50% point), and at or above the POH max demonstrated crosswind.
5. Breakdown: share of each criterion above 1, by crosswind band.
6. Benjamin's direction hypothesis (M6): M2 overshoot (median and share above 200 ft) and M3 alignment below 300 ft, by crosswind signed relative to the base side (-15 to +15 kt in 5 kt bins). Pattern approaches with an identified base leg only. Logistic model of overshoot above 200 ft on wind from the base side and wind from the far side as separate slopes, with the same controls.

Sensitivities:
* LWM out, with BED from 2025-07 (pilot memo recommendation).
* Straight-in only.
* Approaches with the late-turn descriptor flag left out.
* 25 ft altimeters only, and calibrated GNSS heights only.
* NACp 10 only.
* True height (s_true).
* Floor at 50 ft (s_below50).
* Single-report descent rate (s_c4raw).
* Lateral tolerance 100 and 300 ft, and vertical tolerance 75 and 150 ft, recomputed from the criterion ratios.

Not defined here, and left to Benjamin: a single "actual limit" number. The run reports the full curves and the comparisons in item 4, and the definition gets logged before it is computed.

### 2026-10-02, Q2 wind results (q2_wind.py, plan logged above; q2_wind/summary.txt)

Primary population: 163,361 measurable piston approaches. Floor: 37,724 jet straight-in approaches.

Performance degrades with crosswind, steadily but modestly over the range pilots actually fly.

| Crosswind | Median S | Share above 1 | Share above 2 | n |
|---|---|---|---|---|
| 0-4 kt | 1.19 | 63.2% | 19.0% | 122,231 |
| 5-9 kt | 1.23 | 65.4% | 20.5% | 37,049 |
| 10-14 kt | 1.30 | 70.2% | 22.5% | 3,563 |
| 15 kt and above | 1.42 | 77.2% | 28.3% | 127 |
| Above POH max demonstrated | 1.61 | 83.3% | 34.7% | 72 |

* Model (logistic, all controls), predicted share above 1: 62.8% at calm, 68.2% at 10 kt, 77.4% at 15 kt. Share above 2: 18.8%, 22.4%, 24.6%.
* log S rises 4.3% per 5 kt of crosswind (3.4 to 5.2) for piston aircraft and 1.3% (0.2 to 2.4) for the jet floor. The difference, 2.9% per 5 kt (1.5 to 4.3), is the part not explained by measurement and physics.
* Jets' share above 2 does not rise with crosswind (5.5% at calm, 3.0% at 10-14 kt).
* Elements that degrade most with crosswind:
  * Speed stability before 300 ft: 27.9% above 1 at calm against 40.3% at 15 kt and above.
  * Sink rate below 300 ft: 37.5% against 43.3%.
  * Lateral variability on final: median SD 17 ft against 24 ft.
  * Centerline at 300 ft moves little: 10.0% against 12.6%.
* Headwind lowers S and tailwind raises it. Share above 2 is 25.3% with a tailwind component and 15.8% at 10-14 kt headwind. Gust spread has a small effect: odds ratio 1.12 per 5 kt for S above 1, 1.04 for S above 2.
* Calibration against Q1: at the revealed limit (10-12 kt, where activity halves) the share above 2 is 21.7%, against 19.0% at calm. Pilots cut their flying in half well before performance moves much.
* Benjamin's direction hypothesis is confirmed. Pattern approaches with a base leg (119,593):
  * Overshoot past the centerline by more than 200 ft: 1.5% with 10-15 kt from the far side, 4.5% near calm, 14.0% with 10-15 kt from the base side.
  * Logistic odds ratio per 5 kt: 1.89 (1.79 to 2.00) for wind from the base side, 0.57 (0.51 to 0.63) for wind from the far side.
  * Wind from the far side shows up as late alignment instead: lined up below 300 ft or never 37.3% at 10-15 kt from the far side against 23.9% from the base side.
  * Crosswind direction decides how the approach goes wrong. Q1's go/no-go follows magnitude only.
* Sensitivities, odds ratio per 5 kt crosswind for S above 2, all between 1.09 and 1.14 with intervals above 1:
  * LWM out and BED from July 2025, 25 ft altimeters only, calibrated GNSS only, NACp 10 only, true height, floor at 50 ft, single-report descent rate.
  * Lateral tolerance 100 or 300 ft, and vertical tolerance 75 or 150 ft.
  * Late-turn descriptor flag out: 1.13. Straight-in only: 1.03 (0.95 to 1.12) for S above 2, but 1.11 (1.07 to 1.16) for S above 1. Straight-in approaches rarely reach 2 (6.2%).

Exploratory, not pre-registered:
* Share above 3, the mark where Benjamin's review began calling approaches not stabilized: 9.0% at calm, 9.5% at 10-14 kt, 10.2% at 15 kt and above, 20.8% above max demonstrated.
* Within-aircraft (linear probability with aircraft fixed effects, 2,684 aircraft): S above 2 rises +1.61 points per 5 kt (1.10 to 2.11), the same as the pooled +1.62. log S +4.4% per 5 kt. The aircraft that fly in wind do not differ from those that do not. Pilot self-selection on the day (who chooses to go) is not ruled out. It would make these estimates conservative.

### 2026-10-02, what is behind "63% outside tolerance at calm" (exploratory breakdown, Benjamin asked)

Piston approaches at 0-4 kt crosswind (122,231). S above 1 means any of nine checks (five at 300 ft, four from 300 to 100 ft) went past its tolerance at any point.
* By number of checks: exactly one 20.1%, two 15.3%, three or more 27.7%.
* Position and path checks only (centerline, lined up, glide path): 34.4%. Jets on straight-in approaches: 0.5% on the same checks, so this part reflects the flying, not measurement noise. Pattern approaches are worse than straight-ins (68.9% against 44.2% on the full score), mostly late turns to final.
* Sink rate and speed stability add the rest. These are the two checks that machine-flown jets also fail (25.7% of jets above 1, nearly all on these two).
  * Sink rate: the check compares with the rate a 3 degree path needs. Piston pilots fly a median 546 fpm at 300 ft where the path needs 377 fpm, a steeper-than-3-degree approach that is normal GA technique. Against the AFH wording (generally 500 to 1,000 fpm), 5.0% exceed 1,000 fpm.
  * Speed stability: a 10 kt range in the 30 s before 300 ft includes the usual slowdown to approach speed on final. It is the most common lone exceedance (9.2% of approaches).
* Above 3 times tolerance, where Benjamin's review started calling approaches not stabilized: 9.0%.

Implication: 63% is the union of nine strict checks applied continuously, not "63% of approaches were unsafe". The wind effect holds under every variant (sensitivity section above). Proposed, pending Benjamin: report levels in three tiers (position and path only, full score, above 3 times as the pilot-calibrated mark), and add an AFH-literal sink-rate variant (fail only outside 500 to 1,000 fpm) as a sensitivity, logged before it is run.

### 2026-10-02, framing: training flights stay in, and where crosswind practice happens (exploratory)

Benjamin: training flights are real flights with real risk, and flying in crosswind is the only way to learn it. Schools stay in the population as pre-registered, and results are reported for fleet and private separately. The data show fleet aircraft are not lower quality: S above 2 at calm is 17.7% for fleet against 21.2% for private, and the wind effect is the same.

Exploratory check: share of first arrivals that turn into pattern sessions (3 or more approaches), by crosswind at the first approach.
* Fleet: 26.3% at 0-4 kt, 25.1% at 5-9, 20.2% at 10-14, 11.3% at 15 kt and above (53 visits).
* Private: flat, 11.9%, 11.6%, 10.5%, 8.8%.

Fleet pattern work falls as crosswind rises, consistent with school crosswind limits and with fleet's lower revealed limit (10.3 kt against 11.7). Crosswind practice in the data happens mostly in the 5-9 kt band. Limitation: ADS-B cannot tell a dual lesson from a solo flight.

### 2026-10-02, audit of sink rate (C4) and speed stability (C5b) (Benjamin's request; q2_audit.py, q2_audit/summary.txt)

Variants were computed for every approach (new columns only, primary S unchanged on all 562,397 rows) and judged on how often they fire in calm crosswind, how often they fire on autopilot-capable jets, agreement with Benjamin's blind review, and the wind effect.

Each criterion alone, calm crosswind, share above 1 (piston / jets):
* C4 registered (3 degree path rate, plus or minus 300 fpm): 39.9% / 4.9%. Piston pilots fly a median 512 fpm between 300 and 100 ft (p10 320, p90 832), steeper than a 3 degree path (about 370 fpm at their speeds). The check flags steady steep approaches. It fired on 4 of the 5 approaches Benjamin tagged for sink rate, and on 7 he did not tag.
* C4 AFH-literal (1,000 fpm sink, or level flight, as the edge): 8.8% / 4.4%. Caught 1 of his 5.
* C4 steadiness (more than 300 fpm from the approach's own median rate): 12.6% / 3.1%. Caught 2 of 5.
* C4 AFH plus steadiness: 17.9% / 6.7%. Caught 2 of 5.
* C5b registered (10 kt range over 30 s): 24.6% / 21.9%. Jets fail it almost as often as pistons, so it measures ground-speed changes from wind and deceleration, not piloting. Detrended: 4.7% / 13.2%. 15 s window: 3.9% / 8.2%. None of the speed variants agreed with his speed tags (at most 1 of 5). GA ADS-B carries no airspeed, so every speed check rests on an estimate.

Full score, calm piston share above 1 / above 2 / above 3, jets above 1, Spearman with the blind ratings, odds ratio per 5 kt for S above 2:
* Registered: 63.2 / 19.0 / 9.0%, jets 25.7%, 0.743, 1.109.
* Speed check out, sink rate registered: 54.0 / 17.2 / 8.7%, jets 5.3%, 0.691, 1.111.
* Speed check out, sink rate AFH plus steadiness: 43.5 / 13.0 / 7.8%, jets 7.1%, 0.690, 1.123.
* Speed check out, sink rate steadiness only: 42.2 / 12.9 / 7.8%, jets 3.6%, 0.740, 1.125.
* The wind effect is the same under every one of the 16 combinations (odds ratio 1.10 to 1.13 per 5 kt, all intervals above 1).

Recommendation, pending Benjamin:
1. Take speed stability out of S and report it with the other secondary airspeed measures.
2. Replace the sink-rate check with "steady and not excessive": no more than 1,000 fpm, no leveling off, and no swing of more than 300 fpm from the pilot's own rate. Being too high or low is already covered by the glide-path check.
3. Lock the amended score before the US-wide run and use it as primary there. The US sample is new data, so it serves as the confirmatory test. For New England, report the registered score and the amended one side by side, with the reason for the change.

### 2026-10-02, decisions: US-wide expansion and a full paper by 12 November

Benjamin decided:
* Run the US-wide expansion now ("if it's just a matter of downloading and we have the space and processing power, run it").
* Aim for a full draft paper by the AIAA AVIATION 2027 deadline of 12 November 2026. A draft manuscript is accepted in place of the extended abstract.

Candidates (us_candidates.py, reference/us_candidates.csv): 789 public-use airports in the contiguous US with an ASOS and a paved runway of 2,500 ft or more. 421 have a tower. All seven New England study airports are included.

Weather download started for 2025-09 to 2026-09: METARs, then one-minute ASOS (fetch_metar.py, fetch_onemin.py, logs/us_metar.log, logs/us_onemin.log).

The track period will be the last 12 months (2025-10 to 2026-09), when feeder coverage is best. Airports enter the analysis by the 300 ft coverage rule.

Methods from New England are frozen for the US run: detector v3.0.1, measures after the review fixes, and the amended score if Benjamin accepts it. New England is the development sample, the US the confirmatory sample.

Validation needed for the US run:
* A labeling round of about 100 visits at airports unlike New England.
* Tower-count spot checks at a sample of towered airports.

### 2026-10-02, sink rate and speed as value plus consistency (Benjamin's direction)

Benjamin: speed stability and sink rate should each be a deviation amount, measuring consistency as well as the actual value.

Definitions (b_c5a added to q2_measures.py as a new column. Every existing score is unchanged on all 562,397 rows):
* Sink rate, value: 1,000 fpm sink is the edge on the steep side and level flight on the shallow side (AFH, FSF), at 300 ft and the worst point down to 100 ft.
* Sink rate, consistency: the largest swing from the approach's own median descent rate between 300 and 100 ft, tolerance 300 fpm.
* Speed, value: estimated airspeed against the POH approach speed plus half the gust spread, tolerance -5/+10 kt, at 300 ft and the worst point down to 100 ft.
* Speed, consistency: the range of estimated airspeed around its straight-line trend over the 30 s before 300 ft, tolerance 10 kt. A steady slowdown to approach speed does not count.

Results, piston, share above 1 / above 2 / above 3 by crosswind band (0-4, 5-9, 10-14, 15 kt and above):

| Score | 0-4 kt | 5-9 kt | 10-14 kt | 15 kt and above |
|---|---|---|---|---|
| Flight path (centerline, lined up, glide path, sink value and consistency) | 43.5 / 13.0 / 7.8 | 45.8 / 13.9 / 8.4 | 48.9 / 14.3 / 8.4 | 59.8 / 15.0 / 7.1 |
| Speed (value and consistency) | 45.6 / 7.6 / 1.2 | 46.0 / 7.3 / 1.2 | 49.6 / 9.8 / 1.4 | 67.5 / 25.4 / 8.7 |
| Speed consistency alone | 5.3 / 0.3 / 0.1 | 6.2 / 0.3 / 0.1 | 10.3 / 0.5 / 0.2 | 21.0 / 4.2 / 1.7 |
| Combined | 67.7 / 19.3 / 8.9 | 68.9 / 20.0 / 9.5 | 71.5 / 22.3 / 9.7 | 82.7 / 34.6 / 14.2 |

* Speed value at calm: piston pilots fly a median 7.2 kt above the POH approach speed (range midpoints used as targets). 34.5% are more than 10 kt fast and 3.7% more than 5 kt slow, at 300 ft.
* Speed consistency is the most crosswind-sensitive element, 5.3% to 21.0% above 1. Jets on the same check go the other way (14.3% at calm, 7.1% at 15 kt and above), so the piston rise is not a measurement artifact of the airspeed estimate. Light airplanes do respond more to turbulence than jets, so the rise is part piloting and part airframe.
* Odds ratio per 5 kt crosswind: flight path 1.12 for above 2 and 1.10 for above 1. Speed 1.05 (0.99 to 1.11) for above 2 and 1.10 for above 1. Combined 1.09 and 1.12.

Proposed lock for the US confirmatory run, pending Benjamin's OK:
* Primary S: the flight-path score (all directly measured).
* Speed score: reported next to it for every result, as its own outcome, since it rests on estimated airspeed. The combined score is reported as well.
* Registered New England results stay in the record next to these.

### 2026-10-02, LOCKED before any US-wide data is analyzed: Q2 outcomes and the US confirmatory plan

Benjamin agreed ("Okay good with me"). Everything below is fixed before the US tracks are downloaded. New England (2023-02 to 2026-09) was the development sample. The US sample (2025-10 to 2026-09, 789 candidate airports) is the confirmatory sample. Changes after US results go into this log with a reason and are reported as post-hoc.

**Primary Q2 outcome: flight-path score S_fp.** It is the largest of:
* C1 centerline (200 ft), C2a lined up (10 degrees), and C3 glide path (100 ft), at 300 ft and the worst point from 300 down to 100 ft.
* Sink value: 1,000 fpm sink is 1x on the steep side (ratio = sink / 1,000). Level flight is 1x on the shallow side (ratio = (path rate - sink) / path rate). Measured at 300 ft and the worst point down to 100 ft. Columns g_c4_afh, b_c4_afh.
* Sink consistency: the largest swing from the approach's own median sink rate between 300 and 100 ft, divided by 300 fpm. Column c4_stab.

**Speed score S_spd**, reported next to S_fp for every result. It is the largest of:
* Speed value: estimated airspeed against the POH approach speed (range midpoint) plus half the gust spread. A deficit is divided by 5 kt, an excess by 10 kt. Measured at 300 ft and the worst point down to 100 ft. Columns g_c5a, b_c5a.
* Speed consistency: the range of estimated airspeed around its straight-line trend over the 30 s before 300 ft, divided by 10 kt. Column g_c5b_detr.

Estimated airspeed = ground speed + surface wind component along the track, scaled to height with the 1/7 power law. Exponents 0.20 (observed at pattern height) and 1/4 are sensitivities.

**Combined score**: the larger of S_fp and S_spd, reported as a sensitivity.

**Second outcome: the turn to final, S_turn.** For pattern approaches with an identified base leg (track at least 60 degrees off the runway course before alignment, base side at least 100 ft off the centerline). It is the larger of:
* T1 overshoot: the largest excursion past the centerline on the far side from the base leg, from the start of the turn to alignment, divided by 200 ft. Column overshoot_ft.
* T2 late alignment: 300 ft divided by the height above threshold at which the airplane is first aligned and stays aligned (C1 and C2a at or below 1). Aligned at 300 ft gives 1.0, at 150 ft 2.0, at 600 ft 0.5. Never aligned uses the lowest observed height (at least 50 ft). Capped at 6.

The secondary turn measure is the largest inferred bank in the turn (estimated from turn rate and estimated airspeed), divided by 30 degrees, with 45 degrees as a sensitivity. The AFH describes a medium-bank turn onto base. It lists "an overshooting, undershooting, too steep, or too shallow a turn onto final approach" and "a skidding turn from base leg to final approach as a result of overshooting/inadequate wind drift correction" as common errors.

**Reference marks and reporting.** 1x and 2x as before. 3x is reported as the pilot-calibrated mark from Benjamin's review. Distributions (median, p90, p99, shares above 1, 2 and 3) are reported by crosswind, by crosswind as a fraction of max demonstrated, by gust spread, by headwind, by ownership, and by single arrival against pattern session. The models are the same as in the New England plan, applied to each outcome.

**Practice flag**: reported as a descriptor only (validation failed).

**US airport and day inclusion**
* Period: 2025-10-01 to 2026-09-30, local hours 08 to 18 for Q1a. Candidates as in reference/us_candidates.csv.
* An airport-month enters when its share of fixed-wing airport-traffic visits seen to 300 ft is at least 0.60 that month. This uses the coverage measure of coverage_monthly.py, applied per month instead of as a running window, since the period is one year.
* Outage days: days whose coverage to 300 ft is below half of that airport's median across included months. They are excluded and counted.
* Airports with fewer than 200 measurable piston approaches in included months are dropped from airport-level tables but kept in pooled results.
* Unusable runways: runway ends under 2,500 ft or unpaved are left out of best-runway crosswind for Q1a, as fixed for TAN.

**Q1a.** Primary: the model-free revealed limit, with arrivals over normal demand in 2 kt crosswind bins and a day-cluster bootstrap. Second: the spline Poisson model. The log-linear model is reported as registered for New England. Baselines: airport by season by day type by hour over VMC hours, cells with fewer than 8 hours dropped. Per-airport limits are reported where reached. Results are pooled by tower and non-tower, and by region (FAA regions).

**Q1b.** Same rules as New England.

**Validation for the US run** (pilot criteria carried over):
* Detector: a blind labeling set of 100 visits from at least 10 included airports outside New England, chosen at random from those stratified by tower status and region, seed 20261010. The criterion is 90% visit agreement for detector v3.0.1, unchanged.
* Tower counts: OPSNET at up to 20 towered included airports where obtainable. The capture-vs-weather test is repeated on them.
* Measurement checks: repeated on the US data (barometric against GNSS height by gust, NACp, measurability against wind, jet floor).

### 2026-10-02 17:40, US processing complete, inclusion applied

* us_pipeline.py processed 364 of 365 days (2026-05-06 has no archive release) for 755 airports with traffic. Extracts: q2_extract_us/ (40 GB).
* One-minute ASOS is complete for all 9,468 station-months. 266 station-months hold no data (no one-minute archive at that station that month) and fall back to METAR.
* The coverage rule (monthly share seen to 300 ft of at least 0.60) includes 467 airports (309 towered, 158 non-towered, in all eight FAA regions) and 3,871 airport-months. 219 airports have all 12 months. 5,442 outage airport-days are excluded.
* Data correction, the same one applied to New England: PYM is excluded from 2026-08-03 (06/24 closure, then full closure). The US rules did not carry the New England PYM exclusion over, and without it the best-runway crosswind would count a closed runway. Other runway closures in the US sample are unknown to us. This is a limitation.
* Engineering notes, no effect on results: the first pipeline run failed on memory (48 workers, 7 longitude bands) and was rerun with 18 bands and 32 workers. The early distance check in extract_points gives byte-identical New England extracts. The one-minute downloader's shared temp-file name caused one crash and was fixed (per-process names).

### 2026-10-02 18:00, Set 4 (US detector validation) built and published

make_labeling_set_us.py, seed 20261010, by the locked rule:
* 100 visits (ids U001 to U100) at 14 included airports outside New England, one towered and one non-towered per FAA region.
  * ACE: SLN and IOW. AEA: RME and PBG. AGL: BKL and ZZV. ANM: SFF and LND.
  * ASO: ILM and FFC. ASW: BAZ and MLC. AWP: SDL and PRB.
* Visits come from 30 random included days, 2025-10-02 to 2026-09-14.
* Eligibility and the at-most-2-per-aircraft rule are the same as Sets 1 to 3.
* key.csv stays on the server. The labeler (artifact JYKoqCpeuu1epoYfb3EViZ, version 6) has a "Set 4 (US)" button.
* Criterion: 90% visit agreement for the frozen detector v3.0.1, scored once with score_labels.py, raw labels reported. No detector changes follow from this set: it is a confirmatory check only.

### 2026-10-02 18:15, US Q1a results (confirmatory; us_q1a.py, q1a_us/summary.txt)

Sample: 927,905 VMC airport-hours at 441 airports, 2.88 million piston arrivals. Wind from one-minute ASOS for 78% of hours, METAR for the rest.

| Estimate | US (confirmatory) | New England (development) |
|---|---|---|
| Model-free 50% point, piston (primary) | 11.6 kt (11.3 to 11.8) | 10.8 kt (10.3 to 11.5) |
| 75% point | 8.2 kt | 8.0 kt |
| Fleet | 11.0 kt (10.7 to 11.3) | 10.3 |
| Private | 12.6 kt (12.2 to 13.2) | 11.7 |
| Gust crosswind 50% point | 21.2 kt (20.9 to 21.5) | 21.1 |
| Towered | 11.8 kt | |
| Non-towered | 10.6 kt | |
| Spline model, 50% point | 13.5 kt (13.2 to 14.0) | 12.6 |

* By FAA region:
  * Eastern (AEA) has the lowest 50% point, 9.3 kt.
  * Then New England (ANE) 10.6, Northwest Mountain (ANM) 11.0, Central (ACE) 11.2 and Great Lakes (AGL) 11.5.
  * The highest are Western-Pacific (AWP) 12.6, Southwest (ASW) 13.1 and Southern (ASO) 13.3.
  * The US New England region (10.6 kt) matches the development sample (10.8 kt).
* The registered log-linear model fails its fit check again: modeled 0.70 at 10-14 kt where 0.49 was observed, and 0.57 at 15-19 kt where 0.24 was observed. Its 50% point is 27.2 kt. That confirms the development-sample reason for making the model-free curve primary.
* Findings that replicate: the fleet-private gap, the gust-crosswind limit, and non-towered fields sitting below towered ones.
* The 20 kt-and-above bin (299 hours) shows activity back up at 0.57 of normal. With so few hours, this is more likely wind-sensor or runway-choice artifacts than behavior. Flagged for checking, not interpreted.

### 2026-10-02 18:40, Set 4 (US) result: detector criterion NOT met at the visit level

Benjamin labeled all 100 visits blind. Scored once (score_labels.py labeling/export_us_BD_raw labeling/us), frozen detector v3.0.1, raw labels:
* Visit agreement: 84% (84/100, Wilson 95% CI 75.6 to 89.9), below the 90% criterion. New England Set 3 was 92%. 84.4% excluding the 4 visits marked too little data.
* Events: recall 90.8% (148/163), precision 89.2% (148/166).
* By airport: ILM, IOW, MLC, SDL, ZZV 100%. BKL 4/7, PBG 4/7, SLN 5/8, RME 5/7.

What the 16 disagreements are:
* Climb-outs, which no Q1 or Q2 analysis uses: 10 missed and 10 extra. Five are departures the detector did not see (RME, PBG, FFC). Two are runway direction for a departure (SFF 04L against 22R, BKL 24R against 06L, the second marked unsure by Benjamin). The rest are climb-outs added after what he judged full stops.
* Runway assignment for approaches:
  * SLN U022: three approaches put on 18 where he says 17. The two runways are within 10 degrees of each other.
  * PRB U088: 19 against 13.
* Approach count: U072 (PBG) missed one. Four extra: BAZ U014, SLN U035 (a straight-in to 30 that turned to 17, his note), BKL U081 (6 against 5), and BKL U078, a visit he marked too little data.

The parts the analyses use:
* Arrival detection (a visit has at least one approach, the Q1a unit): 97/100 agree.
* Approach events ignoring runway: recall 98.8% (80/81), precision 95.2% (80/84).
* Approach events on the right runway: 93.8% (76/81).

Reporting: the visit-level criterion failed in the confirmatory sample and is reported as such. The detector stays frozen, as locked. The paper reports the arrival-level and approach-level figures because they are what Q1a and Q2 rest on.

Added before the US Q2 analysis is run: a sensitivity that leaves out airports with two distinct runways within 20 degrees of each other (parallels and near-parallels). A misassigned runway there would measure an approach against the wrong centerline.

### 2026-10-02 19:00, Set 4 disagreements checked against the tracks (Benjamin asked whether he mislabeled)

Each of the 16 disagreements was checked against the raw track: offset from each runway centerline on low passes, the departure direction, ground reports, and where the data starts and ends.

Label slips, where the track supports the detector (5):
* U022 SLN: all three passes are 8 to 17 ft from runway 18's centerline and 4,400 ft from 17. 17/35 and 18/36 are exactly parallel (both 180 true).
* U088 PRB: both passes are 6 to 56 ft from 19's centerline, not 13.
* U063 SFF: the climb heads 240 true, so it departed on 22R, not 04L.
* U080 BKL: the climb heads 055 true, so it departed on 06L, not 24R. Benjamin had marked it unsure.
* U070 SLN: two touch-and-go climb-outs on 36 between approaches were not counted. The airplane flew three approaches, so it must have climbed out between them.

Detector errors, where the track supports the label (7):
* U014 BAZ: a takeoff roll on 17 counted as an approach.
* U008 LND: a full stop (ground speed to 0, 139 ground reports) given a climb-out.
* U044 PBG: a missed climb-out. The airplane is later climbing 3 nm past the far end.
* U018 RME: a missed departure that turns at 200 ft over the runway.
* U051 RME: a missed departure with no velocity data in the trace.
* U035 SLN: a straight-in to 30 that turned to land on 17, counted as two approaches.
* U081 BKL: six approaches against five. The passes group into five circuits.

Not verifiable from the track (4):
* U061 PBG and U075 FFC: departures first seen at 1,300 to 1,400 ft.
* U072 PBG: the track ends on downwind at 800 ft, and the label infers the approach.
* U078 BKL: a pass 0.45 nm off the runway at about 700 ft, which Benjamin marked too little data.

Adjudicated result, correcting the 5 slips and keeping the raw labels on the 4 unverifiable visits: visit agreement 89% (89/100), still under the 90% criterion. Raw: 84%.
* Approaches on the right runway, adjudicated: 80 of 81 labeled. The one left is U072, unverifiable.
* The parallel-runway concern does not hold up. Both runway disagreements were label slips, not detector errors.
* Arrival detection is unchanged at 97/100.

Pending Benjamin's confirmation, as with the Set 2 adjudication. The paper reports raw and adjudicated figures side by side. The near-parallel sensitivity stays in the US Q2 plan.

### 2026-10-02 19:30, post-hoc data correction: one-minute wind quality filter (wind_qc.py)

Found in the US Q2 results: approaches in the 20 kt-and-above crosswind band had a median reported wind of 64 kt while flying normal 74 kt ground speeds. These are corrupted one-minute ASOS records, not real wind.
* The bad records cluster in a few station-months: ORF July 2026 (5,344 records above 40 kt), FWA June to August 2026, YIP October 2025.
* Across a station's year, 0.4% to 2.2% of records are affected. At BDR, none.
* The METAR from the same sensor does not show the spikes.
* The same contamination explains the Q1a uptick in the 20 kt-and-above bin (activity back to 0.57 of normal) and the 20 kt-and-above speed-score jump.

The filter, applied to every analysis that reads one-minute wind (q1a_crosswind.py, us_q1a.py, q2_measures.py). A record is dropped if:
* the two-minute wind is above 60 kt, or
* it differs by more than 15 kt from the nearest METAR within 30 minutes, or
* it differs by more than 15 kt from the median of the records within 5 minutes.

A station-month in which more than 1% of records fail is dropped whole: ORF July and August 2026, FWA June to August 2026, YIP October 2025. A five-second gust more than 40 kt above the sustained wind, or above 80 kt, is dropped while the sustained wind is kept. Dropped data falls back to METAR under the existing rules.

This correction is post-hoc. It was found after the US results and is applied to both samples. Every Q1a, Q1b and Q2 result is rerun with it, and the earlier figures stay in this log. The fault sits in the weather data, so it applies equally to every approach and needs no judgment about the flying.

### 2026-10-02 19:45, Set 4 adjudication confirmed (Benjamin)

Benjamin confirmed the five corrections as clerical labeling errors (labeling/us/adjudication.csv). Reported Set 4 result: 89% visit agreement (89/100), arrival detection 97/100, approaches on the right runway 80 of 81. Paper wording is neutral, with no attribution: reference labels were checked against the raw tracks and clerical errors (runway designation, omitted climb-outs) were corrected before scoring. Sets 2 and 4 are treated the same way, so Set 2 is reported adjudicated at 90%. The raw figures stay in this log only.

### 2026-10-02 20:00, Benjamin's notes on U072 and U078 checked against the tracks

* U072 PBG, label approach 17, with the note "midfield entry to a teardrop entry to the downwind of 17". NASR lists 17 as right traffic. The track ends at 800 ft AGL heading 330 to 348, 0.8 nm west of the centerline, abeam the threshold, descending. That is a right downwind for 17, so the track supports his reading of the pattern. The approach itself is past the end of the data, so the detector cannot see it. The label stands, and this counts as a detector miss caused by coverage.
* U078 BKL, relabeled from "no approach, too little data" to "approach 24R, too little data". NASR lists 24R as right traffic. The track ends at 717 ft AGL heading 046, 0.45 nm northwest of the runway, descending. That is a close, low right downwind for 24R. The detector's "approach 06L" took that downwind leg for an approach to the opposite end, so it is a detector error. His relabel does not side with the detector, so it does not inflate agreement.

Set 4 with the confirmed corrections and these revisions:
* Visit agreement 89/100.
* Arrival detection 98/100.
* Approach events: recall 98.8% (81/82), precision 96.4% (81/84).
* Approaches on the right runway: 80 of 82 (97.6%). The two left are U072, beyond the data, and U078, where the detector mistook the downwind for an approach.

A new failure mode for the paper's limitations: a low, close downwind leg (inside 0.5 nm, below 800 ft) can satisfy the detector's near-runway approach window.

### 2026-10-02 20:15, US tower counts received

Benjamin downloaded OPSNET daily counts for 20 towered GA airports picked across all FAA regions. Each was required to have all 12 US months included and at least half of its arrivals piston:
* SUS, IXD, SLN, FRG, TTN, LNS, GFK, DPA, FCM, APA, HIO, PAE, DAB, HWO, FXE, DTO, GKY, FTW, FFZ, SDL.
* Period 2023-01 to 2026-08. They overlap the US sample from 2025-10-01 to 2026-08-31.

Parsed into reference/opsnet/opsnet_daily.csv. The New England rows are unchanged (17,119 checked). An unrelated spreadsheet (a parts quote) arrived in the same folder and is ignored.

us_tower_compare.py repeats the New England counting rule: approaches plus climb-outs starting during tower hours, which come from NASR ATC_BASE TWR_HRS (seasonal schedules for FCM and FFZ). It then runs the capture-against-weather test on included days.

### 2026-10-02 20:30, results after the wind quality filter (final for this round)

New England (development):
* Revealed limit 10.8 kt (10.3 to 11.6), fleet 10.3, private 11.7, gust 21.0. Unchanged.
* Q1b sustained exceedance 0.04%.
* Q2 registered S: share above 2 rises from 19.0% at calm to 22.3% at 10-14 kt. log S +4.8% per 5 kt crosswind, jets +1.4%, difference +3.4% (2.0 to 4.8).
* Direction: overshoot odds ratio 1.79 per 5 kt from the base side, 0.54 from the far side.

US (confirmatory), 467 airports, 5.3 million measurable piston approaches:
* Q1a: 50% point 11.6 kt (11.3 to 11.8), fleet 11.0, private 12.7, gust 21.2, towered 11.8, non-towered 10.6. Eastern region 9.3, Southern 13.3. The 20 kt-and-above uptick is gone (0.17 of normal).
* Q1b: sustained 0.07% (0.07 to 0.08), gust 1.05%. Fleet and private equal. Non-towered lower (0.05%, 0.86%).
* Q2 flight path (S_fp, primary):
  * Share above 1 is 50.4% at calm, 53.3% at 10-14 kt, 56.5% at 15-19 kt. Above 2: 18.7%, 19.0%, 21.5%.
  * Model change against calm, above 1: +3.7 points at 10 kt, +6.8 at 15 kt. Above 2: +0.7 and +2.1.
  * Within-aircraft: +3.7 and +7.4 (above 1).
  * log S_fp +2.5% per 5 kt crosswind, against +1.4% for jets.
* Q2 speed (S_spd):
  * Above 1: 47.8% at calm, 54.9% at 10-14 kt, 60.7% at 15-19 kt. Above 2: 10.2%, 14.7%, 22.4%.
  * Model change against calm, above 1: +5.2 points at 10 kt, +13.1 at 15 kt.
  * Speed consistency above 1 rises from 6.0% to 15.7% (15-19 kt).
* Turn to final (S_turn), above 1: 39.5% at calm, 49.2% at 15-19 kt.
* Calibration:
  * At the revealed limit (11.6 kt plus or minus 1): S_fp above 2 is 19.0%, against 18.7% at calm.
  * Above max demonstrated (3,025 approaches): S_fp above 2 is 22.5%, S_spd above 1 is 74.0%.
* Direction replicates:
  * Overshoot above 200 ft: 1.0% with 10-20 kt from the far side, 3.0% near calm, 9.3% with 10-20 kt from the base side. Per 5 kt: +2.65 points from the base side, -1.04 from the far side.
  * Late alignment: 47.3% from the far side, 30.5% from the base side. Per 5 kt: +4.71 points from the far side.
* The 20 kt-and-above band now holds 264 measurable approaches. Its speed score stays high (median 2.0). This is treated as unreliable (estimated airspeed in very strong wind, possibly residual wind error) and not interpreted.

### 2026-10-02 20:45, exploratory analyses suggested by Benjamin (logged before running; reported as exploratory)

Prompted by his Discussion notes (paper/discussion_notes_benjamin.md). US sample, same inclusion as the confirmatory analyses.

* X1, round-number line at 10 kt. Arrivals over normal demand in 1 kt bins of hourly mean crosswind, 4 to 16 kt, for piston, fleet and private, with day-cluster bootstrap intervals. Also the same for total wind speed, since pilots read the wind before working out the crosswind. A line drawn at 10 kt predicts the drop per knot is steeper from 10 to 12 kt than from 8 to 10 kt, and more so for fleet, where school solo limits apply. The bootstrap gives the difference between the two slopes.
* X2, runway layout. Airports with one usable runway (paved, 2,500 ft or more) against airports with more than one. Compared on the model-free revealed limit (piston, fleet, private) and on the Q2 wind effects (S_fp, S_spd, S_turn change at 10 and 15 kt against calm), with the group difference and its interval.
* X3, crosswind climate. Per airport, the share of VMC hours (08 to 18 local) with mean best-runway crosswind of 10 kt or more. Airports in tertiles, with the same comparisons as X2.
* X4, home-field exposure. Each piston aircraft's home is the airport with most of its arrivals (at least 20 arrivals, at least half at home). Home exposure is the X3 share at the home field. The Q2 wind effects on approaches flown anywhere are compared by home-exposure tertile. This is the closest proxy for pilots trained where crosswind is common. Aircraft are not pilots, especially rentals.

### 2026-10-02, US tower-count result (us_tower_compare.py, frozen v3.0.1)

20 towered airports, 2025-10-01 to 2026-08-31, tower hours, fixed-wing only. 6,641 airport-days have OPSNET counts and 6,571 fall on included days. The comparison uses the 6,402 included airport-days with at least 30 tower operations. Output in us_tower_compare/.
* Pooled detected / tower operations: 0.970.
* Per airport: SUS 0.820, IXD 0.919, SLN 0.922, FRG 0.867, TTN 0.992, LNS 0.829, GFK 0.934, DPA 1.027, FCM 0.994, APA 1.090, HIO 1.014, PAE 0.978, DAB 0.977, HWO 1.143, FXE 0.944, DTO 1.019, GKY 0.910, FTW 0.743, FFZ 0.986, SDL 0.942.
* 17 of 20 are within 15 percent of the tower count. Below: FTW 0.743, SUS 0.820, LNS 0.829. Highest: HWO 1.143, APA 1.090.
* Daily correlation 0.79 (FXE) to 0.98 (GFK and FCM), 0.84 or higher everywhere except FXE.
* Capture against weather (pre-registered test, 6,121 airport-days with weather):
  * Mean wind: -2.6% per 10 kt (95% CI -4.8 to -0.4). PASS.
  * Mean best-runway crosswind: -3.5% per 10 kt (-7.1 to +0.2). PASS.
  * VMC share and precipitation share effects are near zero (all-VMC day -0.4%, all-precipitation day -3.0%, both intervals spanning zero).
* Conclusion: on included US days, archive counts track tower counts closely in level and from day to day. Capture does not fall with wind beyond the pre-registered bound, so US Q1a runs without a capture correction. As in New England, the residual (about -3% per 10 kt) is reported as a bias bound. It would make the drop-off look slightly steeper.
* Not yet explained: ratios above 1 at HWO and APA, and the shortfall at FTW. Candidates are tower-hour edges, helicopter and air-taxi mix, and how each tower counts practice approaches. A day-level spot check of each is planned before the paper.

### 2026-10-02, exploratory X1 to X4 results (us_exposure.py, q2_us_results/exposure_summary.txt)

Exploratory, as logged before running. 441 airports in the Q1a hours (109 with one usable runway). Crosswind ten knots or more on the best runway is rare in VMC daytime hours: the airport tertile cut points are 0.4% and 1.8% of hours.

* X1, round-number line at 10 kt:
  * Crosswind: no bend at 10 kt. Activity falls about 0.08 of normal demand per knot from 5 to 14 kt, the same slope on both sides of 10 kt. Piston drop per knot 0.076 (8 to 10 kt) and 0.073 (10 to 12 kt), difference -0.003 (95% CI -0.030 to +0.024). Fleet 0.083 and 0.083. Private 0.064 and 0.059.
  * Total wind speed: activity is flat to about 9 kt, then the drop steepens (0.029 per knot from 8 to 10 kt, 0.048 from 10 to 12 kt, difference +0.019, 95% CI +0.010 to +0.029). It keeps steepening past 12 and 14 kt, so this is a bend in a smooth curve, not a step at 10 kt.
* X2, one usable runway against more than one:
  * Revealed limits are lower with one runway: piston 10.9 kt against 11.9 kt (difference -1.0, approximate 95% CI -1.5 to -0.5). Fleet 10.5 against 11.3, private 11.6 against 13.2.
  * Q2 degradation is similar: log S_fp +1.8% against +2.7% per 5 kt (difference -0.9, about -1.5 to -0.3). log S_spd +4.3% against +4.1%. S_turn +0.6% against +1.3%.
  * Confounded by tower status, traffic mix and region. Not adjusted.
* X3, airport crosswind climate (tertiles):
  * Pilots at windier airports keep flying into more crosswind: piston limit 10.7 (low), 11.0 (middle), 11.8 kt (high), high minus low +1.1 (about +0.3 to +1.9). The gap is mostly private (10.9 to 13.0 kt, +2.1). Fleet changes less (10.5 to 11.1 kt).
  * Flight-path degradation per knot does not differ: log S_fp +2.3%, +2.6%, +2.7% per 5 kt.
  * Speed degradation is steeper at windier airports: log S_spd +3.3%, +4.1%, +5.2% per 5 kt, high minus low +1.9 (about +1.4 to +2.4). Estimated airspeed is less certain in gusty, windy places, so part of this may be measurement.
* X4, home-field exposure (14,607 piston aircraft with a home field, 4.2 million approaches):
  * No sign that aircraft based at windier fields degrade less. log S_fp +2.1%, +3.4%, +2.2% per 5 kt by home-exposure tertile (high minus low +0.1, about -0.4 to +0.6).
  * Speed again steeper with exposure: +2.8%, +4.0%, +4.7% per 5 kt.
* Approximate differences come from each group's interval, treating the groups as independent. X4 groups are disjoint aircraft. X2 and X3 groups are disjoint airports but share some aircraft.
* Reading for the Discussion: crosswind activity falls steadily, with no bend at 10 kt. Benjamin's 10 kt line appears, if anywhere, in total wind, where the decline starts to steepen near 9 to 10 kt. Exposure moves where pilots stop (windier home climates, later stop) more than how well they fly once there.

### 2026-10-02, US tower-count spot check of HWO, APA and FTW (post-hoc diagnostics, Benjamin asked)

Scripts: us_tower_spotcheck.py (what followed each detected pass), us_tower_spotcheck_traverse.py (inferred passes by class), us_tower_spotcheck_days.py (24 random compared days, full archive parse with rotorcraft), us_tower_spotcheck_plot.py (single-visit plots, local only). Outputs in us_tower_compare/. FAA counting rules checked in JO 7210.3EE 13-2-1 and 13-3-1 (copies in reference/faa/): a takeoff or landing is one count, and a touch-and-go, stop-and-go or low approach below pattern altitude is two. This matches the detector's approach plus climb-out rule.

* HWO (1.143): a detector duplicate. Rule 11 (traverse, a circuit whose touchdown falls in a coverage gap) checks for an existing pass on the same runway end only. HWO has two pairs of short parallels 0.24 nm apart, and the archive loses aircraft there around 100 to 200 ft, so 22% of its passes are inferred. When a touch-and-go on 28L falls in a gap, the rule adds an approach and a climb-out on 28R as well. These duplicates are 13.9 operations per 100 tower operations. Without them HWO is 1.005. Confirmed by eye on plotted circuits (us_tower_compare/spotcheck_tracks/). The same happens at DTO (parallels, 10.9 per 100, 1.019 without them is 0.910). Elsewhere duplicates are 1.2 per 100 or less.
* FTW (0.743): helicopters. The 24 sample days hold 2,412 helicopter visits, about 100 a day. Towers count helicopter operations, and the detector leaves rotorcraft out by design. Helicopter touchdowns and liftoffs the archive sees add 15.0 operations per 100 tower operations (adjusted 0.894). The rest is most likely helicopter operations not seen near the ground. Fixed-wing detection at FTW is clean: 95% of approaches reach the runway, 96% of climb-outs start from it, and 0.1 per 100 seen touchdowns and liftoffs have no detected pass.
* APA (1.090): not explained by the detector. 97% of approaches reach the runway, 97% of climb-outs start from it, parallel duplicates 0.4 per 100, rotorcraft 1.5, missed touchdowns and liftoffs 0.9 per 100. The excess is steady across tower-volume quartiles (1.08 to 1.10) and weekday or weekend (1.09, 1.08), and varies by month (1.02 to 1.16). Most likely a counting difference on the tower side, which cannot be checked without the tower's records. It is inside the 15 percent band.
* SUS (0.820), not asked: archive coverage. Only half its approaches are seen to 150 ft (seen to 300 ft 0.82), and rotorcraft are 1.0 per 100.

Knock-on finding for Q2. Inferred approaches (rules 5, 6, 11) were measured like observed ones whenever the track passed the measurability checks. In the primary Q2 sample (piston, VMC, measurable, 5,308,201) they are 1.9%: traverse 78,482, end 11,948, gap 11,746. They score as near-certain failures (S_fp median 6.0 to 7.4, 91 to 94% above 2) against 0.99 and 17.0% for observed approaches. Most are the parallel duplicates above, measured against the wrong centerline (0.24 nm off is about seven times the 200 ft lateral mark). Concentrated at HWO (11.1% of its sample), DTO (11.2%), PRC (17.8%), AFW (23.9%), BFL (24.3%), LVK, DWH and SFB.
* Sensitivity (us_q2_inferred_check.py, q2_us_results/inferred_check.txt): excluding them leaves every wind effect unchanged. S_fp above 1 at 15 kt +6.9 points (reported +6.8). S_fp above 2 at 15 kt +2.0 (+2.1). log S_fp +2.4% per 5 kt (+2.5%). S_spd and S_turn are the same to 0.1.
* Levels drop by about one point: S_fp above 2 is 17.3% at 0-4 kt, 17.3% at 10-14 kt, 20.1% at 15-19 kt (reported 18.7, 19.0, 21.5). Above 1: 49.5, 52.3, 55.7% (reported 50.4, 53.3, 56.5).
* Q1a is unaffected by construction (arrivals counted once per visit, at the first approach). Q1b moves from 0.070% to 0.069% sustained and from 1.054% to 1.048% gust (all piston VMC approaches with a published POH value, before the inclusion filter).
* Proposed (needs Benjamin): drop inferred approaches from all Q2 measurement as a post-hoc correction, the same way the wind quality filter was handled, with the as-registered numbers in the supplement. An inferred approach was not observed, so it has no flight path to score. The detector stays frozen at v3.0.1 for all counts. The rule 11 parallel check goes in the limitations and in a later v3.0.2.

### 2026-10-02, detector v3.1 candidate: parallel-runway groups and pattern side (logged before implementation and validation)

Benjamin asked for a pattern recognizer: parallel runways do not share traffic patterns, so the pattern side should identify the runway. Development analysis first (us_parallel_patterns.py, us_parallel/patterns.txt, every 4th day of the US year, geometry only, no Q2 outcomes):
* 118 included airports have same-direction parallels within 0.8 nm (85 within 0.4 nm). NASR pattern flags are incomplete: of 304 included end pairs, 99 are published with the patterns on the outside, 68 with both on the same side, and 136 lack a flag. So the side has to be learned from the tracks.
* Premise holds: where the low track (300 ft or less over the runway) decides the landing runway and a downwind is seen, the downwind is on that runway's outer side for 93.3% of 501,598 circuits (92.6% below 0.15 nm separation, 95.7% at 0.4 to 0.8 nm). It is unreliable at a few airports (DWH 46%, BFI 62%, BIL 73%).
* Where low data exist, v3.0.1 already picks the same runway as the low track for all but 369 of 2,020,258 approaches.
* With the low track hidden, the nearest centerline from the approach's points above 300 ft is right 99.8% of the time, against 93.4% for the downwind side. Position on final is the stronger cue whenever there is any final. The downwind side is the fallback when a circuit has no final-approach points at all.
* The HWO and DTO duplicates are a bookkeeping problem: rules 5, 6, 7 and 11 look for an existing pass on the same runway end only, and rule 11 picks the first qualifying end in list order.

Rule 12 (v3.1), applied after rules 1 to 11:
1. Parallel group: runway ends within 10 degrees of the same course whose centerlines are at most 0.8 nm apart.
2. Merge: two passes of the same kind on ends of one parallel group within 120 s of each other (approaches by end time, climb-outs by start time) count once. An observed pass is kept over an inferred one. Two observed passes are left as v3.0.1 has them (rule 9 already handles those within 90 s).
3. Runway of an inferred pass in a parallel group, in this order: (a) nearest centerline from the median lateral offset of the visit's points in that group's approach window (up to 2 nm before the threshold, track within 30 degrees, 900 ft or less) in the 120 s before an inferred approach, or in its climb window (past the threshold, track within 30 degrees, 1,200 ft or less) in the 120 s after an inferred climb-out, at least 2 points. (b) Pattern side: the median side of the downwind (abeam the runway, 300 to 2,000 ft, track within 30 degrees of the reciprocal) in the 6 minutes before an approach or after a climb-out, at least 3 points, giving the outermost runway on that side. Used only for runway ends whose learned same-side rate is at least 85% over at least 100 decisive circuits (us_parallel/side_reliable.json, built from the development analysis). (c) Otherwise the v3.0.1 choice. A traverse approach and its climb-out get the same runway, using both sides' evidence (a, then b).
4. Merge again (step 2) after step 3.
Observed passes are never reassigned.

Validation, criteria fixed now:
* V1: no change at the seven New England study airports (no parallels). Event sets identical on labeling Sets 1 to 3 and on the New England extracts.
* V2: visit agreement on every labeled set (development, held-out, Set 3, US Set 4 raw and adjudicated) is at least v3.0.1's.
* V3: US tower counts (us_tower_compare.py rerun with v3.1): every airport whose parallel duplicates were under 1 per 100 tower operations moves by less than 0.02. HWO and DTO move down by about their duplicate share. The capture-vs-weather test still passes.
* Diagnostic, no criterion: the S_fp distribution of inferred approaches in the US Q2 sample under v3.1.
* If V1 to V3 pass, the US analyses are rerun with v3.1 into new folders. v3.0.1 results stay on disk. Which one is primary is Benjamin's call. v3.0.1 is kept frozen at notes/ops_detector_v3.0.1_2026-10-02.py.

### 2026-10-02, detector v3.1 validation results

Implemented as logged (ops_detector.py VERSION 3.1, rule 12, detect(a, ends, side_ok=None)). v3.0.1 frozen at notes/ops_detector_v3.0.1_2026-10-02.py. Pattern-side table us_parallel/side_reliable.json: 159 runway ends at 64 airports pass the 85% / 100-circuit bar (HWO all eight ends, DTO 18R and 36L, APA 17R and 35L, FFZ all four).
* V1 PASS. The New England labeled sets and study airports have no parallel groups, so rule 12 returns v3.0.1's passes unchanged (event sets identical on Sets 1 to 3).
* V2 PASS (score_labels_v31.py). Sets 1 to 3 unchanged (100, 95, 92 of 100 under both). Set 4 changes one visit (U081, BKL: v3.0.1 6 approaches and 6 climb-outs, v3.1 6 and 5, label 5 and 4). Set 4 stays 84/100 raw and 89/100 adjudicated.
* V3 FAILS as written (us_tower_compare.py --out us_tower_compare_v31, us_tower_compare_v31_check.py). FCM moved -0.022 against the 0.02 bar. HWO moved -0.176 and DTO -0.150, more than their traverse-duplicate shares (0.139, 0.109) that the criterion predicted. All other airports pass (IXD, FRG, TTN, LNS, HIO, FXE, GKY, SDL unchanged to 0.002). Pooled 0.970 to 0.941. Capture against weather still passes (mean wind -1.8% per 10 kt, -4.0 to +0.4, crosswind -2.9%, -6.4 to +0.8).
* Why the criterion missed (us_q2 extracts, 30 random days at HWO, DTO, FCM, FTW, every removed pass classified, and examples checked by eye): every pass rule 12 removed was inferred and within 120 s of an observed pass of the same kind in the same parallel group. Two duplicate kinds beyond the traverse ones were not counted when the expectation was set:
  * A rule 5 cascade. The traverse climb-out on the parallel resets rule 5's "since the previous climb-out" clock, so rule 5 adds a second approach on the real runway. One touch-and-go became five passes (HWO 2026-02-10, SLG2: approach 10R, traverse approach and climb-out 10L, gap approach 10R, climb-out 10R). HWO 987 and DTO 552 such passes in the sample.
  * Rule 6 on the parallel. The data end a few seconds after an observed landing, on the runway, 0.08 nm from the other parallel, and rule 6 adds an approach to that parallel (FCM 2025-12-23, C172: approach 10R to the threshold, then an "end" approach on 10L 14 s later). FCM 196, FTW 164, DTO 108 in the sample.
* Reading: rule 12 removes only duplicates. The pre-set bar assumed traverse duplicates were the only kind. Adoption is Benjamin's call, with this failure reported as is.
* After v3.1: HWO 0.967, DTO 0.869 (now below the tower, archive coverage as at SUS), APA 1.076, FTW 0.719 (helicopters), pooled 0.941.
* US Q2 re-measured with v3.1 where rule 12 changes a visit (q2_measures.py --us --rule12 --out q2_us_v31, stored passes kept elsewhere so rounding in the stored points cannot move anything). Results to follow.

### 2026-10-02, US Q2 with detector v3.1 (q2_us_v31/, q2_us_results_v31/)

q2_measures.py --us --rule12: 303,675 visits changed, approaches 19,722,072 to 19,324,678 (-2.0%), measurable 15,688,219 to 15,522,398. Primary piston sample 5,308,201 to 5,247,849. Observed approaches are unchanged (5,206,025 against 5,205,992). Traverse-inferred measurable approaches fall from 78,482 to 18,217. Gap and end inferred approaches barely move (11,746 to 11,958, 11,948 to 11,682). The remaining inferred approaches still score as artifacts (S_fp median 6.8 to 7.4, 83 to 93% above 2), now mostly at airports without parallels (PIE, DVT, BIL, MSN, OSH).
* Piston wind effects (as registered, inferred approaches included): S_fp above 1 at 15 kt +6.9 points (v3.0.1 +6.8), above 2 +2.2 (+2.1), log S_fp +2.6% per 5 kt (+2.5%). S_spd identical. S_turn above 1 at 15 kt +6.4 (+6.1). Within-aircraft unchanged (+7.5 against +7.4).
* Levels about one point lower: S_fp above 2 is 17.8% at 0-4 kt, 18.1% at 10-14 kt, 20.9% at 15-19 kt (v3.0.1 18.7, 19.0, 21.5).
* Jet floor is cleaner: S_fp above 2 at calm 0.8% (was 1.8%), above 3 0.2% (1.1%). Jets log S_fp +1.2% per 5 kt (+1.4%). The piston minus jet gap widens slightly, to about 1.4% per 5 kt.
* Calibration: at the revealed limit (11.6 plus or minus 1 kt) S_fp above 2 is 18.2% against 17.8% at calm. Above max demonstrated 21.9% (22.5%).
* Direction unchanged: overshoot above 200 ft +2.69 points per 5 kt from the base side, -1.05 from the far side.
* Q1b unchanged: sustained 0.07%, gust 1.06% (1.05%). Q1a unchanged by construction (arrivals once per visit).
* Which cue decided the runway for inferred passes that survived the merge (8 parallel airports, 80 days): final or climb-out points decided it in 203 checks and were missing in 1,710. The downwind side then decided 715 times and could not decide 861 times (no downwind seen, or the runway end's side not reliable).

Recommendation to Benjamin (his call, asked 2026-10-02):
1. Adopt v3.1 as the US detector. V1 and V2 pass. V3 missed its pre-set bar, and every extra removal was a verified duplicate of a kind the expectation did not cover. Report the miss in the paper, with v3.0.1 numbers in the supplement.
2. Still drop inferred approaches from Q2 scoring (they were not observed and still score as artifacts). Under v3.1 with that exclusion, the piston Q2 numbers equal the v3.0.1 exclusion numbers, since observed approaches are unchanged.

### 2026-10-02, DECIDED (Benjamin): detector v3.1 and no inferred approaches in Q2

Benjamin: "Yes to both, use v3.1 and drop inferred approaches."
* Detector v3.1 is the detector for all US analyses. New England is unchanged by construction (no parallel groups). v3.0.1 results stay on disk (us_tower_compare/, q2_us/, q2_us_results/) for the supplement. The V3 tower-count criterion miss is reported as it happened.
* Inferred approaches (rules 5, 6, 7, 11) are not measurable for Q2, in the US (us_q2.py sets their status to "inferred", so every Q2 table, the calibration and the exploratory X1 to X4 exclude them) and in New England (q2_wind.py). They stay in Q1b, which counts operations rather than scoring flight paths.
* Q1a is unaffected: rule 12 only drops an inferred pass when an observed pass of the same kind is kept, so every visit keeps its arrival, and the dropped passes come after the visit's first approach.
* Code defaults now point at the primary run: us_q2.py reads q2_us_v31/approaches.csv and writes q2_us_results_v31/ (US_Q2_KEEP_INFERRED=1 reproduces the as-registered sample), us_tower_compare.py writes us_tower_compare_v31/. New England results with inferred approaches kept are copied to q2_wind_with_inferred/.
* Final reruns started 2026-10-02 23:13 UTC: us_q2.py, us_exposure.py, q2_wind.py.

### 2026-10-02, speed score check before freezing (us_speed_check.py, q2_us_results_v31/speed_check.txt)

Piston, VMC, measurable, observed approaches, v3.1, 4,406,751 with a gate airspeed and a POH target.
* The rise of S_spd with wind is not "too slow" flags. Slow at 300 ft (more than 5 kt under target) is about 2% and falls with headwind (5.8% at 5 to 10 kt tailwind, 0.7% at 15 kt and more headwind). So the 1/7 profile understating wind at height does not drive it.
* It is "too fast" (more than 10 kt over target): 41% at 0-4 kt crosswind, 53% at 15-19 kt. By headwind, 32% to 67%. The median approach is 8.4 kt over the POH target plus half the gust spread.
* Found: estimated airspeed (groundspeed plus headwind) is a true airspeed, and it is compared with POH speeds that are indicated. There is no density correction. By field elevation, the share more than 10 kt fast goes 38% (below 1,000 ft), 41%, 54%, 58%, 74% (4,500 to 6,000 ft), 80% (above 6,000 ft). With a standard-atmosphere correction at field elevation plus 300 ft, the median over target is flat (+6.1 to +8.7 kt) and fast is 29% to 43% everywhere. Overall fast 41.2% to 34.5%.
* Also open: the pre-registered wind-profile sensitivity for the speed measures (exponents 0 and 1/4, plus the observed 0.20) has not been run on the US data.
* Proposed to Benjamin (not applied): convert estimated true airspeed to calibrated airspeed with the density at the airplane's height (METAR temperature and altimeter, field elevation, standard lapse rate) before comparing with POH speeds, as a post-hoc measurement correction, and run the profile sensitivity in the same re-measurement.

### 2026-10-02, DECIDED (Benjamin): airspeed correction, curves for the actual limit, public repository later

Benjamin: "Yes to both, apply the airspeed correction and use curves." Also: he will re-label 30 visits for the intra-rater check later. The public repository (code and aggregate tables only, ODbL credit to ADSB.lol) comes once everything is done. Author block: Benjamin DosSantos Jr., Independent Researcher, New Bedford, Massachusetts.

Airspeed correction (post-hoc measurement correction, applied to both samples):
* Estimated airspeed (groundspeed plus the ASOS headwind on the track, scaled to height) is a true airspeed. Every comparison with POH speeds (C5a at the gate and below it) and the 10 kt stability tolerance (C5b and its variants) now uses calibrated airspeed, CAS = TAS x sqrt(rho / rho0). Density at the airplane's height comes from the station pressure (altimeter setting and field elevation), the METAR temperature (remarks T group, else body group), and the standard lapse rate. Standard values where a METAR lacks them. The METAR used is the one nearest the end of the approach pass, within 90 min. Bank-angle estimates keep true airspeed, which is what turn physics needs.
* New columns: gate_est_tas (the old gate_est_as), cas_factor, air_temp_c. gate_est_as is now calibrated. --airspeed tas reproduces the uncorrected runs.
* Check, APA July 2026: median gate airspeed over the POH target +16.2 kt as true airspeed, +6.3 kt as calibrated (median factor 0.881 at 26 C).
* Same re-measurement runs the registered wind-profile sensitivity for the speed measures: exponent 0 and 1/4 (registered) and the observed 0.20, beside the primary 1/7.

Actual limit: no single number. The paper reports the curves (share above 1, 2 and 3 by crosswind, the model changes against calm) and the calibration comparisons (calm, the revealed limit, 0.75 to 1.0 of max demonstrated, above max demonstrated). The decision logged here closes the open item from the 2026-10-02 Q2 plan.

Outputs: US primary q2_us_v31_cas/ (results q2_us_results_v31_cas/), sensitivities q2_us_v31_cas_exp0/, _exp020/, _exp025/. New England q2/ (the uncorrected New England file is kept as q2_tas/).

### 2026-10-03, paper wording on label adjudication (Benjamin)

Benjamin: pointing out the clerical label errors makes the paper look bad when they do not matter. The paper now says only that disagreements between the detector and the labels were adjudicated against the raw track before scoring, and reports the adjudicated figures (Set 2: 90%, Set 3: 92%, Set 4: 89%). The raw figures (Set 2: 87%, Set 4: 84%) and the five Set 4 corrections stay in this log and in labeling/us/adjudication.csv. The clerical row was removed from the paper's table of changes. The Set 4 result is still reported as below the 90% criterion.

### 2026-10-03, intra-rater check (logged before the draw)

Benjamin re-labels 30 visits blind, to measure how consistent a single rater is. That consistency is the noise floor for the detector's 90% visit criterion.
* Pool: the 400 visits of Sets 1 to 4 and Benjamin's first, unadjudicated labels (Set 1 labeling/export_BD_raw_2026-10-01, Set 2 labeling/export_heldout_BD, Set 3 labeling/export_set3_BD_raw, Set 4 labeling/export_us_BD_raw).
* Draw: 7 visits from Set 1, 7 from Set 2, 8 from Set 3, 8 from Set 4, at random, seed 20261003 (make_relabel_set.py).
* Blinding: new IDs R01 to R30 in a new random order, so the tool shows no earlier labels. Same tool, same tracks, same instructions. The key (labeling/relabel/key.csv) is not published.
* Outcomes, no pass or fail bar: visit-level agreement between the two labelings (identical counts of approaches and climb-outs per runway end) with a Wilson 95% interval, agreement on whether there was an arrival, on the number of approaches, and on the runway of each approach. Reported with and without visits marked too little data in either labeling. For context, detector v3.1 agreement with each labeling on the same 30.

### 2026-10-03, intra-rater check result (score_relabel.py, labeling/relabel/score.txt)

Benjamin re-labeled the 30 visits blind (R01 to R30). Scored once against his first, unadjudicated labels, as logged before the draw:
* Same events both times: 28 of 30 visits (93%, Wilson 95% 79 to 98%). 27 of 29 (93%) without the one visit marked too little data.
* Every approach agreed: whether there was an arrival 30 of 30, the number of approaches 30 of 30, approaches by runway 30 of 30.
* The two disagreements are the runway named for a departure climb-out, both in Set 4: R12 (U063) 04L then 22R, and R13 (U080) 24R then 06L. Both second labels match the Set 4 adjudication made earlier and the detector, so the re-label independently supports those two corrections.
* Detector v3.1 matches the first labels on 25 of 30 and the second labels on 27 of 30. The detector agrees with the rater nearly as often as the rater agrees with himself.

### 2026-10-03, US results with calibrated airspeed (primary: v3.1, no inferred approaches, CAS; q2_us_results_v31_cas/)

Compared with the same run on true airspeed (q2_us_results_v31/, also v3.1 without inferred approaches). Flight-path and turn results are identical, as expected.
* Speed level at 300 ft (us_speed_check.py): median over the POH target plus half the gust spread +6.3 kt at 0-4 kt crosswind (was +8.4). More than 10 kt fast 29.7% (was 41.0%). More than 5 kt slow 3.5% (was 2.2%).
* By crosswind, fast rises from 29.7% (0-4 kt) to 41.2% (15-19 kt), unsteady from 4.6% to 12.4%. By headwind, fast rises from 18.9% (5 to 10 kt tailwind) to 56.4% (15 kt or more headwind), and the median over target from +2.8 to +11.3 kt. Slow is 11.0% with a tailwind and 1.2% in strong headwind.
* S_spd above 1 by crosswind: 39.9%, 42.7%, 48.8%, 55.0% at 0-4, 5-9, 10-14, 15-19 kt (was 47.7, 50.1, 54.9, 60.9). Above 2: 7.2, 8.1, 10.9, 16.0% (was 10.2, 11.2, 14.7, 22.3).
* Model change against calm, S_spd above 1: +5.1 points at 10 kt, +13.4 at 15 kt (was +5.2, +13.0). Above 2: +1.0 and +4.4 (was +1.8, +6.5). log S_spd +3.9% per 5 kt (was +4.1%). Per 5 kt headwind +5.8 points (was +7.8).
* Calibration, S_spd above 1: calm 39.4%, revealed limit (11.6 plus or minus 1 kt) 48.0%, 0.75 to 1.0 of max demonstrated 57.4%, above max demonstrated 66.5% (was 47.1, 53.8, 64.5, 74.2).
* Exploratory X3 and X4: speed degradation is still steeper at windier airports (log S_spd +3.0, +3.8, +4.8% per 5 kt by climate tertile) and for aircraft based there (+2.6, +3.8, +4.3%), so that pattern is not the high-elevation offset.
* Final primary flight-path numbers for the paper (unchanged by the correction): S_fp above 1 is 49.5% at 0-4 kt, 52.3% at 10-14 kt, 55.7% at 15-19 kt. Above 2: 17.3%, 17.3%, 20.1%. Model change above 1: +3.7 points at 10 kt, +6.9 at 15 kt. log S_fp +2.4% per 5 kt, jets +1.2%. S_turn above 1 base 38.2%, +6.2 points at 15 kt. Overshoot above 200 ft +2.69 points per 5 kt from the base side.
* New England (q2_wind.py, inferred approaches dropped, CAS): registered S above 2 is 18.1% at 0-4 kt and 21.5% at 10-14 kt (was 19.0 and 22.3). Same pattern.

### 2026-10-03, registered wind-profile sensitivity for the speed score (q2_us_results_v31_cas_exp0, _exp020, _exp025)

Same primary sample (v3.1, no inferred approaches, calibrated airspeed). Only the exponent that scales the surface wind to the airplane's height changes. Flight-path and turn results are identical across all four, as expected.

| Exponent | S_spd above 1, 0-4 / 10-14 / 15-19 kt | Change at 15 kt (above 1) | Change at 15 kt (above 2) | log S_spd per 5 kt |
|---|---|---|---|---|
| 0 (surface wind, registered) | 36.4 / 43.5 / 48.4% | +7.4 | +1.7 | +2.0% |
| 1/7 (primary) | 39.9 / 48.8 / 55.0% | +13.4 | +4.4 | +3.9% |
| 0.20 (observed in pattern turns) | 43.1 / 54.0 / 60.2% | +16.6 | +5.9 | +4.9% |
| 1/4 (registered) | 46.7 / 59.3 / 64.6% | +18.0 | +8.4 | +5.9% |

* The speed score rises with crosswind under every exponent. The size depends on how much the wind grows with height: +7 to +18 points at 15 kt. Exponent 0 is a lower bound (it assumes no increase above 10 m). The observed 0.20 puts the effect a little above the primary.
* Calibration, S_spd above 1 at calm / at the revealed limit / above max demonstrated: exponent 0 35.9 / 42.8 / 58.2%, 1/7 39.4 / 48.0 / 66.5%, 0.20 42.5 / 52.9 / 72.8%, 1/4 46.1 / 58.1 / 77.5%.
* For the paper: report the primary with this range. The direction of the speed result is robust. Its size carries the wind-profile uncertainty.

### 2026-10-03, New England development sample on the locked scores (q2_ne_locked/, us_q2.py with US_Q2_SAMPLE=ne)

Same code and scores as the US primary (v3.0.1 equals v3.1 here, no inferred approaches, calibrated airspeed), with the New England Q1a windows. 161,762 measurable piston approaches at seven airports.
* S_fp above 1: 43.0% at 0-4 kt, 45.4% at 5-9 kt, 48.4% at 10-14 kt. Above 2: 12.2%, 13.3%, 13.5%. Model change above 1: +4.7 points at 10 kt, +12.1 at 15 kt. log S_fp +3.7% per 5 kt, jets +2.6%. Within-aircraft above 1: +5.7 and +13.0.
* S_spd above 1: 42.7%, 43.2%, 48.0%. Model change +4.1 at 10 kt, +18.5 at 15 kt. log S_spd +4.3% per 5 kt.
* S_turn above 1 base 31.8%, +6.0 at 10 kt, +12.5 at 15 kt.
* Calibration: at the revealed limit (10.8 plus or minus 1 kt) S_fp above 2 is 13.2% against 12.2% at calm. Above max demonstrated (78 approaches) 17.9%.
* Q1b: sustained 0.04%, gust 1.24%, fleet and private alike.
* Direction: overshoot above 200 ft +4.29 points per 5 kt from the base side, -1.41 from the far side.
* Levels are lower than in the US (S_fp above 1 at calm 43.0% against 49.5%), and the wind effects are the same or somewhat larger. Both samples tell the same story.

### 2026-10-03, overnight: freeze, figures, and a full first draft (Benjamin: "go ahead and set up for an overnight run")

* Freeze (notes/freeze_2026-10-03.md): checksums of code, reference tables and every primary output in freeze/manifest_2026-10-03.sha256, and of the ADS-B caches and extracts (174,749 files) in freeze/inputs_2026-10-03.sha256.
* New England on the locked scores: q2_ne_locked/ (entry above).
* Figures from frozen outputs: paper/figures/make_fig_data.py writes paper/figures/data/ (activity with day-cluster intervals, shares with aircraft-cluster intervals, direction, POH crosswind percentiles), and make_fig_results.py draws activity.pdf (Fig. 2), calibration.pdf (Fig. 3) and direction.pdf (Fig. 4).
* Paper: Results (with Tables 2 and 3), Introduction, Background, Discussion, Conclusions and a first Abstract drafted in paper/main.tex. Every number was checked against the frozen summaries. Citations use only the claims verified in notes/literature_review.md. Discussion uses Benjamin's notes (round-number limits, flight-school solo limits, half the gust factor, home-field familiarity) as interpretations, marked exploratory where they rest on X1 to X4.

### 2026-10-03, figures redesigned for readability (Benjamin: "easier to interpret and more professionally laid out")

Same data and numbers, new presentation (paper/figures/figstyle.py shared by all figures: STIX text to match the paper, left and bottom axes only, light horizontal grid, Okabe-Ito colors, the same color for the same quantity everywhere, lines labeled where they end instead of legends).
* Fig. 1 (scoring): tolerance key across the top, runway drawn at the threshold, worst points annotated with the arithmetic (140 / 100 = 1.4).
* Fig. 2 (activity): traffic as a percent of normal, reference lines at normal and half of normal, revealed limits marked by drop lines with their values. The New England line was dropped (it is in Table 2).
* Fig. 3 (calibration): panel (b) now shows the change from calm wind (crosswind under 4 kt) in the share above 1 for flight path, speed, turn to final and jets, so every line starts at zero. Levels stay in Table 3. Bins with fewer than 900 approaches are left out.
* Fig. 4 (direction): a plan-view sketch of the turn to final with both wind cases, then one panel per measure with the far and base-leg sides labeled on the axis.
Captions updated to match. Manifest regenerated.
* Fig. 4 redrawn again (Benjamin: "the turn to final charts could be clearer"): one row per wind side, each with a sketch of what that wind does (gray dashed calm turn, colored path) and a chart of the change from calm wind in both measures against crosswind from that side (0 to 15 kt). Calm levels in the caption (overshoot 3.0%, late alignment 36.3%).
* Alignment measure relabeled "Not lined up by 300 ft" in Fig. 4, its caption, and the Results text (Benjamin). Same definition: first lined up and stayed lined up only below 300 ft, or never.
* Wind-side terms changed to the pilots' own (Benjamin asked "wind with the base leg or wind against"): a crosswind from the base-leg side is a tailwind on base, and from the far side a headwind on base. Used in Fig. 4, its caption, the Results subsection (now "Tailwind and headwind on base", with one sentence defining the terms), the Discussion, Conclusions and Abstract. Fig. 4 charts now show the actual shares with dotted calm-wind levels instead of change from calm. Fig. 3 keeps change from calm, relabeled "Extra approaches per 100 (0 = same as calm wind)".
* Fig. 3: panel (a) retitled "Arrivals relative to normal demand" (Benjamin: "How much pilots fly" not academic), panel (b) back to the share of approaches above 1 in percent (his preference). Caption updated.
* Fig. 3 panel (a) now has its own crosswind tick labels and axis label (hourly mean on the runway most nearly into the wind), and panel (b) names its crosswind (runway in use, at each approach) (Benjamin).
* Fig. 3 panel (b) back to the increase over calm wind in percentage points (Benjamin: percentages compressed the data). Points rather than relative percent, since relative change would make the jets look worst (+83%) only because they start at 6.6%. Calm levels in the caption.
* Fig. 3 now has both views (Benjamin: "do we have both?"): (a) arrivals, (b) the share of approaches above 1 in percent, which shows about half beyond tolerance even in calm wind, and (c) the same shares as the increase over calm wind in percentage points. Full-page float. Caption updated.
* Fig. 3 panel (c) retitled "Increase over calm wind", caption "(c) The rise in each share above its calm-wind level" (Benjamin).

### 2026-10-04, Results paragraph on gusts and headwind (Benjamin asked whether performance drops off with wind or gust factor)

Added "Gusts and headwind" to the Results, from the frozen primary run (q2_us_results_v31_cas/summary.txt, covariate effects in the registered models and the gust-spread and headwind bands). Per 5 kt gust spread: S_fp above 1 +2.4 points (jets +1.8), above 2 +0.3, S_spd above 1 -2.4 (the target adds half the gust spread), S_turn above 1 -0.4. Raw bands: S_fp above 2 is 17.5% at gust spread under 0.5 kt and 14.8% at 10 kt or more. Per 5 kt headwind: S_fp above 1 -2.0, S_turn above 1 -4.0, S_spd above 1 +5.8. S_fp above 1 is 52.5% with a tailwind and 48 to 50% with a headwind. Reading: performance degrades with crosswind, not with gustiness. Total wind speed as a single variable was not modeled (offered as an exploratory run).

### 2026-10-04, X5 exploratory: approach performance against total wind speed (logged before running; Benjamin asked for it)

Not registered, reported as exploratory. Same primary sample and scores (piston, VMC, measurable, v3.1, no inferred approaches, calibrated airspeed), script us_wind_speed.py, output q2_us_results_v31_cas/wind_speed_summary.txt.
* Shares above 1, 2, 3 by total two-minute wind speed at the gate (0-4, 5-9, 10-14, 15-19, 20+ kt), for S_fp, S_spd, S_turn, with the usual bootstrap intervals.
* The registered model form with total wind speed in place of crosswind (piecewise linear, knots 5, 10, 15 kt) and no headwind term, gust spread and the same controls kept, airport and runway absorbed, aircraft-clustered errors. Change against calm at 5, 10, 15, 20 kt, and log score per 5 kt. Jets the same way, as the floor.
* Direction check: at the same total wind (5-9, 10-14, 15-19 kt), shares above 1 by the crosswind fraction of the wind (under 1/3, 1/3 to 2/3, over 2/3).

### 2026-10-04, X5 results (exploratory, q2_us_results_v31_cas/wind_speed_summary.txt)

* Total wind speed alone does not degrade the flight path. S_fp above 2 is 18.9% at 0-4 kt total wind and 15.2% at 15-19 kt. Model with total wind in place of crosswind: above 2 -3.4 points at 10 kt and -4.3 at 15 kt. log S_fp -2.2% per 5 kt total wind (jets -0.5%).
* Speed degrades strongly with total wind: S_spd above 1 35.5%, 39.9%, 48.5%, 58.9%, 67.1% by band. Model +10.8 points at 10 kt, +22.9 at 15 kt. log S_spd +11.8% per 5 kt.
* Turn to final improves with total wind (S_turn above 1 -6.7 points at 10 kt, -8.8 at 15 kt).
* At the same total wind, approaches with the wind mostly across the runway have slightly more flight-path scores above 1 (10-14 kt: 50.5% against 48.4% mostly along the runway, 15-19 kt: 52.8% against 49.0%) and fewer speed scores above 1 (44.9% against 49.3%, 54.1% against 59.5%).
* Reading: pilots land into the wind, so total wind is mostly headwind, which helps the flight path and the turn and adds speed. Flight-path trouble follows the crosswind part, speed trouble the along-runway part.

### 2026-10-04, X6 exploratory: crosswind strength against wind angle (logged before running; Benjamin asked "if cross wind speed vs cross wind angle is more conducive of an out of tolerance approach")

Same primary sample and scores. Wind angle relative to the runway in use = atan2(crosswind, headwind), 0 degrees straight down the runway, 90 a direct crosswind, above 90 a quartering tailwind. Script us_xw_angle.py, output q2_us_results_v31_cas/xw_angle_summary.txt.
* Grid: crosswind 5-9, 10-14, 15-19 kt by angle 0-30, 30-60, 60-90, above 90 degrees: n and shares above 1 and 2 for S_fp, above 1 for S_spd and S_turn.
* Which wind measure explains out-of-tolerance approaches best: linear probability models of S_fp above 1, S_fp above 2 and S_spd above 1, airport and runway absorbed, the usual controls, with one wind description at a time (crosswind piecewise linear, angle piecewise linear with knots 30, 60, 90 degrees, total wind piecewise linear, crosswind plus headwind). Compared by the variance each adds over the controls alone (within R squared). Point estimates only.

### 2026-10-04, X6 results and paper additions (exploratory)

* Grid at 10-14 kt crosswind: S_fp above 2 is 16.4% at 30-60 degrees, 17.2% at 60-90, 20.3% above 90 (quartering tailwind). S_turn above 1: 38.8, 41.6, 45.9%. S_spd above 1: 54.0, 45.2, 43.7%. Same order at 5-9 and 15-19 kt.
* Within R squared added over the controls (x 1000): S_fp above 2: crosswind alone 0.03, angle 1.42, total wind 0.81, crosswind plus headwind 2.21. S_spd above 1: crosswind 0.70, angle 2.51, total wind 9.76, crosswind plus headwind 10.56. Controls alone 62.6 (S_fp above 1) and 43.7 (above 2).
* Reading: for the flight path and the turn, the angle matters more than crosswind strength alone (a headwind part helps, a tailwind part hurts). The crosswind and headwind components together describe it best, which is what the registered models use. Speed follows the total wind. Wind explains a small share of which approaches go out of tolerance.
* Benjamin asked to add X5 and X6 to the paper with a heatmap: new Fig. 5 (paper/figures/make_fig_angle.py, from xw_angle_summary.txt), and a paragraph in Results, Exploratory analyses ("Six further comparisons"). Manifest regenerated.
* Fig. 5 panels now share one blue scale (Benjamin: different colors implied a meaning they do not have). Shading scaled within each panel, stated in the caption.

### 2026-10-04, dev container stopped (Benjamin: "we can shut down the development server for now")

Nothing running. Outputs frozen (freeze/manifest_2026-10-03.sha256 covers code, reference tables, outputs and figures). Data and code live on the host volume at /home/dev and persist. The scratchpad copy of PyMuPDF (used only to render pages for checking) does not persist and is not needed. Next on restart: Benjamin's notes on the draft.

### 2026-10-05, review checks on the draft (logged before running; post-hoc diagnostics and sensitivities)

Benjamin's current draft is in paper_benjamin_2026-10-05/paper/main.tex (his edits, uploaded 2026-10-05). A review of it raised questions that need the server. None of these changes a locked rule or a primary result. Each is reported as a post-hoc check. Scripts and outputs go in review_2026-10-05/.
* Speed: share of approaches above 1 on the speed consistency check alone, and the median speed excess at 300 ft (calibrated airspeed minus the POH target plus half the gust spread), by crosswind band.
* Development airports in the confirmatory sample: the US headline numbers (model-free limit, Q1b share, S_fp and S_spd changes at 15 kt) with the seven New England study airports left out.
* Count ladder for the approach populations: detected approaches, piston, VMC, wind at the lowest point, POH value (published or assumed), measurable at 300 ft, and the counts above the demonstrated value under each definition.
* Capture correction for the revealed limit: arrivals divided by modeled capture, exp(b x hourly mean wind), with b from the development test (-3.9% per 10 kt), its lower bound (-6.2%), and the US v3.1 test (-1.8%), baselines recomputed from corrected arrivals. Same with the crosswind slopes.
* Model-free against spline gap (11.6 against 13.3 kt): the model-free limit within gust-spread and headwind strata, and the spline curve evaluated at the mean headwind and gust spread seen in each crosswind bin.
* Clustering: the Q2 linear probability and log-score models with standard errors clustered by aircraft (as registered), by airport-day, two-way by aircraft and airport-day, and by airport.
* Calm-wind speed share: denominators with and without approaches that lack a speed score.
* Headwind effect on S_spd under the no-growth wind profile (exponent 0).
* 95% intervals (wider of aircraft and day cluster bootstrap) for every cell of the performance-at-the-limit table.
* Jets: share of straight-in jet approaches with autopilot or approach mode reported at the gate.
* Outage days and wind: mean wind on excluded outage days against included days, US.
* Wind filter and gusts: share of one-minute records dropped by the 15 kt rules at stations that kept every month, and whether the gust field drives drops.
* Turn to final by wind side: S_turn and S_fp shares by tailwind and headwind on base.
* Spearman between Benjamin's blind ratings and the final locked scores (S_fp, S_spd, combined), with bootstrap intervals.
* Jet comparison group by airport class, and the 500 ft secondary gate results.
* Housekeeping (2026-10-05): paper/figures/make_fig_results.py was run once by mistake, which rewrote activity, calibration and direction (.pdf and .png) from the same frozen data. The three PDFs were restored from Benjamin's identical upload and match freeze/manifest_2026-10-03.sha256 again. The PNGs are not in the manifest and were regenerated from unchanged code and data (same sizes). Proposed figure changes (aligned labels, calm baseline below 5 kt) are drawn only in review_2026-10-05/figures_proposed/.
* Added to the 2026-10-05 review checks before running: the revealed limit with every piston approach counted instead of one arrival per visit (Benjamin's "is this a good thing?"), the New England tolerance sensitivities (centerline 100 and 300 ft, glide path 75 and 150 ft) on the US sample, and the prespecified logistic form for the shares (airport fixed effects, all controls) against the linear probability models the US script uses.
* Found while running them (2026-10-05): the US script's linear probability models replaced the logistic models of the New England plan before any US result, without an entry here. Logged now as an unlisted change, to be added to the paper's table of changes.
* Results of the 2026-10-05 review checks are in review_2026-10-05/ (q1a_checks, q1a_outage_check, wind_filter_check, q2_checks_part1 and part2, q2_checks2, spearman_check, set4_counts, airport_counts, approach_count_check, tol_check, logit_check) and are summarized in notes/review_answers_2026-10-05.md. No primary result changed. The logistic comparison ran on a random 1.5 million approaches (seed 20261005) with airport fixed effects, since the full-size fit was too slow on this machine's single-threaded BLAS.

### 2026-10-05, paper edits applied (Benjamin: "Use prespecified, published only, and apply the edits")

* paper/main.tex is now Benjamin's uploaded version (paper_benjamin_2026-10-05/, kept unchanged) with the edits proposed in notes/review_answers_2026-10-05.md applied by review_2026-10-05/apply_edits.py (75 replacements, each matched exactly once), plus three "data are/show" fixes. The previous server draft is saved as review_2026-10-05/server_main_before_2026-10-05.tex.
* Wording: "pre-registration" and "registered" became "prespecification" and "prespecified" throughout. Sec. IV.I is "Changes to prespecified rules", with a new row for the linear probability models.
* Table 4 (performance at four points) uses published maximum demonstrated values only (2,468 and 26,585 approaches), 95% intervals, and speed shares among approaches with a speed score.
* New Table "Approaches in each analysis" and a paragraph in Sec. V.B explain the 4.93 million (comparison with the demonstrated crosswind) against 5.19 million (performance) approaches: 3,982,667 in both (review_2026-10-05/overlap.py).
* references.bib: Boyd and Knecht titles completed, new entries faa2023acs, faaregistry, faanasr, faaopsnet (old file saved in review_2026-10-05/).
* Figures: paper/figures/make_fig_results.py now takes the calm baseline from the 0-4 kt band (crosswind below 5 kt) and labels alignment "aligned". calibration.pdf and direction.pdf redrawn from the same frozen data. These two files no longer match freeze/manifest_2026-10-03.sha256 by design.
* Data Availability statement added with placeholders for the repository URL and DOI (needs Benjamin's GitHub account). AI disclosure added to the Acknowledgments as proposed.
* Compiled with tectonic: 20 pages, no undefined references.
* Data Availability filled in (Benjamin's research GitHub account, created 2026-10-05): https://github.com/benjamindossantosresearch/pilot-wind-limits (repository name chosen by Claude, not yet created). No DOI yet. A repository-only SSH deploy key was generated on the server (~/.ssh/github_pilot_wind_limits, host alias github-pwl) for Benjamin to add with write access once he creates the empty repository.
* Repository pushed 2026-10-05 to github.com/benjamindossantosresearch/pilot-wind-limits (private), commit 7a7772b, from the staging folder /home/dev/pilot-wind-limits: code, notes/decisions.md, q2_measures.md, frozen detectors, POH table and sources, candidate airports, OPSNET daily counts, and aggregate result folders. Left out: ADS-B caches and extracts, per-approach files, labeling sets and review sets (tracks), and the tower spot-check example lists (they named individual aircraft). Licenses as recommended to Benjamin (MIT code, ODbL aggregates), pending his confirmation.
* 2026-10-05: Benjamin approved the repository and made it public, and confirmed open licenses (code MIT, aggregates ODbL 1.0 as ADSB.lol requires). Added .zenodo.json and CITATION.cff (commit ba8d37a) so the Zenodo archive carries his name, ORCID, and license. Next: he links the repository in Zenodo and publishes release v1.0.0, then the DOI goes into the paper's Data Availability, the README, and CITATION.cff.

### 2026-10-05, checks of an outside audit of the draft (logged before running; post-hoc diagnostics)

Benjamin had another Claude session audit the compiled paper and the public repository. Its quantitative claims are checked here before any paper change. Scripts and outputs in review_2026-10-05/ (audit_checks.py on q1a_us/hours.csv, audit_checks_app.py on the US approaches file).
* Wind source: share of hours on METAR fallback, the model-free limit on one-minute hours and on METAR hours separately, gust spread by source (median, share zero, maximum), and the low-gust stratum (gust spread 6.4 kt or less, crosswind 12 kt or more) by source.
* Wind speed against crosswind: activity by total wind band for hours with crosswind under 3 kt and hours with the wind mostly across the runway (crosswind at least the headwind), one-minute hours only. Model-free half points against total wind for those two groups. Deviance explained by single-variable 2 kt binned Poisson fits of crosswind, headwind, total wind, and peak gust.
* Base rate for the demonstrated-crosswind share: hours with best-runway crosswind of 15 kt or more, their share of normal demand and of arrivals.
* Calm activity and the half-of-calm crossing.
* Capture correction with the all-12-airport development slope (-6.4% per 10 kt, lower bound -8.2%).
* Approach level: wind source and gust spread at the gate by source, position source of the gate point, and ownership classes (trust, commercial, unknown).
* Audit check results (2026-10-05, notes/audit_review_2026-10-05.md): the audit's numbers reproduce. Confirmed: 21.8% of revealed-limit hours and 22.2% of measurable approaches use METAR wind (fallback as prespecified, undisclosed in the paper). One-minute-only limit 11.0 kt (10.7 to 11.3), spline 13.0 kt, METAR hours 13.3 kt. The low-gust 15.6 kt figure added to the paper today is a METAR artifact (602 of 616 such hours) and must be removed with the 12.3 kt spline figure. Traffic responds to total wind and gusts (deviance: crosswind 29k, headwind 45k, total wind 59k, peak gust 77k), but crosswind cuts traffic at fixed total wind (14 to 17 kt total: 0.70 along the runway to 0.22 above 15 kt crosswind) and has the strongest per-knot rate ratio. Base rate: 15 kt+ best-runway crosswind hours are 0.17% of hours, 0.094% of normal demand, 0.021% of arrivals, activity 0.22. Calm activity 1.04, half of calm at 11.3 kt. All-12 capture slope gives 11.9 kt (12.0 at the bound). Approach results on one-minute wind only are unchanged (S_fp above 2 +1.9 at 15 kt, S_spd above 1 +13.9). Gate position sources: ADS-B 91.1%, ADS-R 7.9%, TIS-B 1.0%, MLAT 0.01%. Trust registrations 0.4%. Zenodo did not archive release v1.0.0 (no record after 33 min), most likely published before the switch was on.
* Zenodo archived release v1.0.0 after all (slow, not missed): concept DOI 10.5281/zenodo.23173344, version DOI 10.5281/zenodo.23173345, creator and MIT license correct. The concept DOI went into the paper's Data Availability, and both into the README and CITATION.cff (commit eaff2fd). A v1.0.1 release after the audit fixes will match the submitted paper.
* Audit fixes applied 2026-10-05 (Benjamin: report raw and adjudicated detector scores, yes. Soften the crosswind-limit reading, yes. AI disclosure: he reviewed every line of code and specified the work, so the disclosure must not overstate the assistant's part). review_2026-10-05/apply_audit_edits.py, 29 replacements, plus an abstract trimmed to about 220 words. New exploratory table of activity by total wind and crosswind. The METAR-artifact low-gust sentence (15.6 kt, 12.3 kt) is removed. Paper compiles at 21 pages.

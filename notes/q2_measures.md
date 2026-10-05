# Q2 measure definitions

Status: final, approved by Benjamin 2026-10-02, before any Q2 result was computed. Changes after this date go into notes/decisions.md with a reason.

## Goal

Q2 quantifies how far approach performance moves out of tolerance as wind increases, not only whether it gets worse. That it gets worse in crosswind is expected. The contribution is the size of the effect: how severe deviations become, how often, and at what wind (absolute and relative to the aircraft's maximum demonstrated crosswind). Severity is therefore continuous. The stabilized-approach tolerances define the scale, and event levels are reference marks on it, not pass or fail outcomes.

## Sources

- FAA Airplane Flying Handbook (FAA-H-8083-3C), Chapter 9, Stabilized Approach Concept: 500 ft VMC gate, and for a typical GA piston airplane in a traffic pattern an immediate go-around if the approach becomes unstabilized below 300 ft AGL. Criteria: constant 3 degree glide path, tracks the centerline with bank normally no more than 15 degrees on final, airspeed +10/-5 KIAS of the recommended landing speed (AFM or 1.3 VSO, gust factor allowed), landing configuration, descent rate generally 500 to 1,000 fpm, appropriate power, checklists complete. Common error listed: a skidding turn from base to final from overshooting or inadequate wind drift correction.
- FAA Airplane Flying Handbook, Chapter 8: pattern altitude usually 1,000 ft above field elevation, downwind about 1/2 to 1 mile from the runway, base ground track perpendicular to the extended centerline.
- FAA Private Pilot ACS (FAA-S-ACS-6C): pattern altitude within 100 ft, airspeed within 10 kt. Approach speed +10/-5 kt with gust factor applied.
- FAA AC 120-82, Flight Operational Quality Assurance: event levels are "the parameter limits that classify the degree of deviation from the established norm into two or more event severity categories".
- Flight Safety Foundation ALAR Briefing Note 7.1: 500 ft VMC gate, sink rate no more than 1,000 fpm.
- Yoo and Garcia (2026, AIAA AVIATION): wind was associated more with variability than with path deviation, hence M4.

## What ADS-B can and cannot see

Available: position about every 2 s on final at the study airports, barometric altitude in 25 ft steps (converted to height with the METAR altimeter), vertical rate in 64 fpm steps, ground track, ground speed. Usually missing for GA: indicated airspeed and bank angle. Never available: configuration, power, checklists. Airspeed is estimated and bank is inferred from turn rate. Configuration, power, and checklists are named as limitations.

## Reference frame

- Height above threshold (HAT): height relative to the threshold elevation of the runway end in use (NASR RWY_END_ELEV, or the displaced threshold elevation where one exists). Gates use indicated height (what the pilot's altimeter showed, METAR altimeter setting without temperature correction). True height (cold-temperature corrected) is a sensitivity check.
- Reference glide path: the runway end's published visual glide path angle and threshold crossing height from NASR (VISUAL_GLIDE_PATH_ANGLE, THR_CROSSING_HGT) where a PAPI or VASI exists, otherwise 3 degrees and 50 ft over the threshold.
- Cross-track offset: perpendicular distance from the extended runway centerline, signed (negative on the base side, positive on the far side).
- Wind: one-minute ASOS (two-minute average wind and five-second gust) at the minute the airplane passes the gate, split into headwind and crosswind components on the runway's true course. Gust spread = gust minus sustained wind. Crosswind is also expressed as a fraction of the type's POH maximum demonstrated crosswind.
- Estimated airspeed: ground speed plus the headwind component at the airplane's height. The surface headwind (10 m) is scaled to height with a power-law wind profile, exponent 1/7 (neutral conditions), so at 300 ft HAT the headwind is about 1.37 times the surface value. Without this, airplanes would look slow on windy days, the condition under study. Sensitivity runs use exponents 0 (surface wind only) and 1/4.
- Target approach speed: the type's POH recommended approach speed with landing flaps, or 1.3 VSO where only VSO is published, plus half the gust spread. Types without a sourced POH speed are scored on speed stability (C5b) only.
- Inferred bank: tan(bank) = estimated true airspeed x turn rate / g, from the ground-track turn rate smoothed over 10 s.

## Population and observability

- Approaches detected by ops_detector.py v3.0.1 at the study airports, inside each airport's Q1a window, piston fixed-wing GA in the FAA registry on the flight date (Cape Air and other commercial operators excluded), VMC hours only.
- An approach is measurable at a gate only if ADS-B points exist within 10 s on both sides of the gate crossing (values interpolated). Approaches not measurable at a gate are counted and tested against wind, so a coverage drop in strong wind cannot pass as better performance.
- Straight-in approaches (track within 30 degrees of the runway course from 2 nm out) are kept for M1, M3, and M4 and left out of M2 and M6.
- Go-arounds are not outcomes (decided 2026-10-01). An approach that ends in a go-around is measured like any other up to its lowest point.

## M1. Severity at the gate (primary measure)

Primary gate: 300 ft HAT. Secondary gate: 500 ft HAT.

Each criterion is turned into a severity ratio: the measured deviation divided by its stabilized-approach tolerance. A ratio of 1.0 is the edge of a stabilized approach. Below 1 is within tolerance, 2 is twice the tolerance, and so on.

| Criterion | Deviation measured | Tolerance (ratio 1.0) |
|---|---|---|
| C1 Lateral | absolute offset from the extended centerline | 200 ft |
| C2a Track | absolute ground track difference from the runway course | 10 degrees |
| C2b Bank | inferred bank over the previous 10 s | 15 degrees |
| C3 Vertical path | absolute height difference from the reference glide path | 100 ft |
| C4 Descent rate | absolute difference from the rate the reference path needs at the current ground speed | 300 fpm (separately flagged: above 1,000 fpm, or level or climbing before the lowest point) |
| C5a Airspeed | estimated airspeed minus target: a deficit is divided by 5 kt, an excess by 10 kt (slow is penalized twice as hard, as in the +10/-5 tolerance) | -5/+10 kt |
| C5b Speed stability | range of estimated airspeed over the 30 s before the gate | 10 kt |

Approach severity score S: the largest criterion ratio at the 300 ft gate, combined with the largest C1 to C4 ratio anywhere between 300 ft and the lowest observed point (AFH: an approach that becomes unstabilized below 300 ft calls for a go-around). S tells how far the worst element of the approach was out of tolerance. Every criterion ratio is also kept and reported on its own, so results show which element degrades with wind and by how much.

Reference marks on the scale (for comparison with flight data monitoring practice, AC 120-82):
- Level 1 (outside stabilized tolerance): ratio above 1.
- Level 2 (severe): ratio above 2.

How results are reported: the full distribution of S and of each criterion ratio as a function of crosswind, headwind, and gust spread (median, 90th and 99th percentiles, and the share of approaches above 1 and above 2), both in knots and as a fraction of the aircraft's maximum demonstrated crosswind. The analysis models those quantiles and tail shares with airport, runway, aircraft type, fleet or private ownership, and season as controls (model details set before the Q2 run).

Sensitivity runs: lateral tolerance 100 and 300 ft, vertical tolerance 75 and 150 ft, wind-profile exponents 0 and 1/4, true height in place of indicated height.

## M2. Base-to-final overshoot

For approaches flown from a base leg: from the start of the turn to final until the airplane is aligned (M3), the maximum cross-track excursion past the extended centerline on the far side from the base leg, in feet (continuous). Reference marks: 200 ft (overshoot) and 500 ft (severe overshoot). The maximum inferred bank during the turn is kept as well.

## M3. Alignment height

The HAT at which the airplane first has C1 and C2a ratios at or below 1 and keeps them there down to the 300 ft gate, or to the lowest observed point (continuous). Reference mark: alignment below 300 ft HAT, or never aligned, is late alignment.

## M4. Variability on final

Standard deviation of vertical rate and of cross-track offset between alignment (or 500 ft HAT, whichever is lower) and 200 ft HAT, or the lowest observed point.

## M5. Pattern measures (secondary)

For visits with an identified downwind leg (track within 20 degrees of the reciprocal of the runway course, alongside the runway):
- Downwind altitude: deviation from pattern altitude (1,000 ft above field elevation unless published otherwise) as a ratio to the ACS 100 ft tolerance.
- Downwind spacing: distance from the runway centerline (AFH 1/2 to 1 mile) and its variation within the leg.
- Final length: distance from the threshold where the base-to-final turn ends.

## M6. Crosswind direction relative to the pattern (Benjamin's hypothesis)

For approaches with a base leg, the base side comes from the track (which side of the extended centerline the base leg was flown), with NASR right-traffic flags as a cross-check. The crosswind component on final is signed relative to that side: positive means wind from the base side, a tailwind on base that carries the airplane through the centerline. Prediction: at equal crosswind magnitude, M2 overshoot distance and M3 alignment height are worse with positive (base-side) crosswind. If go/no-go (Q1) follows crosswind magnitude only while M2 and M3 follow direction, that is a specific gap between revealed and actual limits.

## Sanity check before the full run

Benjamin reviews about 20 approaches with high severity scores and 10 with low scores in the labeler, to confirm the measures match what a pilot sees in the tracks. Any change that follows is logged with its reason before the wind analysis.

## Amendments, 2026-10-02 (after a critical review, before any Q2 result)

Reason: in a study of wind, any measurement error that grows with wind would look like pilots getting worse. The review found three measures exposed to that, plus three other weaknesses. No onboard flight data (G1000 or AHRS logs) is available, so measurement validation uses internal checks and a control group instead.

1. Primary severity score narrowed. S is built from the directly measured criteria only: C1 lateral, C2a track, C3 vertical path, C4 descent rate, C5b speed stability. C5a (estimated airspeed against the POH target) and C2b (inferred bank) become secondary measures, reported with their known limits. A check of the archive found indicated airspeed and roll angle on 0 percent of GA points, so both rest on estimates.
2. Machine-flown control group. Airline and business-jet approaches flown on coupled ILS at the well-covered towered airports (HVN, BED, and any others in the windows) are measured with the same C1, C2a, C3, and C4 ratios against the same wind variables. Their wind response estimates the floor that comes from measurement and physics rather than piloting. GA results are reported against that floor.
3. Measurement validation without onboard data:
   - Vertical: indicated height from barometric altitude against GNSS geometric height for the same points, from independent sensors. The spread gives the vertical measurement error, and it is tested against wind and gust (static pressure errors in gusts would show up here).
   - Descent rate: barometric rate against geometric rate against the differenced height track.
   - Lateral: ADS-B navigation accuracy categories (NACp) give a position error bound per point. Approaches below a set accuracy are flagged.
   - Wind at pattern height: in pattern turns, ground speed rises and falls with the wind at that height. Fitting a wind vector to many airplanes' turns per hour estimates the wind near pattern altitude, which tests the 1/7 power-law profile used for estimated airspeed. Model winds aloft (HRRR analyses) are a fallback check.
   - Measurement noise model: synthetic approaches with known deviations, degraded with ADS-B-like quantization, update rates, and position error, are run through the same pipeline to show which deviation sizes the measures can resolve.
4. Practice maneuvers. Training airports include intended non-standard approaches (power-off 180, short-field, no-flap). Approaches whose shape matches them (a continuous curved final ending below 300 ft HAT, or a steep descent from abeam the touchdown point) are flagged. Results are reported with and without flagged approaches, and the flagged share is tested against wind (instructors may avoid these drills in strong wind).
5. Statistical dependence. Approaches are clustered by aircraft and by day (one student can fly a dozen circuits). Models use random effects or cluster-robust inference for aircraft and day. Model details are set before the Q2 run.
6. Tolerances as units. With continuous severity, tolerances mainly set the scale's units. The sensitivity runs (lateral 100 and 300 ft, vertical 75 and 150 ft) are reported to show that trends do not depend on them.

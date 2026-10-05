#!/usr/bin/env python3
"""Apply the agreed review edits (2026-10-05) to paper/main.tex, which starts as Benjamin's uploaded version.
Every replacement must match exactly once."""

import sys

P = "paper/main.tex"
s = open(P).read()
R = []


def rep(old, new, count=1):
    n = s.count(old)
    if n != count:
        sys.exit(f"expected {count} match(es), found {n}:\n{old[:160]}")
    R.append((old, new))


# ------------------------------------------------------------------ abstract
rep("Activity declined to half of normal demand at a crosswind component of 11.6 kt",
    "General aviation traffic by piston airplanes fell to half of normal demand at a crosswind component of 11.6 kt")
rep("Fleet aircraft reached the threshold at lower crosswinds than privately owned aircraft (11.0 versus 12.7 kt), and only 0.07\\% of 4.9 million approaches by aircraft with a published demonstrated crosswind were flown above it.",
    "Fleet aircraft reached the threshold at lower crosswinds than privately owned aircraft (11.0 versus 12.7 kt). Only 0.07\\% of 4.9 million approaches by aircraft with a published demonstrated crosswind were flown in a sustained crosswind stronger than that value.")
rep("When 5.2 million approaches were scored against stabilized approach criteria at 300 ft,",
    "When the 5.2 million approaches with a flight path measurable at 300 ft were scored against stabilized approach criteria,")
rep("Taken together, these results indicate that pilots as a group discontinue flying before flight path control degrades appreciably, and that speed control is the first element of approach performance affected by wind.",
    "Taken together, these results indicate that pilots as a group stop flying before their flight path control degrades appreciably, and that approach speed is the first part of the approach to change with wind.")

# ------------------------------------------------------------------ introduction and background
rep("Wind is the weather hazard most frequently cited in general aviation accidents. In United States accident records from 1982 to 2013, wind was cited in more than half of weather-related accidents, and crosswind was identified in 40\\% of non-fatal wind accidents \\cite{fultz2016}.",
    "Wind is the weather hazard most often cited in general aviation accidents. Fultz and Ashley found wind in more than half of the weather-related accidents in the United States from 1982 to 2013, and crosswind in 40\\% of the nonfatal wind accidents \\cite{fultz2016}.")
rep("\\subsection{Crosswind knowledge and personal minimums}", "\\subsection{Pilot judgment and personal minimums}")
rep("found that visibility and ceiling together predicted the decision to take off better than either factor alone, while none of ten personality tests predicted it \\cite{knecht2005}.",
    "found that visibility and ceiling together predicted the decision to take off, while none of ten personality tests did \\cite{knecht2005}.")
rep("Hunter found that pilots who perceived less risk in flight situations reported more involvement in hazardous events \\cite{hunter2006}.",
    "Hunter found that inaccurate risk perception, measured as the gap between the perceived risks of flying and of driving, was a better indicator of past involvement in hazardous events than the risk ratings themselves \\cite{hunter2006}.")
rep("Childs et al.\\ gave private pilots flight checks at 8, 16, and 24 months after certification and found that their ability to predict their own skill level was negligible \\cite{childs1983}.",
    "Childs et al.\\ checked the flight skills of private pilots 8, 16, and 24 months after certification and found that the pilots' ability to predict their own skill on specific tasks was negligible \\cite{childs1983}.")
rep("Airline flight data monitoring programs grade exceedances of such criteria by severity level \\cite{faa2004ac12082}, and energy-based metrics have been proposed for general aviation safety analysis \\cite{puranik2017}.",
    "Airline flight data monitoring programs grade exceedances of such criteria by severity level \\cite{faa2004ac12082}. Puranik et al.\\ proposed energy-based metrics for general aviation safety analysis and applied them to recorded flight data \\cite{puranik2017}. The speed and sink rate checks used here are simpler measures of the same energy state.")
rep("Huang and Johnson proposed ADS-B as a data source for general aviation flight data monitoring \\cite{huang2017}, and Boyd analyzed ADS-B tracks of privately owned aircraft on cross-country flights and found that 65\\% of the aircraft crossing mountainous terrain completed at least one flight with potentially hazardous ridge-level winds \\cite{boyd2023}.",
    "Huang and Johnson proposed ADS-B as a data source for general aviation flight data monitoring \\cite{huang2017}. Boyd analyzed ADS-B tracks of 50 privately owned airplanes on cross-country flights and found that 65\\% of those transiting areas subject to mountain winds completed at least one flight with potentially hazardous ridge-level winds \\cite{boyd2023}.")

# ------------------------------------------------------------------ data
rep("Aircraft position data were obtained", "Aircraft position data was obtained")
rep("Every method in this paper was developed and tested on this sample. Archive coverage at these airports was incomplete in the early part of this period, so each airport is analyzed within a window that excludes its early gap.",
    "Every method in this paper was built and tuned on this sample, and the confirmatory sample described next is the test. Archive coverage at these airports was incomplete in the early part of this period, so each airport is analyzed within a window. The window starts at the first month after which archive capture never fell below a fixed level: 75\\% of tower operations at the towered airports (65\\% at Lawrence and Norwood, which never held 75\\%), and 60\\% of visits tracked down to 300 ft at the non-towered airports.")
rep("All methods were frozen and logged before any confirmatory data were analyzed.", "All methods were frozen and logged before any confirmatory data was analyzed.")
rep("These rules were fixed before the data were analyzed. They admitted 467 airports and 3,871 airport-months and excluded 5,442 outage days. The 467 airports comprise 309 towered and 158 non-towered airports and span all eight FAA regions of the contiguous United States.",
    "These rules were fixed before the data was analyzed. They admitted 467 airports and 3,871 airport-months and excluded 5,442 outage days. A day with no fixed-wing visits counted as an outage under this rule, so some quiet days were excluded along with receiver failures. Outage days were slightly windier than included days, and restoring all of them lowers the revealed limit from 11.6 kt to 11.5 kt. The 467 airports comprise 309 towered and 158 non-towered airports and span all eight FAA regions of the contiguous United States.\n\n"
    "The seven development airports also met the admission rule for the confirmatory sample, and the two periods overlap for 12 months. Leaving them out changes the confirmatory revealed limit by less than 0.1 kt and the performance effects by 0.1 percentage point or less.")
rep("Surface wind data were obtained", "Surface wind data was obtained")
rep("A station-month in which more than 1\\% of records failed these checks was discarded entirely, and the METAR wind was used for those hours. This filter was added after registration (Sec.~\\ref{sec:deviations}).",
    "A station-month in which more than 1\\% of records failed these checks was discarded entirely, and the METAR wind was used for those hours. The checks apply to the two-minute wind only. A five-second gust was set aside only if it exceeded 80 kt or the sustained wind by more than 40 kt. In the station-months kept, the filter removed 0.013\\% of records. This filter was added after results had been seen (Table~\\ref{tab:deviations}).")
rep("was matched to the FAA aircraft registry, using", "was matched to the FAA aircraft registry \\cite{faaregistry}, using")
rep("Three values were taken from the POH for each of the 20 aircraft types that account for 93\\% of piston approaches: the maximum demonstrated crosswind, the approach speed with landing flaps, and the stall speed in the landing configuration.",
    "Three values were taken from the POH for each of the 20 aircraft types that fly most piston approaches: the maximum demonstrated crosswind, the approach speed with landing flaps, and the stall speed in the landing configuration. These 20 types account for 92\\% of piston approaches in the development sample and 85\\% in the confirmatory sample.")
rep("Those models were assigned the value for their type family and flagged as assumed.",
    "Those models were assigned the value for their type family and flagged as assumed. Only published values are used when approaches are compared with the demonstrated crosswind.")
rep("Runway geometry was taken from the FAA National Airspace System Resource (NASR) data.",
    "Runway geometry was taken from the FAA National Airspace System Resource (NASR) data \\cite{faanasr}.")
rep("For the revealed limit analysis, a runway end was counted as available only if it is paved and at least 2,500 ft long. In the development sample, this rule excluded one 1,034 ft turf runway, a change made after registration (Sec.~\\ref{sec:deviations}).",
    "For the revealed limit analysis, a runway end was counted as available only if it is paved and at least 2,500 ft long, since few pilots of typical piston airplanes would choose a shorter or unpaved runway as the runway into the wind. The same length sets which airports were candidates for the confirmatory sample. In the development sample, this rule excluded one 1,034 ft turf runway, a change made after results had been seen (Table~\\ref{tab:deviations}).")

# ------------------------------------------------------------------ methods
rep("The reports from each aircraft within 5 nautical miles of an airport were divided into visits wherever the reports ceased for more than five minutes.",
    "A visit is the stretch of one aircraft's reports within 5 nautical miles of an airport. A gap of more than five minutes in the reports ends one visit and starts the next.")
rep("an exclusion adopted after registration (Sec.~\\ref{sec:deviations}).", "an exclusion adopted after results had been seen (Table~\\ref{tab:deviations}).")
rep("The parallel-runway rule was added after the confirmatory data were first analyzed (Sec.~\\ref{sec:deviations}).",
    "The parallel-runway rule was added after the confirmatory data was first analyzed (Table~\\ref{tab:deviations}).")
rep("in a purpose-built replay tool without access to the detector output,", "in a purpose-built replay tool without access to the detector output or the identity of the aircraft,")
rep("Set 4 comprised 100 visits drawn at random from 14 airports outside New England before the confirmatory analysis began, and it tested the frozen detector on airports not used in development. On Set 4, the detector was fully correct on 89\\% of visits, just below the criterion. Most of the errors were climb-outs, which do not enter the revealed limit or performance analyses. The detector found 97 of the 100 arrivals and assigned 80 of 81 approaches to the correct runway.",
    "Set 4 comprised 100 visits drawn at random from 14 airports outside New England before the confirmatory analysis began. It tested the frozen detector on airports not used in development. The detector was fully correct on 89 of the 100 visits, just below the criterion. Most of the errors were climb-outs, which do not enter the revealed limit or performance analyses. The 100 visits contained 55 arrivals. The detector found 54 of them and added one that was not there. It placed 80 of the 82 labeled approaches on the correct runway.")
rep("Detected operations were also compared with FAA tower counts from the Operations Network (OPSNET), following earlier studies",
    "Detected operations were also compared with FAA tower counts from the Operations Network (OPSNET) \\cite{faaopsnet}, following earlier studies")
rep("The comparison was repeated in the confirmatory sample at 20 towered airports spanning all eight FAA regions, over 6,402 included airport-days from October 2025 to August 2026.",
    "The comparison was repeated in the confirmatory sample at 20 towered airports over 6,402 included airport-days from October 2025 to August 2026. The 20 airports were chosen before any tower count was obtained. Each was admitted in all 12 months and had at least half of its fixed-wing arrivals by piston airplanes. The three busiest by piston arrivals were taken from each FAA region outside New England, with two from the Western-Pacific Region to keep the total at 20.")
rep("Capture changed by $-1.8$\\% per 10 kt of mean wind (95\\% interval $-4.0$\\% to $+0.4$\\%), again within the limit.",
    "Capture changed by $-1.8$\\% per 10 kt of mean wind (95\\% interval $-4.0$\\% to $+0.4$\\%), again within the limit. The development interval excludes zero, so the revealed limit was also computed with arrivals divided by the capture modeled at each hour's wind. The correction raises the confirmatory limit from 11.6 kt to 11.7 kt with the confirmatory slope and to 11.8 kt with the development slope, and to at most 11.9 kt at the steepest slope inside either interval.")
rep("True height was obtained by adding the standard cold-temperature correction computed from the METAR temperature.",
    "True height was obtained with the standard temperature correction, which scales the indicated height above the field by the ratio of the METAR temperature to the standard temperature at field elevation. On a 30$^\\circ$C day at a sea-level airport, 300 ft indicated is about 316 ft true.")
rep("indicated height was obtained by reversing the cold-temperature correction.", "indicated height was obtained by reversing the temperature correction.")
rep("An airplane that performs ten touch-and-goes in a single visit therefore contributes one arrival.",
    "An airplane that performs ten touch-and-goes in a single visit therefore contributes one arrival. The decision being measured is whether to fly, which a pilot makes once per visit.")
rep("The registered estimator was a Poisson regression of arrivals on crosswind $X$, headwind $H$, and gust spread $G$, with the logarithm of normal demand as an offset. That model failed its goodness-of-fit check in the development sample (Sec.~\\ref{sec:results}), so the primary estimate is model-free. Activity is the ratio of arrivals to normal demand within 2 kt crosswind bins, and the revealed limit is the crosswind at which activity falls to half of normal demand, located by interpolation between bins. Intervals were obtained from a bootstrap over days with 1,000 resamples. A Poisson model with piecewise-linear crosswind terms (knots at 5, 10, and 15 kt) provides a second estimate that, unlike the model-free estimate, holds headwind and gust spread at their medians.",
    "The primary estimate needs no model. Each VMC hour is compared with normal demand for that hour. For example, if an airport normally sees 6 piston arrivals between 10:00 and 11:00 on a summer Saturday, an hour with 3 arrivals has an activity of 0.5. Hours are grouped into 2 kt bins of crosswind, and activity in each bin is the total of arrivals divided by the total of normal demand. The revealed limit is the crosswind at which activity reaches 0.5, found by interpolating between bins. Intervals come from 1,000 bootstrap resamples of whole days.\n\n"
    "Two Poisson models provide a check. The prespecified model regressed arrivals on crosswind $X$, headwind $H$, and gust spread $G$, with the logarithm of normal demand as an offset. It assumes that each knot of crosswind cuts traffic by the same percentage. In the development sample, traffic held steady to about 5 kt and then fell steeply, so that model failed its goodness-of-fit check (Sec.~\\ref{sec:results}). A second Poisson model with piecewise-linear terms in all three wind variables (knots at 5, 10, and 15 kt) fits the data. It holds headwind and gust spread at their medians, so it shows the effect of crosswind alone. Intervals for both models come from 200 bootstrap resamples of whole days.")
rep("For every piston approach in VMC by an aircraft with a demonstrated crosswind value,", "For every piston approach in VMC by an aircraft with a published demonstrated crosswind value,")
rep("Sink rate at each point is the median of the vertical rates reported within 5 s.",
    "Sink rate at each point is the median of the vertical rates reported within 5 s. The 1,000 ft/min sink rate follows the Handbook and the Flight Safety Foundation \\cite{faa2021afh,fsf2000}. The published criteria state the other checks only in words, such as tracking the centerline, so their tolerances are definitions of this study.")
rep("It therefore expresses how far outside the stabilized window the approach was at its worst point below 300 ft.",
    "It therefore expresses how far outside the stabilized window the approach was at its worst point below 300 ft. Lower scores are better. An approach flown exactly on the centerline and glide path still scores about 0.4, since its descent rate of about 400 ft/min is 0.4 of the 1,000 ft/min limit.")
rep("with the surface wind scaled to the height of the airplane using a 1/7 power-law profile.",
    "with the surface wind scaled to the height of the airplane using a 1/7 power-law profile. The estimate ignores the wind across the track, which the airplane also flies into while crabbing. At 70 kt this understates airspeed by about 0.7 kt at 10 kt of crosswind and 1.6 kt at 15 kt, so the speed results are conservative.")
rep("The conversion was added after registration (Sec.~\\ref{sec:deviations}).", "The conversion was added after results had been seen (Table~\\ref{tab:deviations}).")
rep("The value check compares estimated airspeed with a target equal to the handbook approach speed plus half the gust spread $G$. A deficit is divided by 5 kt and an excess by 10 kt, so an airplane that is 5 kt slow or 10 kt fast scores 1. The consistency check divides the spread of airspeed about its linear trend over the 30 s before the gate by 10 kt, so a steady deceleration to approach speed is not penalized.",
    "The value check compares estimated airspeed with a target equal to the handbook approach speed plus half the gust spread $G$, at the 300 ft crossing and at every report down to 100 ft. A deficit is divided by 5 kt and an excess by 10 kt, so an airplane that is 5 kt slow or 10 kt fast scores 1. This band follows the Private Pilot Airman Certification Standards, which allow 10 kt fast but only 5 kt slow \\cite{faa2023acs}. A slow approach puts the wing near its critical angle of attack, where the airplane can stall or sink rapidly \\cite{faa2021afh}, while a fast approach mainly lengthens the flare and the landing roll. The consistency check fits a straight line to the estimated airspeed over the 30 s before the gate and takes the range of the departures from that line. A range of 10 kt scores 1, so a steady deceleration to approach speed scores near zero. Airplanes outside the 20 types have no handbook approach speed, so their speed score is the consistency check alone.")
rep("No onboard flight data were available", "No onboard flight data was available")
rep("Scores and ratings ranked the approaches similarly (Spearman rank correlation 0.74).",
    "Flight-path scores and ratings ranked the approaches similarly (Spearman rank correlation 0.69 on 29 measurable approaches, 95\\% interval 0.42 to 0.85).")
rep("with exponents of 0 and 1/4, as registered, and with", "with exponents of 0 and 1/4, as prespecified, and with")
rep("\\subsection{Statistical analysis and pre-registration}", "\\subsection{Statistical analysis and prespecification}")
rep("Every rule was entered in a dated decision log before the analysis it governs was run. Changes made after results had been seen are identified as such, with the reason for each, and the registered result is reported alongside the revised one.",
    "Every rule was entered in a dated decision log before the analysis it governs was run. The log is published with the code. Changes made after results had been seen are identified as such, with the reason for each, and the prespecified result is reported alongside the revised one.")
rep("Regression models estimate how the share above each threshold and the logarithm of the score change with crosswind. The models include gust spread $G$ and headwind $H$, include fixed effects for each airport and runway, and adjust for aircraft type, ownership, season, straight-in versus pattern entry, and height source.",
    "Linear probability models estimate how the share above each threshold changes with crosswind, and linear models of the logarithm of the score estimate how the whole distribution shifts. Crosswind enters the share models as a piecewise-linear term with knots at 5, 10, and 15 kt, and the log-score models as a straight line. The models include gust spread $G$, headwind $H$, a fixed effect for each runway end at each airport, and controls for aircraft type, ownership, season, straight-in versus pattern entry, and height source.")
rep("\\subsection{Changes after registration}\\label{sec:deviations}", "\\subsection{Changes to prespecified rules}\\label{sec:deviations}")
rep("lists each change made to a registered rule after results had been seen, in either sample. Each change corrects a measurement or data fault, aligns a rule across the two samples, or replaces an estimator that failed its own check.",
    "lists each change made to a prespecified rule after results had been seen, in either sample. Each change corrects a measurement or data fault, aligns a rule across the two samples, or replaces an estimator that failed its own check or could not be fitted at the scale of the confirmatory sample.")
rep("& The registered log-linear Poisson model failed its fit check in the development sample & The log-linear model, reported as registered, places the limit beyond the observed data (26 to 27 kt) \\\\",
    "& The prespecified log-linear Poisson model failed its fit check in the development sample & The log-linear model, reported as prespecified, places the limit beyond the observed data (27.0 kt in the confirmatory sample and 27.8 kt in the development sample) \\\\")
rep("Inferred passes not scored & No observed flight path & Shares above each threshold about 1 percentage point lower. Wind effects unchanged \\\\",
    "Inferred passes not scored & No observed flight path & Shares above each threshold about 1 percentage point lower. Wind effects unchanged \\\\\n"
    "Linear probability models for the shares & The prespecified logistic models are impractical with thousands of airport-runway fixed effects & Made before any confirmatory result. A logistic model with airport fixed effects gives the same changes at the threshold of 1 and larger ones at the threshold of 2 (3.4 versus 2.0 points at 15 kt) \\\\")

# ------------------------------------------------------------------ results
rep("The registered log-linear model did not fit the data.", "The prespecified log-linear model did not fit the data.")
rep("The approach performance analysis uses 5.19 million measurable piston approaches at 428 airports, with 6.79 million straight-in jet approaches as the comparison group.",
    "The approach performance analysis uses 5.19 million measurable piston approaches at 427 airports, with 6.80 million straight-in jet approaches as the comparison group, two thirds of them at the 30 busiest airline airports.\n\n"
    "The comparison with the demonstrated crosswind and the performance analysis use different subsets of the 6.54 million piston approaches flown in VMC (Table~\\ref{tab:counts}). The comparison needs a published demonstrated crosswind for the airplane and a wind reading at the lowest point of the approach. It also counts inferred passes, which are operations even without an observed flight path. It uses 4.93 million approaches. The performance analysis needs a flight path measured at 300 ft and the wind at that point, whatever the aircraft type. It uses 5.19 million approaches. About 3.98 million approaches are in both. The other 0.95 million in the comparison were inferred or could not be measured at 300 ft, and the other 1.21 million in the performance analysis were flown by aircraft with no published demonstrated crosswind.\n\n"
    "\\begin{table}[hbt!]\n"
    "\\caption{\\label{tab:counts} Approaches in each analysis, United States}\n"
    "\\centering\n"
    "\\small\n"
    "\\begin{tabular}{@{}lr@{}}\n"
    "\\toprule\n"
    "Approaches & Number \\\\\n"
    "\\midrule\n"
    "Detected at admitted airports on included days & 16,800,302 \\\\\n"
    "\\quad Flown by piston airplanes & 7,183,705 \\\\\n"
    "\\quad\\quad In VMC & 6,539,832 \\\\\n"
    "Comparison with the demonstrated crosswind & \\\\\n"
    "\\quad Published value and wind at the lowest point & 4,934,969 \\\\\n"
    "\\quad Above the demonstrated crosswind, sustained wind & 3,509 \\\\\n"
    "Approach performance & \\\\\n"
    "\\quad Flight path measured at 300 ft, with wind at that point & 5,190,504 \\\\\n"
    "\\quad With a published demonstrated crosswind & 3,982,968 \\\\\n"
    "\\quad Above the demonstrated crosswind at 300 ft & 2,468 \\\\\n"
    "In both analyses & 3,982,667 \\\\\n"
    "\\bottomrule\n"
    "\\end{tabular}\n"
    "\\end{table}")
rep("Activity reaches half of normal demand at 11.6 kt (95\\% bootstrap interval 11.3 to 11.8 kt) and three quarters of normal demand at 8.2 kt.",
    "Activity reaches half of normal demand at 11.6 kt (95\\% bootstrap interval 11.3 to 11.8 kt) and three quarters of normal demand at 8.2 kt. Counting every approach instead of one arrival per visit lowers the limit to 10.8 kt, since pilots also cut pattern sessions short in wind.")
rep("The spline Poisson model, which holds headwind and gust spread at their medians, places the limit at 13.3 kt. The registered log-linear model again failed its fit check.",
    "The spline Poisson model, which holds headwind and gust spread at their medians, places the limit at 13.3 kt. The gap from the model-free estimate comes mostly from gusts. Stronger crosswinds usually come with larger gust spreads, which averaged 4.9 kt in the calmest hours and 10.5 kt at 10 to 12 kt of crosswind. With the gust spread set to the level seen at each crosswind, the model places the limit at 12.3 kt. In hours with a gust spread of 6.4 kt or less, traffic fell to half of normal demand only at 15.6 kt of crosswind, and in hours with a gust spread of 8 kt or more it did so at 10.6 kt. The prespecified log-linear model again failed its fit check.")
rep("\\caption{\\label{tab:limits} Revealed limits: crosswind at which activity falls to half of normal demand, kt (95\\% interval)}",
    "\\caption{\\label{tab:limits} Revealed limits: crosswind at which activity falls to half of normal demand, kt (95\\% interval). In New England, the row for all piston aircraft covers the five towered airports, and the non-towered row covers Plymouth and Taunton}")
rep("Towered airports & 11.8 (11.5 to 12.1) & \\\\", "Towered airports & 11.8 (11.5 to 12.1) & 10.8 (10.3 to 11.6) \\\\")
rep("Non-towered airports & 10.6 (10.3 to 11.1) & \\\\", "Non-towered airports & 10.6 (10.3 to 11.1) & 8.7 (8.3 to 11.1) \\\\")
rep("Log-linear model, as registered &", "Log-linear model, as prespecified &")
rep("Of 4.93 million piston approaches by aircraft with a demonstrated crosswind value,", "Of 4.93 million piston approaches by aircraft with a published demonstrated crosswind value,")
rep("Near calm, 49.5\\% of approaches had a flight-path score above 1, 17.3\\% above 2, and 10.6\\% above 3.",
    "Near calm, 49.5\\% of approaches had a flight-path score above 1, 17.3\\% above 2 (twice the tolerance), and 10.6\\% above 3.")
rep("Relative to calm wind, the model estimated an increase of 13.4 points at 15 kt. Most of the increase reflects excess speed.",
    "Relative to calm wind, the model estimated an increase of 13.4 points at 15 kt. For the 20 types with a handbook approach speed, 45.3\\% of approaches had a speed score above 1 near calm, and the share rose by 15.7 points at 15 kt. Most of the increase reflects excess speed.")
rep("Approaches more than 5 kt slow were rare (3.5\\% near calm) except with a tailwind of 5 kt or more (11.0\\%).",
    "Approaches more than 5 kt slow were rare (3.5\\% near calm) except with a tailwind of 5 kt or more (11.0\\%). Speed also became less steady. The consistency check alone exceeded 1 on 5.3\\% of approaches near calm, 9.1\\% at 10 to 14 kt, and 13.5\\% at 15 to 19 kt. Jets moved the other way, from 25.6\\% to 9.2\\%, so the rise is unlikely to come from the airspeed estimate alone.")
rep("ranging from 7.4 points at 15 kt with no growth to 18.0 points with the steepest registered profile.",
    "ranging from 7.4 points at 15 kt with no growth to 18.0 points with the steepest prespecified profile.")
rep("Headwind was also associated with excess speed, with each 5 kt raising the share of speed scores above 1 by 5.8 points. This estimate depends on the assumed wind profile, since estimated airspeed is constructed from the headwind (Sec.~\\ref{sec:performance}).",
    "Headwind was also associated with excess speed, but this estimate rests on the assumed wind profile, since estimated airspeed is built from the headwind (Sec.~\\ref{sec:performance}). Each 5 kt of headwind raised the share of speed scores above 1 by 5.8 points with the 1/7 profile and by 1.2 points if the wind does not grow with height.")
rep("The effect of wind appears mainly in speed, with 48.0\\% of speed scores above 1 compared with 39.4\\% in calm wind. Above the maximum demonstrated crosswind, both measures are worse, with 21.0\\% of flight-path scores above 2 and 66.5\\% of speed scores above 1. Few approaches are flown there, only 2,968 of 5.2 million.",
    "The effect of wind appears mainly in speed, with 48.5\\% of speed scores above 1 compared with 39.9\\% in calm wind. Above the maximum demonstrated crosswind, both measures are worse, with 20.3\\% of flight-path scores above 2 and 65.8\\% of speed scores above 1. Few approaches are flown there, only 2,468 of 5.2 million. Most approaches are flown in light crosswind: 77.9\\% below 5 kt, 19.9\\% at 5 to 9 kt, and 1.9\\% at 10 kt or more.")
rep("\\caption{\\label{tab:calibration} Approach performance at four points on the crosswind scale, United States, share of approaches above each threshold (percent)}",
    "\\caption{\\label{tab:calibration} Approach performance at four points on the crosswind scale, United States, share of approaches above each threshold (percent, 95\\% interval)}")
rep("""\\begin{tabular}{@{}lrrrrr@{}}
\\toprule
 & Approaches & $S_\\mathrm{fp} > 1$ & $S_\\mathrm{fp} > 2$ & $S_\\mathrm{fp} > 3$ & $S_\\mathrm{spd} > 1$ \\\\
\\midrule
Calm, crosswind below 5 kt & 4,054,893 & 49.5 & 17.3 & 10.6 & 39.4 \\\\
Revealed limit, 11.6 kt $\\pm$ 1 kt & 53,540 & 52.2 & 17.4 & 10.8 & 48.0 \\\\
0.75 to 1.0 of maximum demonstrated & 30,148 & 56.3 & 17.9 & 11.1 & 57.4 \\\\
Above maximum demonstrated & 2,968 & 60.3 & 21.0 & 13.4 & 66.5 \\\\
\\bottomrule
\\end{tabular}""",
    """\\begin{tabular}{@{}lrcccc@{}}
\\toprule
 & Approaches & $S_\\mathrm{fp} > 1$ & $S_\\mathrm{fp} > 2$ & $S_\\mathrm{fp} > 3$ & $S_\\mathrm{spd} > 1$ \\\\
\\midrule
Calm, crosswind below 5 kt & 4,054,893 & 49.5 [49.1, 49.8] & 17.3 [17.0, 17.5] & 10.6 [10.4, 10.8] & 39.9 [39.6, 40.3] \\\\
Revealed limit, 11.6 kt $\\pm$ 1 kt & 53,540 & 52.2 [51.6, 52.9] & 17.4 [16.8, 17.9] & 10.8 [10.3, 11.2] & 48.5 [47.9, 49.1] \\\\
0.75 to 1.0 of maximum demonstrated & 26,585 & 55.8 [54.9, 56.7] & 17.6 [16.9, 18.3] & 10.8 [10.2, 11.4] & 56.8 [55.9, 57.7] \\\\
Above maximum demonstrated & 2,468 & 60.7 [58.1, 63.1] & 20.3 [18.1, 22.4] & 12.8 [11.0, 14.7] & 65.8 [63.3, 67.9] \\\\
\\bottomrule
\\multicolumn{6}{@{}p{0.97\\textwidth}@{}}{\\footnotesize Intervals are the wider of bootstraps clustered by aircraft and by day. Maximum demonstrated crosswinds are published values only. Speed shares are of approaches with a speed score.}
\\end{tabular}""")
rep("Relative to calm wind, the share above 2 at 15 kt rose by 2.1 points with NACp 10 positions only,",
    "Relative to calm wind, the share above 2 (twice the tolerance) at 15 kt rose by 2.1 points with NACp 10 positions only,")
rep("and lowered it at the threshold of 2 from 6.5 to 4.4 points (Table~\\ref{tab:deviations}).",
    "and lowered it at the threshold of 2 from 6.5 to 4.4 points (Table~\\ref{tab:deviations}). With the centerline tolerance set to 100 or 300 ft, or the glide path tolerance to 75 or 150 ft, the share above 2 still rose by 1.9 to 3.2 points at 15 kt. Clustering the standard errors by airport-day, by aircraft and airport-day together, or by airport left every wind effect clear of zero. Clustering by airport, the most conservative choice, widened the interval for the share above 1 at 15 kt from 6.1 to 7.7 points to 5.8 to 7.9 points. At the secondary 500 ft gate, most pattern approaches were still turning, so 74\\% exceeded a position or path tolerance in calm wind. The crosswind effect there was similar, with the share of those checks above 2 rising by 2.1 points at 15 kt.")
rep("increase in each share above its calm-wind level (crosswind below 4 kt), in percentage points.",
    "increase in each share above its calm-wind level (crosswind below 5 kt), in percentage points.")

# ------------------------------------------------------------------ discussion and back matter
rep("Performance measured in strong crosswind therefore belongs to a self-selected group and probably understates the degradation that would occur if every pilot flew.",
    "Performance measured in strong crosswind therefore belongs to a self-selected group and probably understates the degradation that would occur if every pilot flew. Self-selection is also consistent with calibration, since pilots who doubt their crosswind skill stay on the ground.")
rep("At 300 ft, the median estimated airspeed was about 6 kt above the target of handbook approach speed plus half the gust spread near calm, and about 11 kt above it in strong headwinds.",
    "At 300 ft, the median estimated airspeed was about 6 kt above the target of handbook approach speed plus half the gust spread near calm, and about 11 kt above it in strong headwinds with the assumed wind profile.")
rep("A tailwind on base of 10 to 20 kt was associated with a threefold increase in the rate of overshooting the centerline by more than 200 ft, and a headwind on base made late alignment more common. An overshoot creates the conditions for the skidding base-to-final turn that the Handbook warns against \\cite{faa2021afh}. Instructors could therefore treat the wind on the base leg, in addition to crosswind strength, as a planning consideration for the turn to final.",
    "A tailwind on base of 10 to 20 kt was associated with a threefold increase in the rate of overshooting the centerline by more than 200 ft, and a headwind on base made late alignment more common. By the scores, a headwind on base was the worse case, since late alignment left more approaches outside tolerance at 300 ft (30.9\\% of flight-path scores above 2, against 18.4\\% with a tailwind on base and 23.0\\% in calm wind). The scores weigh a late alignment and an overshoot alike, however, and the risks differ. The Handbook describes the overshoot as the setup for a skidding, cross-controlled stall: a tailwind on base raises the ground speed, the pilot turns late and overshoots the centerline, and then tightens the turn with rudder toward the inside of the turn \\cite{faa2021afh}. The scores therefore understate the risk of a tailwind on base. Instructors could treat the wind on the base leg, in addition to crosswind strength, as a planning consideration for the turn to final.")
rep("Only 2.8\\% of straight-in approaches scored above 2, compared with 17.3\\% of all approaches in calm wind,",
    "Only 2.8\\% of straight-in approaches scored above 2 in calm wind, compared with 17.3\\% of all approaches,")
rep("ADS-B data were obtained from ADSB.lol under the Open Database License (ODbL), and derived data are shared under the same license. Weather data were obtained from the Iowa Environmental Mesonet, which distributes the NOAA ASOS one-minute and METAR archives. Airport, runway, registry, and tower-count data were obtained from the Federal Aviation Administration.",
    "ADS-B data was obtained from ADSB.lol under the Open Database License (ODbL), and derived data is shared under the same license. Weather data was obtained from the Iowa Environmental Mesonet, which distributes the NOAA ASOS one-minute and METAR archives. Airport, runway, registry, and tower-count data was obtained from the Federal Aviation Administration. The author used Claude (Anthropic), an AI assistant, to write and run analysis code under the author's direction, to locate and check sources, and to draft and edit text and figures. The author designed the study, made every analytic decision, labeled the validation data, reviewed all code, results, and text, and is responsible for the content.\n\n"
    "\\section*{Data Availability}\n"
    "The code, the dated decision log, and aggregate results are available at [repository URL] (archived at [DOI]). Aircraft position data is available from ADSB.lol under the Open Database License, and weather, registry, airport, and tower-count data from the public sources cited.")

for old, new in R:
    s = s.replace(old, new)
open(P, "w").write(s)
print(f"{len(R)} edits applied")

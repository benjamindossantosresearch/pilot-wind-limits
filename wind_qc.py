"""
wind_qc.py

Quality control for the one-minute ASOS wind (found 2026-10-02 in the US run:
at some stations 1.5 to 2.5 percent of one-minute records carry spikes above
40 kt that the METAR from the same sensor does not show).

A one-minute record is dropped when any of these holds:
  * the two-minute wind is above MAX_KT
  * it differs by more than DIFF_KT from the nearest METAR within 30 minutes
  * it differs by more than DIFF_KT from the median of the records within 5 minutes
    (an isolated spike; a real change in wind lasts longer than that)
A station-month in which more than 1 percent of records fail is dropped whole.
Dropped minutes count as missing. Hours with fewer than 30 valid minutes fall
back to the METAR, and a gate with no valid minute within 2 minutes uses the
METAR, as before.

    clean, n_dropped = qc_onemin(onemin, metar_times, metar_speeds)
onemin: dict minute -> (drct, sknt, gust_drct, gust_sknt)
metar_times: sorted epoch seconds, metar_speeds: matching sustained speeds (kt or None)
"""

import bisect
import statistics

MAX_KT = 60.0
DIFF_KT = 15.0
METAR_WINDOW_S = 30 * 60


MONTH_DROP_SHARE = 0.01


def qc_onemin(onemin, metar_times, metar_speeds):
    """Minute-level filter, then a station-month filter: a month in which more than MONTH_DROP_SHARE of the
    records fail is dropped whole (the sensor or its archive is unreliable that month), and its hours use METAR."""
    import datetime as _dt
    clean, dropped = _qc_minutes(onemin, metar_times, metar_speeds)
    if not onemin:
        return clean, dropped
    month = lambda m: _dt.datetime.fromtimestamp(m * 60, _dt.timezone.utc).strftime("%Y-%m")
    total, kept = {}, {}
    for m in onemin:
        total[month(m)] = total.get(month(m), 0) + 1
    for m in clean:
        kept[month(m)] = kept.get(month(m), 0) + 1
    bad_months = {mo for mo, n in total.items() if n and (n - kept.get(mo, 0)) / n > MONTH_DROP_SHARE}
    if bad_months:
        before = len(clean)
        clean = {m: r for m, r in clean.items() if month(m) not in bad_months}
        dropped += before - len(clean)
    return clean, dropped


def _qc_minutes(onemin, metar_times, metar_speeds):
    if not onemin:
        return onemin, 0
    mins = sorted(onemin)
    out, dropped = {}, 0
    for k, m in enumerate(mins):
        rec = onemin[m]
        s = rec[1]
        if s is None:
            out[m] = rec
            continue
        bad = s > MAX_KT
        if not bad:
            t = m * 60
            i = bisect.bisect_left(metar_times, t)
            near = [j for j in (i - 1, i) if 0 <= j < len(metar_times) and abs(metar_times[j] - t) <= METAR_WINDOW_S
                    and metar_speeds[j] is not None]
            if near:
                j = min(near, key=lambda j: abs(metar_times[j] - t))
                bad = abs(s - metar_speeds[j]) > DIFF_KT
        if not bad:
            w = [onemin[mins[q]][1] for q in range(max(0, k - 5), min(len(mins), k + 6))
                 if q != k and abs(mins[q] - m) <= 5 and onemin[mins[q]][1] is not None]
            if len(w) >= 4 and abs(s - statistics.median(w)) > DIFF_KT:
                bad = True
        if bad:
            dropped += 1
            continue
        g = rec[3]
        if g is not None and (g > MAX_KT + 20 or g - s > 40):
            rec = (rec[0], rec[1], rec[2], None)     # implausible gust: keep the sustained wind, drop the gust
        out[m] = rec
    return out, dropped

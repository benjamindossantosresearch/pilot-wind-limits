#!/usr/bin/env python3
"""
q1a_outage_check.py

Benjamin's question on the draft: could the outage-day rule throw away windy days? An outage day is a day whose
share of fixed-wing visits seen to 300 ft is below half the airport median, and a day with no fixed-wing visits
at all counts as an outage. This check (post-hoc, logged 2026-10-05):

  * weather on outage days against included days (VMC share, mean wind, mean best-runway crosswind), split by
    how many fixed-wing visits the day had (0, 1 to 4, 5 or more)
  * the revealed limit with low-traffic outage days put back (outage only when the day had 5 or more visits),
    and with every outage day put back

Same code path as us_q1a.py (airport_rows), outputs only in review_2026-10-05/.

    python3 review_2026-10-05/q1a_outage_check.py --workers 48
"""

import argparse
import datetime as dt
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import q1a_crosswind as qc  # noqa: E402
import us_airports as ua  # noqa: E402
import us_inclusion as ui  # noqa: E402
import wind_qc  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "q1a_outage_check.txt")
GROUPS = ("piston", "fleet", "private")


def day_class(inc, a, utc_day):
    """'ok' (included), 'out0', 'out1_4', 'out5' (outage by visits that day), or None (not in an admitted month)."""
    if a in ui.CLOSED_FROM and utc_day >= ui.CLOSED_FROM[a]:
        return None
    if utc_day not in inc.days_present or not inc.month_ok(a, utc_day[:7]):
        return None
    if utc_day not in inc.outage.get(a, set()):
        return "ok"
    fo = inc.cov_day[a].get(utc_day, (0, 0))[0]
    return "out0" if fo == 0 else ("out1_4" if fo < 5 else "out5")


def airport_rows(args):
    a, counts = args
    inc = ui.load()
    site = ua.load()[a]
    ends = inc.usable_ends(a)
    if not ends:
        return a, []
    onemin = qc.load_onemin(site.station)
    metars, mtimes = qc.load_metar_obs(site.station)
    onemin, _ = wind_qc.qc_onemin(onemin, [t.timestamp() for t in mtimes], [o["sknt"] for o in metars])
    by_hour = {(d, h): c for d, h, c in counts}
    rows = []
    d = dt.date(2025, 10, 1)
    rank = {"ok": 0, "out5": 1, "out1_4": 2, "out0": 3}
    while d <= dt.date(2026, 9, 30):
        t_first = dt.datetime(d.year, d.month, d.day, 8, tzinfo=site.tz)
        t_last = dt.datetime(d.year, d.month, d.day, 18, 59, tzinfo=site.tz)
        utc_days = {t_first.astimezone(dt.timezone.utc).date().isoformat(), t_last.astimezone(dt.timezone.utc).date().isoformat()}
        cls = [day_class(inc, a, u) for u in utc_days]
        if all(c is not None for c in cls) and inc.month_ok(a, d.isoformat()[:7]):
            worst = max(cls, key=lambda c: rank[c])
            for h in range(8, 19):
                t0 = dt.datetime(d.year, d.month, d.day, h, tzinfo=site.tz).timestamp()
                wx = qc.hour_weather(t0, onemin, metars, mtimes, ends)
                if wx is None:
                    continue
                c = by_hour.get((d.isoformat(), h), (0, 0, 0, 0))
                rows.append({"airport": a, "local_date": d.isoformat(), "hour": h, "weekend": d.weekday() >= 5,
                             "season": qc.season_key(d, "window"), "piston": c[0], "fleet": c[1], "private": c[2],
                             "day": worst, **wx})
        d += dt.timedelta(days=1)
    return a, rows


def with_baseline(rows):
    cells = defaultdict(list)
    for r in rows:
        cells[(r["airport"], r["season"], r["weekend"], r["hour"])].append(r)
    kept = []
    for g in cells.values():
        if len(g) < qc.MIN_CELL_HOURS:
            continue
        for grp in GROUPS:
            m = sum(r[grp] for r in g) / len(g)
            for r in g:
                r[f"base_{grp}"] = m
        kept.extend(g)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=48)
    args = ap.parse_args()
    inc = ui.load()
    per = defaultdict(list)
    for a, d, h, p, f, pr, al in inc.counts:
        per[a].append((d, h, (p, f, pr, al)))
    rows = []
    with ProcessPoolExecutor(args.workers) as ex:
        for a, r in ex.map(airport_rows, [(a, per.get(a, [])) for a in inc.included_airports()]):
            rows.extend(r)
    L = ["Outage days and wind (US, admitted airport-months, local 08:00 to 18:59, all hours with weather)", ""]
    for cls, name in (("ok", "included days"), ("out5", "outage days with 5 or more fixed-wing visits"),
                      ("out1_4", "outage days with 1 to 4 visits"), ("out0", "outage days with no fixed-wing visits")):
        g = [r for r in rows if r["day"] == cls]
        if not g:
            continue
        v = [r for r in g if r["vmc"]]
        L.append(f"  {name}: {len({(r['airport'], r['local_date']) for r in g}):,} airport-days, {len(g):,} hours, VMC {100 * len(v) / len(g):.1f}%, "
                 f"mean wind {np.mean([r['speed'] for r in g]):.1f} kt, mean best-runway crosswind {np.mean([r['xw'] for r in g]):.1f} kt, "
                 f"hours with crosswind 10 kt or more {100 * np.mean([r['xw'] >= 10 for r in g]):.2f}%, "
                 f"piston arrivals per VMC hour {np.mean([r['piston'] for r in v]) if v else float('nan'):.2f}")
    L.append("")
    vmc = [r for r in rows if r["vmc"]]
    for label, keep in (("as locked (outage days out)", {"ok"}),
                        ("outage only with 5 or more visits (days with 0 to 4 visits put back)", {"ok", "out0", "out1_4"}),
                        ("every outage day put back", {"ok", "out0", "out1_4", "out5"})):
        sel = with_baseline([dict(r) for r in vmc if r["day"] in keep])
        L.append(f"{label}: {len(sel):,} VMC airport-hours at {len({r['airport'] for r in sel})} airports")
        for grp in GROUPS:
            L += qc.empirical_limit(sel, grp, f"  {grp}")
        L.append("")
    text = "\n".join(L)
    open(OUT, "w").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()

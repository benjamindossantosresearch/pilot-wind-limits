#!/usr/bin/env python3
"""
logit_check.py

The New England plan registered logistic models for the shares above 1 and 2. The US script (us_q2.py) uses
linear probability models with airport-runway effects absorbed, because logistic models with thousands of
airport-runway effects do not scale. This check (post-hoc, 2026-10-05) fits the registered logistic form on the
US primary sample with airport fixed effects (427 airports) and the registered controls, and reports average
marginal changes against calm crosswind at 10 and 15 kt, next to the linear probability estimates.
Also counts admitted airports at each step of the approach sample.

    python3 review_2026-10-05/logit_check.py review_2026-10-05/us_cas.pkl
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import us_inclusion as ui  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logit_check.txt")
L = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


_X = None
_Y = None


def _part(args):
    """Hessian and score of one row chunk (numpy here runs single-threaded BLAS, so chunks go to processes)."""
    lo, hi, beta = args
    Xc = _X[lo:hi]
    eta = np.clip(Xc @ beta, -30, 30)
    p = 1 / (1 + np.exp(-eta))
    W = p * (1 - p)
    return Xc.T @ (Xc * W[:, None]), Xc.T @ (_Y[lo:hi] - p)


def logit_irls(X, y, iters=12, workers=48):
    global _X, _Y
    _X, _Y = X, y
    from multiprocessing import get_context
    n = len(y)
    edges = np.linspace(0, n, workers * 2 + 1).astype(int)
    beta = np.zeros(X.shape[1])
    beta[0] = np.log(y.mean() / (1 - y.mean()))
    with get_context("fork").Pool(workers) as pool:
        for _ in range(iters):
            parts = pool.map(_part, [(edges[i], edges[i + 1], beta) for i in range(len(edges) - 1)])
            H = sum(h for h, _ in parts)
            g = sum(gg for _, gg in parts)
            step = np.linalg.solve(H + 1e-8 * np.eye(len(beta)), g)
            beta = beta + step
            if np.max(np.abs(step[:7])) < 1e-6:   # wind and intercept terms settled (airport terms of tiny airports may drift)
                break
    return beta


def spline_cols(x):
    return np.column_stack([x] + [np.clip(x - k, 0, None) for k in (5, 10, 15)])


def main(pkl):
    df = pd.read_pickle(pkl)
    inc = ui.load()
    adm = set(inc.included_airports())
    d_inc = df[df["day_ok"]]
    say(f"Admitted airports {len(adm)}. With any detected approach on included days {d_inc['airport'].nunique()}. "
        f"With a piston approach in VMC {d_inc[(d_inc['group'] == 'piston') & (d_inc['vmc'] == 1)]['airport'].nunique()}. "
        f"With a measurable piston approach {d_inc[(d_inc['group'] == 'piston') & (d_inc['vmc'] == 1) & (d_inc['status'] == 'ok')]['airport'].nunique()}.")
    Q = d_inc[(d_inc["group"] == "piston") & (d_inc["vmc"] == 1) & (d_inc["status"] == "ok")]
    Q = Q[Q["xw_kt"].notna() & Q["hw_kt"].notna() & Q["gust_spread"].notna()].copy()
    n_all = len(Q)
    Q = Q.sample(n=1_500_000, random_state=20261005)   # functional-form check: a random 1.5 million approaches
    say(f"Random sample of 1,500,000 of the {n_all:,} measurable approaches with gate wind (seed 20261005)")
    small = Q.groupby("airport", observed=True).size()
    say(f"Airports with fewer than 200 measurable piston approaches (kept in pooled results): {int((small < 200).sum())}")
    dummies = [pd.get_dummies(Q[c].astype(str), prefix=c, drop_first=True, dtype=np.float32)
               for c in ("airport", "typeg", "own", "season", "straight_in", "height_source")]
    Z = pd.concat(dummies, axis=1).values.astype(np.float64)
    W = np.column_stack([spline_cols(Q["xw_kt"].values), Q["hw_kt"].values, Q["gust_spread"].values])
    X = np.column_stack([np.ones(len(Q)), W, Z])
    say(f"Design: {X.shape[0]:,} approaches, {X.shape[1]} columns (airport fixed effects and registered controls)")
    for value, thr in (("S_fp", 1), ("S_fp", 2), ("S_spd", 1)):
        m = Q[value].notna().values
        y = (Q[value].values[m] > thr).astype(float)
        Xm = X[m] if not m.all() else X
        beta = logit_irls(Xm, y)
        base = None
        out = []
        for x in (0, 10, 15):
            Xc = Xm.copy()
            Xc[:, 1:5] = spline_cols(np.full(len(Xc), float(x)))
            p = (1 / (1 + np.exp(-np.clip(Xc @ beta, -30, 30)))).mean()
            if x == 0:
                base = p
            else:
                out.append(f"{x} kt {100 * (p - base):+.1f}")
        say(f"  logistic, {value} above {thr}: average predicted share at calm {100 * base:.1f}%, change " + ", ".join(out))
    open(OUT, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])

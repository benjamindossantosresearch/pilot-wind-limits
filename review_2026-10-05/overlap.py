import pandas as pd
df = pd.read_pickle("review_2026-10-05/us_cas.pkl")
P = df[df["day_ok"] & (df["group"] == "piston") & (df["vmc"] == 1)]
q1b = P["xw_low_kt"].notna() & (P["poh_xwind_basis"].astype(str) == "published")
q2 = (P["status"] == "ok") & P["xw_kt"].notna()
q2m = P["status"] == "ok"
print(f"piston VMC {len(P):,}; Q1b {int(q1b.sum()):,}; Q2 measurable {int(q2m.sum()):,}; Q2 with gate wind {int(q2.sum()):,}")
print(f"both (Q1b and Q2 with gate wind) {int((q1b & q2).sum()):,}; Q1b only {int((q1b & ~q2).sum()):,}; Q2 only {int((~q1b & q2).sum()):,}; neither {int((~q1b & ~q2).sum()):,}")
print(f"Q1b only: inferred {int((q1b & ~q2 & P['is_inferred']).sum()):,}, not measurable observed {int((q1b & ~q2 & ~P['is_inferred']).sum()):,}")
print(f"Q2 only: no POH value {int((~q1b & q2 & P['poh_xwind_basis'].isna()).sum()):,}, assumed value {int((~q1b & q2 & (P['poh_xwind_basis'].astype(str)=='assumed')).sum()):,}, published but no low-point wind {int((~q1b & q2 & (P['poh_xwind_basis'].astype(str)=='published')).sum()):,}")

"""Controle: Jaccard entre partições da MESMA janela com sementes diferentes (ruído algorítmico)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import mo_communities as mc

rows = []
for layer in ("all", "answers", "comments"):
    df = mc.load_edges(layer=layer)
    for w in (365, 180):
        for t, (lo, hi) in enumerate(mc.make_windows(df, w)):
            G = mc.build_graph(df, lo, hi)
            sets = []
            for seed in (0, 1):
                U, p = mc.detect(G, seed)
                sets.append([{U.vs[i]["uid"] for i in c} for c in p if len(c) >= 10])
            for A in sets[0]:
                rows.append(dict(layer=layer, window=w, t=t,
                                 best_jaccard=max((len(A & B) / len(A | B) for B in sets[1]), default=0.0)))
d = pd.DataFrame(rows)
d.to_csv("results/baseline_same_window_seeds.csv", index=False)
print(d.groupby(["layer", "window"]).best_jaccard.agg(["mean", "median", "count"]).round(3))

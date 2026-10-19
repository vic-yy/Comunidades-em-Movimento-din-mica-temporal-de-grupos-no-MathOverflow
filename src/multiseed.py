"""5 sementes por camada/janela: Q, estabilidade (Jaccard t->t+1), teto de ruído (seed s vs s+1, mesma janela) e razão normalizada."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import mo_communities as mc

SEEDS = range(5)
rows = []
for layer in ("all", "answers", "comments"):
    df = mc.load_edges(layer=layer)
    for w in (365, 180):
        runs = {s: mc.run_layer(df, w, theta=0.2, seed=s) for s in SEEDS}
        for s in SEEDS:
            r, r2 = runs[s], runs[(s + 1) % 5]
            bm = mc.best_match(r)
            ceil = []
            for t, A_ in enumerate(r["comms"]):
                for a, A in A_.items():
                    ceil.append(max((len(A & B) / len(A | B) for B in r2["comms"][t].values()), default=0.0))
            lin = mc.lineages(r, 0.2)
            rows.append(dict(layer=layer, window=w, seed=s,
                             Q=np.mean([g["Q"] for g in r["graphs"]]),
                             n_comms=r["metrics"].groupby("t").size().mean(),
                             jaccard_next=bm.best_jaccard.mean(), ceiling=np.mean(ceil),
                             normalized=bm.best_jaccard.mean() / np.mean(ceil),
                             conductance=r["metrics"].conductance.mean(),
                             pct_lineages_surviving=(1 - lin.observed).mean(),
                             median_lineage=lin.duration.median()))
        print(layer, w, flush=True)
d = pd.DataFrame(rows); d.to_csv("results/multiseed_runs.csv", index=False)
g = d.groupby(["layer", "window"]).agg(["mean", "std"]).drop(columns="seed")
g.round(3).to_csv("results/multiseed_summary.csv"); print(g.round(3).to_string())

"""Contrafactual de saída de especialistas.

Para cada t: remove de G_{t+1} (a) os top-5% PageRank de t, (b) 5% aleatórios dos ativos de t (20 reps),
re-roda Leiden e mede estabilidade das comunidades de t (restritas aos nós remanescentes) vs t+1, e Q de t+1."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import mo_communities as mc

rng = np.random.default_rng(0)
W, SEED, REPS = 180, 0, 20

def stability(prev, G, seed, removed):
    U, p = mc.detect(G, seed)
    curr = [{U.vs[i]["uid"] for i in c} for c in p if len(c) >= 10]
    js = []
    for A in prev.values():
        A = A - removed
        if len(A) < 5: continue
        js.append(max((len(A & B) / len(A | B) for B in curr), default=0.0))
    return np.mean(js), U.modularity(p.membership, weights="weight")

rows = []
for layer in ("all", "answers", "comments"):
    df = mc.load_edges(layer=layer)
    r = mc.run_layer(df, W, seed=SEED)
    for t in range(len(r["wins"]) - 1):
        c = r["graphs"][t]["cent"]; k = max(1, int(len(c) * 0.05))
        experts = set(c.nlargest(k, "pagerank").uid); active = list(c.uid)
        lo, hi = r["wins"][t + 1]; G2 = mc.build_graph(df, lo, hi)
        base_j, base_q = stability({i: A - experts for i, A in r["comms"][t].items()}, G2, SEED, set())
        keep = [v.index for v in G2.vs if v["uid"] not in experts]
        Ge = G2.subgraph(keep)
        ex_j, ex_q = stability(r["comms"][t], Ge, SEED, experts)
        rj, rq = [], []
        for _ in range(REPS):
            rem = set(rng.choice(active, size=k, replace=False))
            Gr = G2.subgraph([v.index for v in G2.vs if v["uid"] not in rem])
            a, b = stability(r["comms"][t], Gr, SEED, rem); rj.append(a); rq.append(b)
        rows.append(dict(layer=layer, t=t, k=k, base_j=base_j, base_q=base_q, expert_j=ex_j, expert_q=ex_q,
                         rand_j=np.mean(rj), rand_q=np.mean(rq), rand_j_sd=np.std(rj), rand_q_sd=np.std(rq)))
    print(layer, flush=True)
d = pd.DataFrame(rows); d.to_csv("results/counterfactual.csv", index=False)
d["dj_expert"] = d.expert_j - d.base_j; d["dj_rand"] = d.rand_j - d.base_j
d["dq_expert"] = d.expert_q - d.base_q; d["dq_rand"] = d.rand_q - d.base_q
from scipy import stats
for layer, g in d.groupby("layer"):
    print(layer, "n=", len(g),
          "dJ expert %.3f rand %.3f (Wilcoxon p=%.4f)" % (g.dj_expert.mean(), g.dj_rand.mean(), stats.wilcoxon(g.dj_expert, g.dj_rand).pvalue),
          "| dQ expert %.3f rand %.3f (p=%.4f)" % (g.dq_expert.mean(), g.dq_rand.mean(), stats.wilcoxon(g.dq_expert, g.dq_rand).pvalue))

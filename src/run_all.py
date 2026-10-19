"""Executa todas as configurações, gera tabelas (results/*.csv) e figuras (results/*.png|html)."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
import mo_communities as mc

OUT = "results"
os.makedirs(OUT, exist_ok=True)
THETA = 0.2
CONFIGS = [  # (layer, janela em dias, gamma, theta)
    ("all", 365, 1.0, THETA), ("all", 180, 1.0, THETA),
    ("answers", 365, 1.0, THETA), ("answers", 180, 1.0, THETA),
    ("comments", 365, 1.0, THETA), ("comments", 180, 1.0, THETA),
    ("all", 180, 1.0, 0.1),   # sensibilidade ao limiar de Jaccard
    ("all", 180, 2.0, THETA),  # sensibilidade à resolução
]
cache = {}


def get(layer, w, gamma, theta):
    key = (layer, w, gamma)
    if key not in cache:
        df = mc.load_edges(layer=layer)
        cache[key] = mc.run_layer(df, w, theta=theta, gamma=gamma)
    return cache[key]


rows, comm_tables = [], {}
for layer, w, gamma, theta in CONFIGS:
    name = f"{layer}_w{w}_g{gamma}_th{theta}"
    print("==", name, flush=True)
    res = get(layer, w, gamma, theta)
    # eventos com o theta da configuração (o cache guarda eventos do primeiro theta usado; recomputa)
    ev, links, births = [], [], []
    for t in range(len(res["wins"]) - 1):
        lk, e, b = mc.jaccard_events(res["comms"][t], res["comms"][t + 1], theta)
        links += [dict(t=t, a=a, b=bb, jaccard=j) for a, bb, j in lk]
        ev += [dict(t=t, cid=a, event=x) for a, x in e]
        births += [dict(t=t + 1, cid=bb) for bb in b]
    r = dict(res, events=pd.DataFrame(ev), links=pd.DataFrame(links), births=pd.DataFrame(births))
    bm = mc.best_match(r)
    tv = mc.turnover(r)
    ex = mc.expert_features(r)
    m = r["metrics"]
    tab = (m.merge(bm, on=["t", "cid"], how="left")
            .merge(r["events"], on=["t", "cid"], how="left")
            .merge(ex.drop(columns="size"), on=["t", "cid"], how="left"))
    tab["config"] = name
    comm_tables[name] = tab
    tab.to_csv(f"{OUT}/communities_{name}.csv", index=False)
    lin = mc.lineages(r, theta)
    lin.to_csv(f"{OUT}/lineages_{name}.csv", index=False)
    evc = r["events"].event.value_counts()
    rows.append(dict(
        config=name, layer=layer, window=w, gamma=gamma, theta=theta, n_windows=len(r["wins"]),
        mean_nodes=np.mean([g["n"] for g in r["graphs"]]),
        mean_Q=np.mean([g["Q"] for g in r["graphs"]]),
        mean_comms=m.groupby("t").size().mean(), mean_size=m["size"].mean(),
        mean_density=m.density.mean(), mean_conductance=m.conductance.mean(),
        mean_best_jaccard=bm.best_jaccard.mean(),
        mean_left=tv["left"].mean() if len(tv) else np.nan,
        mean_new=tv["new"].mean() if len(tv) else np.nan,
        n_survive=int(evc.get("survive", 0)), n_merge=int(evc.get("merge", 0)),
        n_split=int(evc.get("split", 0)), n_death=int(evc.get("death", 0)), n_birth=len(r["births"]),
        n_lineages=len(lin), median_lineage_len=lin.duration.median(),
    ))
    cache[("res", name)] = r

summ = pd.DataFrame(rows)
summ.to_csv(f"{OUT}/summary_configs.csv", index=False)
print(summ.round(3).to_string())

# ---------------- RQ1: estabilidade vs turnover (rede completa) ----------------
# ---------------- RQ2: saída de especialistas ----------------
rq2 = []
for name, tab in comm_tables.items():
    d = tab.dropna(subset=["frac_experts_left"]).copy()
    d["unstable"] = d.event.isin(["split", "death", "merge"]).astype(int)
    if len(d) < 15:
        continue
    rho, p = stats.spearmanr(d.frac_experts_left, d.best_jaccard)
    rho_b, p_b = stats.spearmanr(d.bridge_share, d.best_jaccard)
    X = pd.DataFrame({"log_size": np.log(d["size"]), "experts_left": d.frac_experts_left,
                      "bridge_share": d.bridge_share})
    X = sm.add_constant(((X - X.mean()) / X.std()).fillna(0.0), has_constant="add")
    ols = sm.OLS(d.best_jaccard.values, X).fit()
    row = dict(config=name, n=len(d), spearman_expertsleft_vs_jaccard=rho, p=p,
               spearman_bridge_vs_jaccard=rho_b, p_bridge=p_b,
               ols_b_experts_left=ols.params["experts_left"], ols_p_experts_left=ols.pvalues["experts_left"],
               ols_b_bridge=ols.params["bridge_share"], ols_p_bridge=ols.pvalues["bridge_share"],
               ols_b_logsize=ols.params["log_size"], ols_p_logsize=ols.pvalues["log_size"], r2=ols.rsquared)
    if d.unstable.sum() >= 5 and (1 - d.unstable).sum() >= 5:
        try:
            lg = sm.Logit(d.unstable.values, X).fit(disp=0)
            row.update(logit_b_experts_left=lg.params["experts_left"], logit_p_experts_left=lg.pvalues["experts_left"],
                       logit_b_bridge=lg.params["bridge_share"], logit_p_bridge=lg.pvalues["bridge_share"])
        except Exception as e:  # separação perfeita etc.
            row["logit_error"] = str(e)[:60]
    rq2.append(row)
pd.DataFrame(rq2).to_csv(f"{OUT}/rq2_experts.csv", index=False)
print(pd.DataFrame(rq2).round(3).T.to_string())

# ---------------- RQ3: respostas vs comentários ----------------
rq3 = []
for w in (365, 180):
    a = comm_tables[f"answers_w{w}_g1.0_th{THETA}"]
    c = comm_tables[f"comments_w{w}_g1.0_th{THETA}"]
    for col in ("density", "conductance", "best_jaccard", "size"):
        x, y = a[col].dropna(), c[col].dropna()
        u, p = stats.mannwhitneyu(x, y)
        rq3.append(dict(window=w, metric=col, answers_mean=x.mean(), comments_mean=y.mean(),
                        answers_median=x.median(), comments_median=y.median(), mannwhitney_p=p))
pd.DataFrame(rq3).to_csv(f"{OUT}/rq3_layers.csv", index=False)
print(pd.DataFrame(rq3).round(4).to_string())

# ---------------- Figuras ----------------
colors = {"all": "#2a6fdb", "answers": "#d95f02", "comments": "#1b9e77"}

for w in (365, 180):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    for layer in ("all", "answers", "comments"):
        name = f"{layer}_w{w}_g1.0_th{THETA}"
        r = cache[("res", name)]
        ax[0].plot([g["Q"] for g in r["graphs"]], marker="o", label=layer, color=colors[layer])
        tab = comm_tables[name]
        ax[1].plot(tab.groupby("t").best_jaccard.mean(), marker="o", label=layer, color=colors[layer])
        lin = pd.read_csv(f"{OUT}/lineages_{name}.csv")
        km = mc.kaplan_meier(lin.duration, lin.observed)
        ax[2].step(km.t, km.S, where="post", label=layer, color=colors[layer])
    ax[0].set(title=f"Modularidade Q por janela ({w} d)", xlabel="janela t", ylabel="Q")
    ax[1].set(title="Estabilidade: melhor Jaccard com t+1", xlabel="janela t", ylabel="Jaccard")
    ax[2].set(title="Sobrevivência das linhagens (Kaplan-Meier)", xlabel="janelas", ylabel="S(t)", ylim=(0, 1.02))
    for a_ in ax:
        a_.legend(); a_.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(f"{OUT}/fig_layers_w{w}.png", dpi=150); plt.close()

# eventos por camada/janela
fig, ax = plt.subplots(figsize=(8, 4))
ev_df = summ[summ.config.str.contains("g1.0_th0.2")].set_index("config")[["n_survive", "n_merge", "n_split", "n_death", "n_birth"]]
ev_df = ev_df.div(ev_df.sum(axis=1), axis=0)
ev_df.plot.bar(stacked=True, ax=ax); ax.set_ylabel("fração de eventos"); plt.xticks(rotation=30, ha="right")
plt.tight_layout(); plt.savefig(f"{OUT}/fig_events.png", dpi=150); plt.close()

# especialistas: saída vs estabilidade
tab = comm_tables[f"all_w180_g1.0_th{THETA}"].dropna(subset=["frac_experts_left"])
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
ax[0].scatter(tab.frac_experts_left, tab.best_jaccard, s=tab["size"] / 5, alpha=.5)
ax[0].set(xlabel="fração de especialistas (top 5% PageRank) que saíram", ylabel="melhor Jaccard em t+1",
          title="Saída de especialistas e estabilidade (all, 180 d)")
ax[1].scatter(tab.bridge_share, tab.best_jaccard, s=tab["size"] / 5, alpha=.5, color="#d95f02")
ax[1].set(xlabel="fração de membros no top 5% betweenness", ylabel="melhor Jaccard em t+1", title="Papel de ponte")
plt.tight_layout(); plt.savefig(f"{OUT}/fig_experts.png", dpi=150); plt.close()

# Sankey/alluvial (plotly, HTML)
import plotly.graph_objects as go
for w in (365, 180):
    r = cache[("res", f"all_w{w}_g1.0_th0.2")]
    ids, labels, src, tgt, val = {}, [], [], [], []
    def node(t, c):
        if (t, c) not in ids:
            ids[(t, c)] = len(labels)
            labels.append(f"t{t}·c{c} (n={len(r['comms'][t][c])})")
        return ids[(t, c)]
    for t in range(len(r["wins"]) - 1):
        for a_, b_ in [(x.a, x.b) for x in r["links"][r["links"].t == t].itertuples()]:
            src.append(node(t, a_)); tgt.append(node(t + 1, b_)); val.append(len(r["comms"][t][a_] & r["comms"][t + 1][b_]))
    # flui também para comunidades grandes sem Jaccard>=theta (sobreposição baixa): liga top-overlap
    fig = go.Figure(go.Sankey(node=dict(label=labels, pad=8, thickness=10), link=dict(source=src, target=tgt, value=val)))
    fig.update_layout(title=f"Linhagem de comunidades, rede completa, janelas de {w} d (links: Jaccard≥{THETA}; largura = nós em comum)")
    fig.write_html(f"{OUT}/sankey_all_w{w}.html")

json.dump({"configs": len(CONFIGS)}, open(f"{OUT}/done.json", "w"))
print("OK")

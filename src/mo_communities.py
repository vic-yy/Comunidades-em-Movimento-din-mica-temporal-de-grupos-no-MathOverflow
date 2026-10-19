"""Pipeline: dinâmica temporal de comunidades no sx-mathoverflow.

Etapas: janelas deslizantes -> Leiden por janela -> rastreio por Jaccard
-> métricas topológicas -> centralidade e saída de especialistas.
"""
import numpy as np
import pandas as pd
import igraph as ig
import leidenalg as la

DAY = 86400
LAYERS = {
    "answers": ["a2q"],
    "comments": ["c2q", "c2a"],
    "all": ["a2q", "c2q", "c2a"],
}


def load_edges(data_dir="data", layer="all"):
    parts = [pd.read_csv(f"{data_dir}/{k}.txt.gz", sep=" ", names=["src", "dst", "ts"]) for k in LAYERS[layer]]
    df = pd.concat(parts, ignore_index=True)
    return df.sort_values("ts").reset_index(drop=True)


def make_windows(df, width_days, overlap=0.5):
    t0, t1 = df.ts.min(), df.ts.max()
    w, step = width_days * DAY, int(width_days * DAY * (1 - overlap))
    out, s = [], t0
    while s + w <= t1 + step // 2:  # mantém a última janela parcial se cobrir >= metade
        out.append((s, min(s + w, t1 + 1)))
        s += step
    return out


def build_graph(df, lo, hi):
    """Grafo dirigido ponderado (nº de interações u->v) da janela [lo,hi). Remove laços."""
    d = df[(df.ts >= lo) & (df.ts < hi) & (df.src != df.dst)]
    g = d.groupby(["src", "dst"]).size().reset_index(name="w")
    ids = pd.unique(np.concatenate([g.src.values, g.dst.values]))
    idx = {u: i for i, u in enumerate(ids)}
    G = ig.Graph(n=len(ids), edges=[(idx[a], idx[b]) for a, b in zip(g.src, g.dst)], directed=True)
    G.es["weight"] = g.w.tolist()
    G.vs["uid"] = ids.tolist()
    return G


def detect(G, seed=0, gamma=1.0):
    """Leiden (modularidade; gamma=1 é a modularidade clássica) sobre o grafo não-dirigido, pesos somados."""
    U = G.as_undirected(mode="collapse", combine_edges="sum")
    part = la.find_partition(U, la.RBConfigurationVertexPartition, weights="weight",
                             resolution_parameter=gamma, seed=seed)
    part.modularity_q = U.modularity(part.membership, weights="weight")
    return U, part


def community_metrics(U, part, min_size):
    """Densidade interna, condutância por comunidade (grafo não-dirigido ponderado)."""
    deg = np.array(U.strength(weights="weight"), dtype=float)
    total = deg.sum()
    memb = np.array(part.membership)
    rows = []
    for c, nodes in enumerate(part):
        n = len(nodes)
        if n < min_size:
            continue
        sub = U.subgraph(nodes)
        dens = sub.density() if n > 1 else 0.0
        vol = deg[nodes].sum()
        internal = 2 * sum(sub.es["weight"]) if sub.ecount() else 0.0
        cut = vol - internal
        cond = cut / min(vol, total - vol) if 0 < min(vol, total - vol) else 0.0
        rows.append(dict(cid=c, size=n, density=dens, conductance=cond))
    return pd.DataFrame(rows)


def jaccard_events(prev, curr, theta=0.2):
    """prev/curr: dict cid -> set(uid). Retorna (links, eventos).

    Link A->B se Jaccard >= theta. merge: >=2 em t apontam p/ mesma B;
    split: A aponta p/ >=2 em t+1; death: A sem link; birth: B sem link.
    """
    links = []
    for a, A in prev.items():
        for b, B in curr.items():
            inter = len(A & B)
            if inter:
                j = inter / len(A | B)
                if j >= theta:
                    links.append((a, b, j))
    out_deg, in_deg = {}, {}
    for a, b, _ in links:
        out_deg[a] = out_deg.get(a, 0) + 1
        in_deg[b] = in_deg.get(b, 0) + 1
    ev = []
    for a in prev:
        k = out_deg.get(a, 0)
        ev.append((a, "death" if k == 0 else "split" if k > 1 else
                   "merge" if any(in_deg[b] > 1 for x, b, _ in links if x == a) else "survive"))
    births = [b for b in curr if in_deg.get(b, 0) == 0]
    return links, ev, births


def run_layer(df, width_days, min_size=10, theta=0.2, seed=0, gamma=1.0):
    wins = make_windows(df, width_days)
    comms, mets, graphs = [], [], []
    for t, (lo, hi) in enumerate(wins):
        G = build_graph(df, lo, hi)
        U, part = detect(G, seed, gamma)
        m = community_metrics(U, part, min_size)
        m["t"] = t
        sets = {int(r.cid): {U.vs[i]["uid"] for i in part[int(r.cid)]} for r in m.itertuples()}
        comms.append(sets)
        mets.append(m)
        pr = G.pagerank(weights="weight", directed=True)
        bt = U.betweenness(weights=None, cutoff=None) if U.vcount() <= 6000 else \
            U.betweenness(weights=None, cutoff=4)
        act = dict(zip(G.vs["uid"], G.strength(mode="all", weights="weight")))
        cent = pd.DataFrame({"uid": G.vs["uid"], "pagerank": pr, "betweenness": bt})
        cent["comm"] = part.membership
        graphs.append(dict(win=(lo, hi), n=G.vcount(), m=G.ecount(), Q=part.modularity_q,
                           cent=cent, act=act))
    metrics = pd.concat(mets, ignore_index=True)
    events, links, births = [], [], []
    for t in range(len(wins) - 1):
        lk, ev, bi = jaccard_events(comms[t], comms[t + 1], theta)
        links += [dict(t=t, a=a, b=b, jaccard=j) for a, b, j in lk]
        events += [dict(t=t, cid=a, event=e) for a, e in ev]
        births += [dict(t=t + 1, cid=b) for b in bi]
    return dict(wins=wins, comms=comms, metrics=metrics, graphs=graphs,
                events=pd.DataFrame(events), links=pd.DataFrame(links), births=pd.DataFrame(births))


def turnover(res):
    """Para cada link A(t)->B(t+1): fração de A que saiu e de B que é nova."""
    rows = []
    for r in res["links"].itertuples():
        A, B = res["comms"][r.t][r.a], res["comms"][r.t + 1][r.b]
        rows.append(dict(t=r.t, a=r.a, b=r.b, jaccard=r.jaccard,
                         left=1 - len(A & B) / len(A), new=1 - len(A & B) / len(B)))
    return pd.DataFrame(rows)


def expert_features(res, top_frac=0.05, drop=0.5):
    """Por comunidade (t): fração de membros 'especialistas' que saíram em t+1, centralidade de ponte.

    Especialista = top `top_frac` por PageRank na janela t. 'Saída' = ausente em t+1 ou
    com atividade (força) caída >= `drop`. Como janelas se sobrepõem em 50%, a atividade
    é comparada com a metade NÃO sobreposta de t+1 (atividade total de t+1 vs t).
    """
    rows = []
    for t in range(len(res["wins"]) - 1):
        g, g2 = res["graphs"][t], res["graphs"][t + 1]
        c = g["cent"]
        k = max(1, int(len(c) * top_frac))
        top = set(c.nlargest(k, "pagerank").uid)
        top_bt = set(c.nlargest(k, "betweenness").uid)
        left = {u for u in top if g2["act"].get(u, 0) < (1 - drop) * g["act"][u]}
        for cid, nodes in res["comms"][t].items():
            n_top = len(nodes & top)
            rows.append(dict(
                t=t, cid=cid, size=len(nodes),
                n_experts=n_top, frac_experts=n_top / len(nodes),
                n_experts_left=len(nodes & left),
                frac_experts_left=(len(nodes & left) / n_top) if n_top else np.nan,
                any_expert_left=int(len(nodes & left) > 0),
                n_bridge=len(nodes & top_bt),
                bridge_share=len(nodes & top_bt) / len(nodes),
            ))
    return pd.DataFrame(rows)


def best_match(res):
    """Para cada comunidade em t: melhor Jaccard com qualquer comunidade em t+1 (0 se nenhuma)."""
    rows = []
    for t in range(len(res["wins"]) - 1):
        for a, A in res["comms"][t].items():
            best, bb = 0.0, None
            for b, B in res["comms"][t + 1].items():
                i = len(A & B)
                if i:
                    j = i / len(A | B)
                    if j > best:
                        best, bb = j, b
            rows.append(dict(t=t, cid=a, best_jaccard=best, best_b=bb))
    return pd.DataFrame(rows)


def lineages(res, theta):
    """Linhagens: segue o melhor link (Jaccard>=theta) de cada comunidade.

    Retorna DataFrame (duration em janelas, observed=1 se a linhagem morreu antes da última janela).
    Início de linhagem = comunidade sem link de entrada (inclui t=0)."""
    bm = best_match(res).set_index(["t", "cid"])
    last = len(res["wins"]) - 1
    has_in = {(r.t + 1, r.b) for r in res["links"].itertuples()}
    rows = []
    for t in range(last + 1):
        for cid in res["comms"][t]:
            if (t, cid) in has_in:
                continue
            tt, c, d = t, cid, 1
            while tt < last:
                r = bm.loc[(tt, c)]
                if r.best_jaccard < theta:
                    break
                tt, c, d = tt + 1, int(r.best_b), d + 1
            rows.append(dict(start=t, duration=d, observed=int(tt < last)))
    return pd.DataFrame(rows)


def kaplan_meier(dur, obs):
    dur, obs = np.asarray(dur), np.asarray(obs)
    ts = np.unique(dur)
    S, out = 1.0, [(0, 1.0)]
    for t in ts:
        at_risk = (dur >= t).sum()
        d = ((dur == t) & (obs == 1)).sum()
        S *= 1 - d / at_risk
        out.append((t, S))
    return pd.DataFrame(out, columns=["t", "S"])

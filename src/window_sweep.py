"""Teste do tamanho da janela (15 a 365 d): taxa de produção, persistência de nós/arestas e estabilidade normalizada. Saída: results/window_sweep.csv."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import sys; sys.path.insert(0, "src")
import numpy as np, pandas as pd
from mo_communities import *
DAYS=86400
# taxa de produção
a=load_edges("data","answers"); c=load_edges("data","comments")
span=(a.ts.max()-a.ts.min())/DAYS
print(f"span {span:.0f} d; respostas {len(a)} ({len(a)/span:.1f}/d), perguntas c/ resposta {a.dst.nunique()} ({a.dst.nunique()/span:.1f}/d), comentarios {len(c)} ({len(c)/span:.1f}/d)")
a["y"]=pd.to_datetime(a.ts,unit="s").dt.year
print(a.groupby("y").size().to_string())
df=load_edges("data","all")
rows=[]
for w in [15,30,60,90,180,365]:
    wins=make_windows(df,w)
    Gs=[build_graph(df,lo,hi) for lo,hi in wins]
    nodes=[set(G.vs["uid"]) for G in Gs]
    edges=[set(zip(*[ [G.vs[e.source]["uid"] for e in G.es], [G.vs[e.target]["uid"] for e in G.es] ])) for G in Gs]
    nj=np.mean([len(nodes[i]&nodes[i+1])/len(nodes[i]|nodes[i+1]) for i in range(len(wins)-1)])
    ej=np.mean([len(edges[i]&edges[i+1])/len(edges[i]|edges[i+1]) for i in range(len(wins)-1)])
    # ceiling vs t->t+1 (min_size ajustado)
    ms=10
    def comms(seed):
        out=[]
        for G in Gs:
            U,p=detect(G,seed); m=community_metrics(U,p,ms)
            out.append({int(r.cid):{U.vs[i]["uid"] for i in p[int(r.cid)]} for r in m.itertuples()})
        return out
    c0,c1=comms(0),comms(1)
    def bj(P,Q):
        v=[]
        for A in P.values():
            v.append(max([len(A&B)/len(A|B) for B in Q.values()],default=0))
        return np.mean(v) if v else np.nan
    cross=np.nanmean([bj(c0[i],c0[i+1]) for i in range(len(wins)-1)])
    ceil=np.nanmean([bj(c0[i],c1[i]) for i in range(len(wins))])
    nev=np.mean([len(G.vs) for G in Gs]); 
    rows.append(dict(w=w,n_win=len(wins),mean_nodes=nev,mean_edges=np.mean([G.ecount() for G in Gs]),
        mean_comms=np.mean([len(x) for x in c0]),node_jacc=nj,edge_jacc=ej,best_j=cross,ceiling=ceil,norm=cross/ceil))
    print(rows[-1],flush=True)
pd.DataFrame(rows).to_csv("results/window_sweep.csv",index=False)

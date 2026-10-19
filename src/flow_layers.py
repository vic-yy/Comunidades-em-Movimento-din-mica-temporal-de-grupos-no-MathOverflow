"""Fluxo de usuários entre comunidades e estabilidade por camada (60/90/180 d). Saída: results/flow_and_window_layers.csv."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
from mo_communities import *
df=load_edges("data","all")
ids=pd.unique(np.concatenate([df.src,df.dst]))
print("IDs: n=%d min=%d max=%d contiguos=%s"%(len(ids),ids.min(),ids.max(),len(ids)==ids.max()-ids.min()+1))
# fluxo de usuarios + sweep por camada
out=[]
for layer in ["all","answers","comments"]:
  d=load_edges("data",layer)
  for w in [60,90,180]:
    res=run_layer(d,w,seed=0); r1=run_layer(d,w,seed=1)
    comms=res["comms"]; T=len(comms)
    bm=best_match(res)
    stay=move=lost=0; tot=0
    for t in range(T-1):
        nxt=comms[t+1]; allnext=set().union(*nxt.values()) if nxt else set()
        for a,A in comms[t].items():
            b=bm[(bm.t==t)&(bm.cid==a)].best_b.iloc[0]
            B=nxt.get(int(b),set()) if b==b and b is not None else set()
            s=len(A&B); m=len((A&allnext)-B); 
            stay+=s; move+=m; lost+=len(A)-s-m; tot+=len(A)
    # ruido
    def bj(P,Q): 
        v=[max([len(A&B)/len(A|B) for B in Q.values()],default=0) for A in P.values()]; return np.mean(v) if v else np.nan
    cross=np.nanmean([bj(comms[i],comms[i+1]) for i in range(T-1)])
    ceil=np.nanmean([bj(comms[i],r1["comms"][i]) for i in range(T)])
    row=dict(layer=layer,w=w,n_win=T,stay=stay/tot,move_other_comm=move/tot,leave_or_small=lost/tot,best_j=cross,ceiling=ceil,norm=cross/ceil)
    print(row,flush=True); out.append(row)
pd.DataFrame(out).to_csv("results/flow_and_window_layers.csv",index=False)

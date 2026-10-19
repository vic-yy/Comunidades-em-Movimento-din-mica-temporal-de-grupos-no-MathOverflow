"""Validação temática: NMI e pureza das comunidades contra a área principal do usuário, consistência de tema nas linhagens e área dos usuários que mudam de comunidade. Saída: results/topic_validation.csv. Requer dump_mo/x/{Users,Posts}.xml."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import re, collections, numpy as np, pandas as pd
import xml.etree.ElementTree as ET
from sklearn.metrics import normalized_mutual_info_score as nmi
from mo_communities import *
D="dump_mo/x/"; rng=np.random.default_rng(0)
qarea={}; posts=[]
for _,e in ET.iterparse(D+"Posts.xml"):
    if e.tag=="row":
        pid=int(e.get("Id")); t=int(e.get("PostTypeId")); u=e.get("OwnerUserId")
        if t==1: qarea[pid]=[x.split(".")[0] for x in (e.get("Tags") or "").split("|") if "." in x]
        if u: posts.append((pid,t,int(u),int(e.get("ParentId")) if e.get("ParentId") else None))
    e.clear()
prof=collections.defaultdict(collections.Counter)
for pid,t,u,par in posts:
    for a in qarea.get(pid if t==1 else par,[]): prof[u][a]+=1
lab={u:c.most_common(1)[0][0] for u,c in prof.items()}
print("areas:",len(set(lab.values())),"; areas mais comuns:",collections.Counter(lab.values()).most_common(5))
df=load_edges("data","all")
out=[]
for w in [90,180]:
    res=run_layer(df,w,seed=0); comms=res["comms"]
    nm,nm0,pur,pur0=[],[],[],[]
    for cs in comms:
        us=[(u,cid) for cid,n in cs.items() for u in n if u in lab]
        if len(us)<50: continue
        y=[lab[u] for u,_ in us]; c=[cid for _,cid in us]
        nm.append(nmi(c,y)); nm0.append(np.mean([nmi(c,rng.permutation(y)) for _ in range(20)]))
        # pureza: share da area dominante em cada comunidade, ponderado
        d=collections.defaultdict(collections.Counter)
        for (u,cid),a in zip(us,y): d[cid][a]+=1
        pur.append(sum(max(v.values()) for v in d.values())/len(us))
        pur0.append(max(collections.Counter(y).values())/len(us))
    # consistencia de tema ao longo de links; baseline: pares aleatorios de comunidades
    def top(cs):
        r={}
        for cid,n in cs.items():
            c=collections.Counter(lab[u] for u in n if u in lab); r[cid]=c.most_common(1)[0][0] if c else None
        return r
    tops=[top(cs) for cs in comms]
    same=[tops[r.t][r.a]==tops[r.t+1][r.b] for r in res["links"].itertuples()]
    rnd=[tops[t][a]==tops[t+1][b] for t in range(len(comms)-1) for a in tops[t] for b in tops[t+1]]
    # movers: usuarios que trocam de comunidade (nao-sucessora) -> mesma area dominante origem/destino?
    bm=best_match(res); mv_same=[]; 
    for t in range(len(comms)-1):
        dest={u:cid for cid,n in comms[t+1].items() for u in n}
        for a,A in comms[t].items():
            b=bm[(bm.t==t)&(bm.cid==a)].best_b.iloc[0]
            for u in A:
                cd=dest.get(u)
                if cd is not None and cd!=b and tops[t][a] and tops[t+1][cd]:
                    mv_same.append(tops[t][a]==tops[t+1][cd])
    row=dict(w=w,NMI=np.mean(nm),NMI_shuffled=np.mean(nm0),purity=np.mean(pur),purity_baseline=np.mean(pur0),
      link_same_area=np.mean(same),pair_random_same_area=np.mean(rnd),mover_same_area=np.mean(mv_same),n_movers=len(mv_same))
    print({k:(round(v,3) if isinstance(v,float) else v) for k,v in row.items()},flush=True); out.append(row)
pd.DataFrame(out).to_csv("results/topic_validation.csv",index=False)

"""Perfil de tags por usuário (dump do Stack Exchange) e pureza temática por comunidade (180 d, camada all). Saída: results/topic_purity_area.csv. Requer dump_mo/x/{Users,Posts}.xml (ver src/download_data.py)."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import sys, re, collections, numpy as np, pandas as pd
import xml.etree.ElementTree as ET
from mo_communities import *
import os
LEVEL=os.environ.get("LEVEL","area")
D="dump_mo/x/"
# usuarios do dump
users=set(); 
for _,e in ET.iterparse(D+"Users.xml"):
    if e.tag=="row": users.add(int(e.get("Id")))
    e.clear()
df=load_edges("data","all")
ids=set(pd.unique(np.concatenate([df.src,df.dst])).tolist())
print("usuarios SNAP:",len(ids)," presentes no dump:",len(ids&users), f"({len(ids&users)/len(ids):.1%})")
# tags por pergunta, e perfil por usuario (perguntas feitas + respondidas)
qtags={}; owner={}; posts=[]
for _,e in ET.iterparse(D+"Posts.xml"):
    if e.tag=="row":
        pid=int(e.get("Id")); t=int(e.get("PostTypeId")); uid=e.get("OwnerUserId")
        if t==1: qtags[pid]=[(x.split(".")[0] if LEVEL=="area" and "." in x else x) for x in (e.get("Tags") or "").split("|") if x]
        posts.append((pid,t,int(uid) if uid else None,int(e.get("ParentId")) if e.get("ParentId") else None))
    e.clear()
prof=collections.defaultdict(collections.Counter)
for pid,t,u,par in posts:
    if u is None: continue
    q=pid if t==1 else par
    for tg in qtags.get(q,[]): prof[u][tg]+=1
print("usuarios com perfil:",sum(1 for u in ids if u in prof))
# tag primaria (area MSC aproximada: primeira tag *-* ?) -> usa tag mais frequente como rotulo do usuario
def top_tags(c): return c
res=run_layer(df,180,seed=0)
rows=[]; rng=np.random.default_rng(0)
allp=[u for u in ids if u in prof]
def ent(counter):
    v=np.array(list(counter.values()),float); p=v/v.sum(); return -(p*np.log2(p)).sum()
def cos_pair(comm):
    us=[u for u in comm if u in prof]; 
    return us
def mean_cos(us,n=2000):
    if len(us)<5: return np.nan
    a=rng.choice(us,n); b=rng.choice(us,n); s=[]
    for x,y in zip(a,b):
        if x==y: continue
        cx,cy=prof[x],prof[y]; dot=sum(v*cy.get(k,0) for k,v in cx.items())
        nx=np.sqrt(sum(v*v for v in cx.values())); ny=np.sqrt(sum(v*v for v in cy.values()))
        s.append(dot/(nx*ny))
    return np.mean(s)
base=mean_cos(allp,4000); print("coseno medio entre usuarios aleatorios (baseline):",round(base,4))
for t,cs in enumerate(res["comms"]):
    for cid,nodes in cs.items():
        us=[u for u in nodes if u in prof]
        agg=collections.Counter()
        for u in us: agg.update(prof[u])
        top=agg.most_common(3)
        tot=sum(agg.values())
        rows.append(dict(t=t,cid=cid,size=len(nodes),n_prof=len(us),cos=mean_cos(us),
            top_tag=top[0][0] if top else None,top_share=top[0][1]/tot if tot else np.nan,
            top3=";".join(k for k,_ in top)))
R=pd.DataFrame(rows); R.to_csv(f"results/topic_purity_{LEVEL}.csv",index=False)
print(R[["cos","top_share"]].describe().round(3))
print("razao cos(comunidade)/baseline:",round(R.cos.mean()/base,2))
# coerencia do tema ao longo das linhagens: top_tag igual entre A e sucessor
L=res["links"]; same=[]
for r in L.itertuples():
    a=R[(R.t==r.t)&(R.cid==r.a)].top_tag.iloc[0]; b=R[(R.t==r.t+1)&(R.cid==r.b)].top_tag.iloc[0]
    same.append(a==b)
print("links A->B com mesma tag dominante:",np.mean(same) if same else None,"n=",len(same))

# Comunidades em Movimento: dinâmica temporal de grupos no MathOverflow

Estudamos como comunidades de usuários do MathOverflow se formam, mudam e desaparecem ao longo de sete anos. Dividimos a rede em janelas de tempo, detectamos grupos em cada janela e os acompanhamos entre janelas. Medimos a estabilidade, o papel dos usuários mais centrais e a relação com os assuntos de matemática.

Projeto da disciplina de Computação Social. Dados: [SNAP sx-mathoverflow](https://snap.stanford.edu/data/sx-mathoverflow.html) (24.818 usuários, 506.550 interações, 2009–2016) e, para os assuntos, o dump público do Stack Exchange.

## Estrutura
```
src/        código (pipeline, experimentos e validações)
results/    tabelas (.csv), figuras (.png) e diagramas Sankey (.html) gerados
docs/       proposta, relatório, guia didático e apresentação
data/       dados brutos (não versionados; ver data/README.md)
```

## Reprodução
```
pip install -r requirements.txt
python src/download_data.py            # arestas do SNAP em data/
python src/run_all.py                  # ~5 min; 8 configurações, RQ2/RQ3, figuras e Sankey
python src/baseline_seed.py            # controle de ruído do Leiden
python src/multiseed.py                # 5 sementes
python src/counterfactual.py           # remoção de especialistas vs. aleatório
python src/window_sweep.py             # teste do tamanho da janela
python src/flow_layers.py              # fluxo de usuários e janelas por camada

python src/download_data.py --dump     # opcional: dump com tags (~510 MB)
python src/topic_purity.py             # pureza temática por comunidade
python src/topic_validation.py         # NMI, consistência de tema e área dos que mudam de comunidade
```
Rode sempre a partir da raiz do repositório. `src/mo_communities.py` é o módulo central (janelas, Leiden via igraph/leidenalg, métricas, rastreio por Jaccard, linhagens, Kaplan-Meier, features de especialistas).

## Decisões de método (desvios da proposta)
- **Leiden** roda no grafo **não-dirigido** com pesos somados (laços removidos: 56.990 em c2q e 55.676 em c2a são autocomentários). PageRank usa o grafo dirigido.
- **CDlib não foi usado**: o pareamento de Jaccard é simples e foi implementado diretamente (evita dependência pesada). Se o grupo quiser manter CDlib no texto, ajustar a proposta.
- Comunidades com < 10 nós são ignoradas. Link A→B se Jaccard ≥ θ = 0,2 (sensibilidade: 0,1).
- Especialista = top 5% por PageRank na janela t; "saiu" = atividade em t+1 caiu ≥ 50% (ou ausente). Ponte = top 5% por betweenness (aproximada com cutoff=4 em janelas > 6000 nós).

## ⚠ Correção na proposta
Contagens reais por camada: a2q **107.581**, c2q **203.639**, c2a **195.330** (total 506.550 e 24.818 usuários conferem). A proposta lista 107.211 / 157.380 / 241.959, que está errado.

## Resultados (resumo; tabelas em results/)
**Controle de validade (importante):** duas execuções do Leiden na *mesma* janela já dão Jaccard médio de só 0,51 (all), 0,39 (answers), 0,55 (comments). Ou seja, o Jaccard bruto t→t+1 (0,19 / 0,13 / 0,20 em 180 d) deve ser lido relativo a esse teto: ≈ 0,36 / 0,34 / 0,36 do teto.

- **RQ1 (estabilidade):** baixa. Mediana da linhagem = 1 janela; só ~3% das linhagens sobrevivem até o fim (KM). Turnover entre comunidades ligadas: ~55% dos membros saem e ~57% são novos. Há um núcleo de poucas comunidades grandes (~350–680 nós) e muitas efêmeras. Q sobe com o tempo (0,29→0,53 em all; 0,33→0,65 em answers).
- **RQ2 (especialistas/pontes):** com θ=0,2 quase não há eventos merge/split (0–1); com θ=0,1 aparecem 31 merges e 22 splits — poder estatístico baixo para eventos discretos. Usando estabilidade contínua (Jaccard do melhor sucessor), controlando tamanho: maior fração de especialistas que saem → menor estabilidade (coef. OLS ≈ −0,01 padronizado, p<0,05 em 7 de 8 configs; negativo em todas) e maior chance de split/merge/morte (logit, p<0,05 em 3 de 8; borderline em mais uma). Maior presença de pontes (betweenness) → maior estabilidade (Spearman +0,27 a +0,49, exceto γ=2: +0,10), mas o efeito se enfraquece com controles (n.s. em algumas configs). Tamanho é o preditor dominante (R² ≈ 0,3–0,45). Associação, não causalidade.
- **RQ3 (respostas × comentários):** Jaccard bruto: comentários > respostas (0,20 vs 0,13); condutância: comentários mais alta (0,45 vs 0,37 → mais dispersas/menos separadas); Q: respostas > comentários. **Contrariando a hipótese**, comentários não são menos estáveis em termos brutos, e normalizando pelo teto de ruído as camadas ficam equivalentes (≈ 0,35 – 0,40). A rede de respostas é mais esparsa e fragmentada (mais comunidades pequenas: ~20 vs ~12 por janela), o que reduz o Jaccard de forma mecânica.

## Próximos passos executados (5 sementes + contrafactual)
Arquivos: `results/multiseed_*.csv`, `results/counterfactual.csv`, `results/fig_counterfactual.png` (scripts `src/multiseed.py`, `src/counterfactual.py`).

**5 sementes (média ± dp)** — estabilidade normalizada = Jaccard t→t+1 / teto de ruído:

| camada | janela | Q | Jaccard t→t+1 | teto | normalizada | % linhagens que chegam ao fim |
|---|---|---|---|---|---|---|
| all | 180 | 0,452±0,000 | 0,187±0,004 | 0,506 | 0,371±0,009 | 9,6% |
| all | 365 | 0,426±0,001 | 0,217±0,005 | 0,558 | 0,389±0,008 | 22,1% |
| answers | 180 | 0,560±0,000 | 0,128±0,003 | 0,383 | 0,334±0,011 | 5,7% |
| answers | 365 | 0,512±0,000 | 0,137±0,004 | 0,377 | 0,363±0,017 | 13,0% |
| comments | 180 | 0,456±0,000 | 0,192±0,003 | 0,536 | 0,359±0,005 | 9,2% |
| comments | 365 | 0,428±0,000 | 0,216±0,005 | 0,551 | 0,393±0,007 | 22,5% |

Refinamento da RQ3: a variação entre sementes é pequena, então as diferenças são reais. A diferença bruta (comentários mais estáveis) quase some após normalizar; sobra um efeito pequeno: respostas ligeiramente menos estáveis em 180 d (0,334 vs 0,359; ~2–3 dp), indistinguível em 365 d. (Nota: a fração de linhagens sobreviventes aqui, 6–23%, usa a definição "linhagem chega à última janela"; o "~3%" acima era a cauda da curva KM e foi substituído por esta.)

**Contrafactual (180 d, 24 transições por camada; remove de G(t+1) os top 5% PageRank de t; controle = 5% aleatório, 20 repetições)**

| camada | Δ Jaccard (especialistas) | Δ Jaccard (aleatório) | Δ Q (esp.) | Δ Q (aleat.) |
|---|---|---|---|---|
| all | −0,076 | +0,011 | +0,192 | +0,005 |
| answers | −0,019 | +0,001 | +0,109 | +0,009 |
| comments | −0,093 | +0,007 | +0,201 | +0,005 |

Wilcoxon pareado (especialistas vs aleatório) p<0,0001 em todas. Remover os especialistas **desestabiliza** a estrutura de comunidades (queda de Jaccard) muito mais que remover nós aleatórios, com efeito maior nos comentários do que nas respostas. A modularidade **sobe**: isso é esperado, pois hubs conectam comunidades e removê-los reduz arestas entre elas; Q não deve ser lido como "mais coesão". Isto é um experimento estrutural (reconstruir o grafo sem esses nós), não prova que a saída real de usuários cause as mudanças observadas.

## Limitações
- Janelas com 50% de sobreposição e comunidades em janelas consecutivas não são independentes; os p-valores são otimistas.
- Seeds: resumo principal usa semente 0; a tabela de 5 sementes confirma que o ruído entre sementes é pequeno.
- Resolução padrão (γ=1) gera poucas comunidades grandes; γ=2 gera ~38 por janela e quase nenhuma sobrevive.
- Rótulos de tópico vêm do dump do Stack Exchange (ver "Validação temática"), por usuário e não por post: as arestas do SNAP não guardam o ID do post. O rótulo é a área mais frequente do usuário em toda a sua história, inclusive depois da janela.

## Validação temática, janela e fluxo (pendências fechadas)
Arquivos: `results/topic_validation.csv`, `results/topic_purity_{area,tag}.csv`, `results/window_sweep.csv`, `results/flow_and_window_layers.csv`.

**Dados de tópico.** Os IDs do SNAP são os IDs originais de usuário do MathOverflow: 24.389 de 24.818 (98,3%) estão em `Users.xml` do dump (`mathoverflow.net.7z`, archive.org, extraído em `dump_mo/x/`; ~1,3 GB, pode ser apagado). O rótulo de cada usuário é a área mais frequente (prefixo da tag: ag, nt, co, pr, fa…; 32 áreas) entre as perguntas que fez ou respondeu. 23.609 usuários têm perfil. No MO cada área tem uma única tag com prefixo, então tag e área dão o mesmo resultado.

**As comunidades discutem o mesmo tema? Parcialmente** (camada `all`, semente 0):

| janela | NMI com área | NMI embaralhado | pureza | pureza base | link A→B mesma área | par aleatório mesma área |
|---|---|---|---|---|---|---|
| 90 d | 0,210 | 0,034 | 0,319 | 0,159 | 87% | 11% |
| 180 d | 0,214 | 0,018 | 0,322 | 0,153 | 88% | 10% |

- As comunidades concentram áreas bem acima do acaso (NMI ~10× o embaralhado, pureza ~2× a base), mas são longe de puras: a área dominante cobre ~1/3 dos membros. Há sinal temático, e ele não é a única coisa que as separa.
- A área dominante se mantém ao longo das linhagens (87–88% contra ~10% ao acaso): comunidades ligadas por Jaccard tratam do mesmo tema.
- **Fluxo:** usuários que mudam para outra comunidade que não a sucessora vão para uma comunidade com a mesma área dominante em só 10–15% dos casos (n = 33,7 mil a 49,6 mil), ou seja, no nível do acaso. A mobilidade não é guiada por tema.
- Ressalvas: uma semente; só a camada `all`; pureza e NMI não foram corrigidos para o número de comunidades.

**Janela.** Taxa: ~6,8 perguntas respondidas, 46 respostas e 170 comentários por dia; respostas/ano caem de 24,8 mil (2010) para 11,8 mil (2015), então a série não é estacionária. O Jaccard de arestas entre janelas consecutivas é 0,35–0,37 em todas as escalas (15 a 365 d), próximo do 0,33 de um grafo sem arestas recorrentes fora da sobreposição de 50%; o de nós é ~0,55. Estabilidade normalizada pelo teto de ruído (camada `all`): 0,28 (15 d), 0,32 (60 d), 0,34 (90 d), 0,37 (180 d), 0,39 (365 d). Por camada em 60/90/180 d: answers 0,29/0,31/0,34; comments 0,32/0,33/0,36. A ordem answers < comments vale em todas as janelas. Janelas maiores parecem mais estáveis em parte por construção. Recomendação: 180 d principal e 60–90 d como sensibilidade. Não testadas: outras sobreposições e RQ2 em 60/90 d.

**Fluxo de usuários** (camada `all`; destino dos membros de cada comunidade na janela seguinte): ficam na sucessora 31% / 32% / 35%, vão para outra comunidade 41% / 39% / 35%, saem ou ficam em comunidade com menos de 10 nós 29% (janelas de 60 / 90 / 180 d). Em `answers` só 25–27% ficam; em `comments`, 30–36%. Não calculado: fluxo entre pares de comunidades e controle de ruído do Leiden para o fluxo.

## Próximos passos sugeridos
Escrever o relatório de 5 páginas e os slides de 20 min a partir de `results/`.

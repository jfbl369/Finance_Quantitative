"""
Bitcoin Transaction Graph — Détection du Wash Trading
=====================================================
Techniques couvertes :
  1. Données synthétiques (3 patterns de wash trading injectés)
  2. Common-Input-Ownership Heuristic (CIOH) — clustering d'adresses
  3. Détection de cycles courts avec score de suspicion composite
  4. Vérification temporelle et similarité de montants sur les cycles
  5. Détection des peel chains (coin mixing / brouillage de piste)
  6. Score de suspicion agrégé par cluster
  7. Visualisation Plotly + évaluation précision/rappel/F1

Données :
  USE_REAL_API = False  → données synthétiques (fonctionne immédiatement)
  USE_REAL_API = True   → API Blockstream.info (gratuit, sans clé)

Dépendances :
  python3 -m pip install networkx plotly pandas numpy requests
"""

import numpy as np
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import time
import random
from collections import defaultdict, deque
from itertools import combinations
from typing import Dict, List, Tuple, Optional, Set
import warnings
warnings.filterwarnings("ignore")
random.seed(42)
np.random.seed(42)


# ===========================================================================
# 0. CONFIGURATION
# ===========================================================================

USE_REAL_API      = False   # True = Blockstream API, False = synthétique
SEED_ADDRESS      = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"

# Paramètres de détection
CYCLE_MAX_LENGTH  = 5       # Longueur max des cycles à analyser
TIME_WINDOW_SEC   = 86_400  # 24h — fenêtre temporelle pour cycles suspects
AMOUNT_TOLERANCE  = 0.05    # 5% — tolérance sur les montants dans un cycle
MIN_CYCLE_AMOUNT  = 0.001   # BTC minimum pour considérer un cycle (filtre dust)

BTC = 1e8  # 1 BTC = 1e8 satoshis


# ===========================================================================
# 1. DONNÉES SYNTHÉTIQUES
# ===========================================================================

def generate_synthetic_graph() -> Tuple[pd.DataFrame, List[Set[str]]]:
    """
    Génère un graphe de transactions Bitcoin synthétique avec :
      - 80 transactions légitimes entre 30 adresses normales
      - 3 patterns de wash trading injectés (camouflés parmi les données normales)

    Pattern 1 — 2-cycle direct      : wash_A1 ↔ wash_B1 (6 allers-retours)
    Pattern 2 — 3-cycle triangulaire: wash_A2 → wash_B2 → wash_C2 → wash_A2
    Pattern 3 — Fan-out/consolidation: wash_HUB → 4 spokes → wash_HUB

    Retourne :
      df            : DataFrame (tx_id, from_addr, to_addr, amount_btc, timestamp, is_wash)
      wash_clusters : ground truth — liste de sets d'adresses wash
    """
    N_ADDR = 30
    normal_addrs = [f"addr_{i:03d}" for i in range(N_ADDR)]
    base_time = 1_700_000_000  # ~novembre 2023 (UNIX timestamp)

    txs = []
    tx_id = 0

    # ── Transactions normales ────────────────────────────────────────────────
    for _ in range(80):
        src = random.choice(normal_addrs)
        dst = random.choice([a for a in normal_addrs if a != src])
        amount = round(max(0.0001, min(np.random.lognormal(-2, 1.5), 10.0)), 6)
        txs.append({
            "tx_id": f"tx_{tx_id:06d}", "from_addr": src, "to_addr": dst,
            "amount_btc": amount,
            "timestamp": base_time + random.randint(0, 30 * 86400),
            "is_wash": False,
        })
        tx_id += 1

    wash_clusters = []

    # ── Pattern 1 : 2-cycle direct (A ↔ B) ─────────────────────────────────
    # L'entité contrôle à la fois wash_A1 et wash_B1.
    # Elle fait des allers-retours pour simuler du volume.
    w_A1, w_B1 = "wash_A1", "wash_B1"
    wash_clusters.append({w_A1, w_B1})
    t = base_time + 5 * 86400
    amount = 0.5
    for i in range(6):
        fee = random.uniform(0.0001, 0.0003)
        txs += [
            {"tx_id": f"tx_{tx_id:06d}", "from_addr": w_A1, "to_addr": w_B1,
             "amount_btc": round(amount, 6), "timestamp": t + i * 7200,     "is_wash": True},
            {"tx_id": f"tx_{tx_id+1:06d}", "from_addr": w_B1, "to_addr": w_A1,
             "amount_btc": round(amount - fee, 6), "timestamp": t + i * 7200 + 3600, "is_wash": True},
        ]
        tx_id += 2
        amount -= fee

    # ── Pattern 2 : 3-cycle triangulaire (A → B → C → A) ───────────────────
    w_A2, w_B2, w_C2 = "wash_A2", "wash_B2", "wash_C2"
    wash_clusters.append({w_A2, w_B2, w_C2})
    t = base_time + 10 * 86400
    FEE = 0.0003
    for i in range(4):
        a1 = round(1.2 - FEE * 3 * i, 6)
        a2, a3 = round(a1 - FEE, 6), round(a1 - 2 * FEE, 6)
        txs += [
            {"tx_id": f"tx_{tx_id:06d}",   "from_addr": w_A2, "to_addr": w_B2,
             "amount_btc": a1, "timestamp": t + i * 86400,          "is_wash": True},
            {"tx_id": f"tx_{tx_id+1:06d}", "from_addr": w_B2, "to_addr": w_C2,
             "amount_btc": a2, "timestamp": t + i * 86400 + 1800,   "is_wash": True},
            {"tx_id": f"tx_{tx_id+2:06d}", "from_addr": w_C2, "to_addr": w_A2,
             "amount_btc": a3, "timestamp": t + i * 86400 + 3600,   "is_wash": True},
        ]
        tx_id += 3

    # ── Pattern 3 : Fan-out puis consolidation ──────────────────────────────
    w_HUB = "wash_HUB"
    spokes = [f"wash_SP{i}" for i in range(4)]
    wash_clusters.append({w_HUB} | set(spokes))
    t = base_time + 20 * 86400
    spoke_amt = 2.0 / len(spokes)
    for j, spoke in enumerate(spokes):
        txs += [
            {"tx_id": f"tx_{tx_id:06d}",   "from_addr": w_HUB,  "to_addr": spoke,
             "amount_btc": round(spoke_amt, 6),          "timestamp": t + j * 600,        "is_wash": True},
            {"tx_id": f"tx_{tx_id+1:06d}", "from_addr": spoke, "to_addr": w_HUB,
             "amount_btc": round(spoke_amt - 0.0002, 6), "timestamp": t + j * 600 + 3600, "is_wash": True},
        ]
        tx_id += 2

    # Quelques tx normales pour les adresses wash (pour les camoufler)
    for waddr in [w_A1, w_B1, w_A2, w_HUB]:
        for _ in range(3):
            txs.append({
                "tx_id": f"tx_{tx_id:06d}", "from_addr": waddr,
                "to_addr": random.choice(normal_addrs),
                "amount_btc": round(random.uniform(0.001, 0.1), 6),
                "timestamp": base_time + random.randint(0, 30 * 86400),
                "is_wash": False,
            })
            tx_id += 1

    df = pd.DataFrame(txs)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")

    n_wash = df["is_wash"].sum()
    print(f"Graphe synthétique : {len(df)} transactions, "
          f"{df[['from_addr','to_addr']].stack().nunique()} adresses uniques")
    print(f"Dont {n_wash} transactions wash trading ({n_wash/len(df)*100:.1f}%)")
    return df, wash_clusters


# ===========================================================================
# 2. API BLOCKSTREAM (optionnel)
# ===========================================================================

def fetch_address_txs(address: str, max_tx: int = 25) -> list:
    url = f"https://blockstream.info/api/address/{address}/txs"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()[:max_tx]
    except Exception as e:
        print(f"  API error ({address[:20]}...): {e}")
        return []

def parse_tx(tx: dict) -> list:
    """Extrait les flux (input_addr → output_addr, montant) d'une transaction."""
    edges, ts = [], tx.get("status", {}).get("block_time", int(time.time()))
    in_addrs = [(i.get("prevout", {}).get("scriptpubkey_address"),
                 i.get("prevout", {}).get("value", 0) / BTC)
                for i in tx.get("vin", [])
                if i.get("prevout", {}).get("scriptpubkey_address")]
    for out in tx.get("vout", []):
        addr = out.get("scriptpubkey_address")
        val  = out.get("value", 0) / BTC
        if addr and val > 0.00001:
            for in_addr, _ in in_addrs:
                if in_addr != addr:
                    edges.append({"tx_id": tx["txid"], "from_addr": in_addr,
                                  "to_addr": addr, "amount_btc": round(val, 8),
                                  "timestamp": ts, "is_wash": None})
    return edges

def fetch_graph_api(seed: str, max_hops: int = 2) -> pd.DataFrame:
    visited, queue, all_edges = set(), deque([(seed, 0)]), []
    while queue:
        addr, depth = queue.popleft()
        if addr in visited or depth > max_hops: continue
        visited.add(addr)
        print(f"  hop {depth}: {addr[:25]}...")
        for tx in fetch_address_txs(addr):
            edges = parse_tx(tx)
            all_edges.extend(edges)
            for e in edges:
                nb = e["to_addr"] if e["from_addr"] == addr else e["from_addr"]
                if nb not in visited:
                    queue.append((nb, depth + 1))
        time.sleep(0.12)
    if not all_edges:
        return pd.DataFrame()
    df = pd.DataFrame(all_edges).drop_duplicates("tx_id")
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    print(f"API → {len(df)} transactions, {len(visited)} adresses explorées")
    return df


# ===========================================================================
# 3. CONSTRUCTION DU GRAPHE
# ===========================================================================

def build_graph(df: pd.DataFrame) -> nx.DiGraph:
    """
    Nœuds = adresses Bitcoin
    Arêtes = flux BTC (from → to), pondérées par le total envoyé.
    Les arêtes parallèles (même paire, transactions différentes) sont agrégées.
    """
    agg = (df.groupby(["from_addr", "to_addr"])
             .agg(weight=("amount_btc", "sum"), n_tx=("tx_id", "count"),
                  first_tx=("timestamp", "min"), last_tx=("timestamp", "max"),
                  is_wash=("is_wash", "any"))
             .reset_index())

    G = nx.DiGraph()
    for _, r in agg.iterrows():
        G.add_edge(r["from_addr"], r["to_addr"],
                   weight=r["weight"], n_tx=int(r["n_tx"]),
                   first_tx=r["first_tx"], last_tx=r["last_tx"],
                   is_wash=bool(r["is_wash"]) if pd.notna(r["is_wash"]) else None)

    for n in G.nodes():
        G.nodes[n]["out_btc"] = sum(d["weight"] for _, _, d in G.out_edges(n, data=True))
        G.nodes[n]["in_btc"]  = sum(d["weight"] for _, _, d in G.in_edges(n,  data=True))
        G.nodes[n]["volume"]  = G.nodes[n]["out_btc"] + G.nodes[n]["in_btc"]

    print(f"\nGraphe : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    return G


# ===========================================================================
# 4. COMMON-INPUT-OWNERSHIP HEURISTIC (CIOH)
# ===========================================================================

class UnionFind:
    """Union-Find avec path compression pour le clustering d'adresses."""
    def __init__(self):
        self.parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str):
        px, py = self.find(x), self.find(y)
        if px != py:
            self.parent[px] = py

    def clusters(self) -> Dict[str, Set[str]]:
        result: Dict[str, Set[str]] = defaultdict(set)
        for node in self.parent:
            result[self.find(node)].add(node)
        return dict(result)


def apply_cioh(df: pd.DataFrame) -> Dict[str, str]:
    """
    Heuristique fondamentale de la blockchain analytics :
    Si plusieurs adresses sont inputs d'une même transaction, elles
    appartiennent au même portefeuille (même clé privée nécessaire).

    Limite connue : CoinJoin invalide cette heuristique.

    Retourne : {adresse → id_cluster}
    """
    uf = UnionFind()
    for _, inputs in df.groupby("tx_id")["from_addr"].apply(list).items():
        for a in inputs:
            uf.find(a)
        for a, b in combinations(inputs, 2):
            uf.union(a, b)
    for addr in df["to_addr"].unique():
        uf.find(addr)

    clusters = uf.clusters()
    addr_to_cluster = {
        member: f"C{i:04d}"
        for i, members in enumerate(clusters.values())
        for member in members
    }
    n_addr = len(addr_to_cluster)
    n_clus = len(clusters)
    print(f"\nCIOH : {n_addr} adresses → {n_clus} clusters "
          f"(réduction de {(1 - n_clus/n_addr)*100:.0f}%)")
    return addr_to_cluster


# ===========================================================================
# 5. DÉTECTION DE CYCLES
# ===========================================================================

def detect_wash_cycles(G: nx.DiGraph, df: pd.DataFrame) -> List[dict]:
    """
    Détecte les cycles suspects dans le graphe.

    Score de suspicion (0–1) basé sur 4 critères :
      +0.20  longueur du cycle (2-cycle = le plus suspect)
      +0.35  fenêtre temporelle : toutes les tx du cycle dans TIME_WINDOW_SEC
      +0.35  similarité des montants : variation ≤ AMOUNT_TOLERANCE
      +0.10  volume significatif (≥ MIN_CYCLE_AMOUNT BTC)

    Algorithme : Johnson via nx.simple_cycles — recherche limitée aux
    composantes fortement connexes (SCC) pour la performance.
    """
    print("\nRecherche de cycles suspects...")

    # Index (from, to) → liste de transactions
    edge_index: Dict[Tuple, list] = defaultdict(list)
    for _, r in df.iterrows():
        edge_index[(r["from_addr"], r["to_addr"])].append(
            {"tx_id": r["tx_id"], "amount": r["amount_btc"], "timestamp": r["timestamp"]}
        )

    results = []
    sccs = [scc for scc in nx.strongly_connected_components(G) if len(scc) > 1]

    if not sccs:
        print("  Aucune SCC → aucun cycle possible dans ce graphe.")
        return []

    raw_count = 0
    for scc in sccs:
        sub = G.subgraph(scc)
        for cycle in nx.simple_cycles(sub):
            if not (2 <= len(cycle) <= CYCLE_MAX_LENGTH):
                continue
            raw_count += 1

            edges = list(zip(cycle, cycle[1:] + [cycle[0]]))
            if not all(e in edge_index for e in edges):
                continue

            # Transaction représentative par arête (la plus récente)
            rep_txs   = [sorted(edge_index[e], key=lambda x: x["timestamp"])[-1] for e in edges]
            timestamps = [t["timestamp"] for t in rep_txs]
            amounts    = [t["amount"]    for t in rep_txs]

            time_span    = max(timestamps) - min(timestamps)
            is_time_ok   = time_span <= TIME_WINDOW_SEC

            max_a, min_a = max(amounts), min(amounts)
            amount_ratio = (max_a - min_a) / max_a if max_a > 0 else 1.0
            is_amount_ok = amount_ratio <= AMOUNT_TOLERANCE
            is_vol_ok    = min_a >= MIN_CYCLE_AMOUNT

            # Score composite
            score = 0.0
            score += 0.20 * (1 - (len(cycle) - 2) / max(CYCLE_MAX_LENGTH - 2, 1))
            if is_time_ok:   score += 0.35
            if is_amount_ok: score += 0.35
            if is_vol_ok:    score += 0.10

            results.append({
                "cycle":        cycle,
                "length":       len(cycle),
                "edges":        edges,
                "time_span_h":  time_span / 3600,
                "amounts":      amounts,
                "cycle_volume": min_a,
                "amount_ratio": amount_ratio,
                "is_time_ok":   is_time_ok,
                "is_amount_ok": is_amount_ok,
                "suspicion":    round(score, 3),
            })

    results.sort(key=lambda x: x["suspicion"], reverse=True)
    suspicious = [c for c in results if c["suspicion"] >= 0.5]
    print(f"  {raw_count} cycles bruts → {len(results)} retenus "
          f"→ {len(suspicious)} suspects (score ≥ 0.5)")
    return results


# ===========================================================================
# 6. DÉTECTION DES PEEL CHAINS
# ===========================================================================

def detect_peel_chains(G: nx.DiGraph, min_length: int = 4) -> List[List[str]]:
    """
    Peel chain : longue séquence linéaire A → B → C → D → …
    Chaque nœud intermédiaire a exactement 1 in-degree et 1 out-degree.
    Montant légèrement décroissant à chaque hop (frais).

    Utilisé pour : coin mixing, chain hopping, brouillage de traçabilité.
    Signal complémentaire aux cycles — souvent précède ou suit un wash pattern.
    """
    chains, visited = [], set()

    for start in G.nodes():
        if start in visited or G.in_degree(start) != 0:
            continue
        chain, cur = [start], start
        while True:
            succs = list(G.successors(cur))
            if len(succs) != 1: break
            nxt = succs[0]
            if G.in_degree(nxt) != 1 or nxt in visited or nxt == start: break
            chain.append(nxt)
            cur = nxt
        if len(chain) >= min_length:
            chains.append(chain)
            visited.update(chain)

    print(f"\nPeel chains (longueur ≥ {min_length}) : {len(chains)} détectées")
    for c in chains[:3]:
        print(f"  {'→'.join(c[:5])}{'→...' if len(c) > 5 else ''} ({len(c)} hops)")
    return chains


# ===========================================================================
# 7. SCORE DE SUSPICION AGRÉGÉ
# ===========================================================================

def compute_scores(
    G: nx.DiGraph,
    cycles: List[dict],
    chains: List[List[str]],
    addr_to_cluster: Dict[str, str],
) -> Dict[str, float]:
    """
    Score composite par adresse (0–1), propagé au niveau cluster (CIOH).

    Contributions :
      Cycles suspects   → +0.50 × score_cycle  (par cycle impliquant l'adresse)
      Peel chain        → +0.20
      Ratio in/out ≈ 1  → +0.15  (fonds qui repartent presque entiers)
      Hub (in ≥ 3 ET out ≥ 3) → +0.15

    Propagation CIOH : le score max d'un cluster est partagé à 80%
    avec toutes les adresses de ce cluster.
    """
    scores: Dict[str, float] = defaultdict(float)

    for c in cycles:
        for addr in c["cycle"]:
            scores[addr] += 0.50 * c["suspicion"]

    for chain in chains:
        for addr in chain:
            scores[addr] += 0.20

    for n in G.nodes():
        in_b, out_b = G.nodes[n].get("in_btc", 0), G.nodes[n].get("out_btc", 0)
        vol = in_b + out_b
        if vol > 0.001:
            ratio = min(in_b, out_b) / max(in_b, out_b) if max(in_b, out_b) > 0 else 0
            scores[n] += 0.15 * ratio
        if G.in_degree(n) >= 3 and G.out_degree(n) >= 3:
            scores[n] += 0.15

    # Normalisation 0–1
    if scores:
        mx = max(scores.values())
        if mx > 0:
            scores = {k: min(v / mx, 1.0) for k, v in scores.items()}

    # Propagation au cluster (CIOH)
    cluster_max: Dict[str, float] = defaultdict(float)
    for addr, cluster in addr_to_cluster.items():
        cluster_max[cluster] = max(cluster_max[cluster], scores.get(addr, 0.0))
    for addr, cluster in addr_to_cluster.items():
        scores[addr] = max(scores.get(addr, 0.0), cluster_max[cluster] * 0.8)

    return dict(scores)


# ===========================================================================
# 8. ÉVALUATION
# ===========================================================================

def evaluate(scores: Dict[str, float], wash_clusters: List[Set[str]], threshold: float = 0.4):
    """Précision / Rappel / F1 vs ground truth (données synthétiques)."""
    truth  = set().union(*wash_clusters)
    flagged = {a for a, s in scores.items() if s >= threshold}
    tp = len(flagged & truth)
    fp = len(flagged - truth)
    fn = len(truth - flagged)
    p  = tp / (tp + fp) if tp + fp > 0 else 0
    r  = tp / (tp + fn) if tp + fn > 0 else 0
    f1 = 2 * p * r / (p + r) if p + r > 0 else 0
    print(f"\n── Évaluation (seuil={threshold}) ──────────────────")
    print(f"  Adresses wash réelles : {len(truth)}")
    print(f"  Adresses flaggées     : {len(flagged)}")
    print(f"  TP={tp}  FP={fp}  FN={fn}")
    print(f"  Précision : {p:.1%}   Rappel : {r:.1%}   F1 : {f1:.1%}")


# ===========================================================================
# 9. VISUALISATION
# ===========================================================================

def plot_graph(
    G: nx.DiGraph,
    scores: Dict[str, float],
    cycles: List[dict],
    wash_clusters: Optional[List[Set[str]]] = None,
) -> go.Figure:
    """
    Encodage visuel :
    - Couleur nœud  : score de suspicion (vert → rouge)
    - Taille nœud   : volume BTC
    - Arête rouge   : appartient à un cycle suspect (score ≥ 0.5)
    - Arête grise   : transaction normale
    - Cercle violet : cluster de wash trading connu (ground truth)
    """
    pos = nx.spring_layout(G, seed=42, k=1.5)

    cycle_edges = {
        e for c in cycles if c["suspicion"] >= 0.5 for e in c["edges"]
    }

    fig = go.Figure()

    # Arêtes normales
    nx_list, ny_list = [], []
    for u, v in G.edges():
        if (u, v) not in cycle_edges:
            x0, y0 = pos[u]; x1, y1 = pos[v]
            nx_list += [x0, x1, None]; ny_list += [y0, y1, None]
    if nx_list:
        fig.add_trace(go.Scatter(x=nx_list, y=ny_list, mode="lines",
                                 line=dict(width=0.6, color="rgba(150,150,150,0.3)"),
                                 hoverinfo="none", showlegend=False))

    # Arêtes suspectes
    sx_list, sy_list = [], []
    for u, v in G.edges():
        if (u, v) in cycle_edges:
            x0, y0 = pos[u]; x1, y1 = pos[v]
            sx_list += [x0, x1, None]; sy_list += [y0, y1, None]
    if sx_list:
        fig.add_trace(go.Scatter(x=sx_list, y=sy_list, mode="lines",
                                 line=dict(width=2.2, color="rgba(210,50,50,0.75)"),
                                 hoverinfo="none", showlegend=True,
                                 name="⚠ Arêtes de cycles suspects"))

    # Nœuds
    nodes = list(G.nodes())
    node_x = [pos[n][0] for n in nodes]
    node_y = [pos[n][1] for n in nodes]
    node_score = [scores.get(n, 0) for n in nodes]
    node_size  = [max(8, min(30, G.nodes[n].get("volume", 0.001) * 15 + 8)) for n in nodes]
    hover = [
        f"<b>{n}</b><br>"
        f"Score : {scores.get(n,0):.3f}<br>"
        f"Volume : {G.nodes[n].get('volume',0):.4f} BTC<br>"
        f"Envoyé/Reçu : {G.nodes[n].get('out_btc',0):.4f} / {G.nodes[n].get('in_btc',0):.4f}<br>"
        f"Degré out/in : {G.out_degree(n)}/{G.in_degree(n)}"
        for n in nodes
    ]

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers",
        marker=dict(size=node_size, color=node_score, cmin=0, cmax=1,
                    colorscale=[[0,"#1D9E75"],[0.3,"#EF9F27"],[0.7,"#E85D24"],[1,"#7A1F1F"]],
                    showscale=True, colorbar=dict(title="Score<br>suspicion", thickness=14, x=1.02),
                    line=dict(width=1, color="white")),
        text=nodes, hovertemplate="%{customdata}<extra></extra>",
        customdata=hover, showlegend=False))

    # Ground truth (données synthétiques)
    if wash_clusters:
        for i, cluster in enumerate(wash_clusters):
            present = [n for n in cluster if n in pos]
            if not present: continue
            cx = np.mean([pos[n][0] for n in present])
            cy = np.mean([pos[n][1] for n in present])
            fig.add_trace(go.Scatter(
                x=[cx], y=[cy], mode="markers",
                marker=dict(size=70, color="rgba(0,0,0,0)",
                            line=dict(width=2.5, color="rgba(160,50,200,0.75)"),
                            symbol="circle"),
                name="Wash cluster (ground truth)" if i == 0 else f"Wash cluster {i+1}",
                showlegend=(i == 0), hoverinfo="skip"))

    fig.update_layout(
        title="Graphe de transactions Bitcoin — Détection du Wash Trading",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="white", paper_bgcolor="white",
        width=960, height=700,
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.85)"))
    return fig


def plot_scores_distribution(
    scores: Dict[str, float],
    wash_clusters: Optional[List[Set[str]]] = None,
) -> go.Figure:
    """Distribution des scores de suspicion — wash vs normaux."""
    truth = set().union(*wash_clusters) if wash_clusters else set()
    wash_s   = [s for a, s in scores.items() if a in truth]
    normal_s = [s for a, s in scores.items() if a not in truth]

    fig = go.Figure()
    if normal_s:
        fig.add_trace(go.Histogram(x=normal_s, name="Normaux",
                                   marker_color="rgba(24,95,165,0.6)", nbinsx=20, opacity=0.8))
    if wash_s:
        fig.add_trace(go.Histogram(x=wash_s, name="Wash trading",
                                   marker_color="rgba(200,50,50,0.7)", nbinsx=20, opacity=0.85))
    fig.add_vline(x=0.4, line_dash="dash", line_color="gray",
                  annotation_text="Seuil 0.4")
    fig.update_layout(
        title="Distribution des scores de suspicion par type d'adresse",
        xaxis_title="Score", yaxis_title="Nb adresses",
        barmode="overlay", plot_bgcolor="white", paper_bgcolor="white",
        width=800, height=380)
    return fig


def plot_top_cycles(cycles: List[dict], top_n: int = 10) -> go.Figure:
    """Tableau des cycles les plus suspects."""
    top = cycles[:top_n]
    rows = [
        (f"{' → '.join(c['cycle'])} → {c['cycle'][0]}",
         c["length"], c["suspicion"],
         f"{c['time_span_h']:.1f}h",
         f"{round(c['cycle_volume'], 4)} BTC",
         "✓" if c["is_time_ok"] else "✗",
         "✓" if c["is_amount_ok"] else "✗")
        for c in top
    ]
    cols = ["Cycle", "Longueur", "Score", "Δt", "Volume", "Δt OK", "Montant OK"]
    fig = go.Figure(go.Table(
        header=dict(values=cols, fill_color="#185FA5",
                    font=dict(color="white", size=12), align="left"),
        cells=dict(values=list(zip(*rows)) if rows else [[]]*len(cols),
                   fill_color=[["#f9f9f9","white"] * (len(rows)//2 + 1)],
                   align="left", font_size=11)))
    fig.update_layout(title=f"Top {top_n} cycles les plus suspects",
                      width=900, height=80 + 30 * len(rows))
    return fig


# ===========================================================================
# 10. PIPELINE COMPLET
# ===========================================================================

if __name__ == "__main__":
    import os
    os.makedirs("output_graphs", exist_ok=True)

    # 1. Données
    if USE_REAL_API:
        print(f"API Blockstream ({SEED_ADDRESS[:20]}...)...")
        df = fetch_graph_api(SEED_ADDRESS, max_hops=2)
        wash_clusters = None
        if df.empty:
            print("Échec API → bascule synthétique")
            df, wash_clusters = generate_synthetic_graph()
    else:
        df, wash_clusters = generate_synthetic_graph()

    # 2. Graphe
    G = build_graph(df)

    # 3. CIOH
    addr_to_cluster = apply_cioh(df)

    # 4. Cycles
    cycles = detect_wash_cycles(G, df)

    print("\nTop 5 cycles suspects :")
    for c in cycles[:5]:
        path = " → ".join(c["cycle"]) + f" → {c['cycle'][0]}"
        print(f"  [{c['suspicion']:.2f}] {path}"
              f"  | Δt={c['time_span_h']:.1f}h"
              f"  | vol={c['cycle_volume']:.4f} BTC")

    # 5. Peel chains
    chains = detect_peel_chains(G, min_length=4)

    # 6. Scores
    scores = compute_scores(G, cycles, chains, addr_to_cluster)

    print("\nTop 10 adresses suspectes :")
    all_wash = set().union(*wash_clusters) if wash_clusters else set()
    for addr, score in sorted(scores.items(), key=lambda x: -x[1])[:10]:
        tag = "⚠ WASH" if addr in all_wash else "      "
        print(f"  {tag} | {addr:20s} | {score:.3f}")

    # 7. Évaluation
    if wash_clusters:
        evaluate(scores, wash_clusters, threshold=0.4)

    # 8. Exports
    plot_graph(G, scores, cycles, wash_clusters).write_html("wash_network.html")
    plot_scores_distribution(scores, wash_clusters).write_html("wash_scores.html")
    plot_top_cycles(cycles).write_html("wash_cycles_table.html")

    print("\n✓ Terminé.")
    print("  → wash_network.html")
    print("  → wash_scores.html")
    print("  → wash_cycles_table.html")
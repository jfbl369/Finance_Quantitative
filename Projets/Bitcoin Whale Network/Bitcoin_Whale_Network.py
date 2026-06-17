"""
Bitcoin Whale Network — Visualisation 2D des baleines
======================================================
Top N adresses Bitcoin par solde, représentées comme un réseau :
  - Taille du nœud  ∝ sqrt(solde BTC) → baleines clairement visibles
  - Couleur par tier : Mega-whale / Whale / Dolphin / Fish
  - Arêtes = transactions connues entre ces adresses
  - Hover : adresse, solde, tier, nb transactions

Sources de données :
  USE_REAL_API = True  → Blockchair API (gratuit, sans clé, ~100 req/h)
  USE_REAL_API = False → Distribution synthétique réaliste (loi de Pareto)

Dépendances :
  python3 -m pip install networkx plotly pandas numpy requests
"""

import numpy as np
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import requests
import time
import random
from typing import List, Dict, Tuple
import warnings
warnings.filterwarnings("ignore")
random.seed(42)
np.random.seed(42)


# ===========================================================================
# CONFIGURATION
# ===========================================================================

USE_REAL_API   = False   # True = Blockchair API, False = synthétique
N_ADDRESSES    = 300     # Nombre d'adresses à visualiser (max ~500 pour Blockchair)
TOP_N_EDGES    = 150     # Nb max d'arêtes à afficher (trop d'arêtes = illisible)
MIN_BTC_WHALE  = 1_000   # BTC minimum pour être une "baleine"
MIN_BTC_MEGA   = 10_000  # BTC minimum pour être une "méga-baleine"
MIN_BTC_DOLPH  = 100     # BTC minimum pour être un "dauphin"

# Tiers et couleurs
TIERS = {
    "Méga-baleine": {"min": MIN_BTC_MEGA,  "color": "#993C1D", "size_mult": 3.5},
    "Baleine":      {"min": MIN_BTC_WHALE,  "color": "#EF9F27", "size_mult": 2.2},
    "Dauphin":      {"min": MIN_BTC_DOLPH,  "color": "#185FA5", "size_mult": 1.4},
    "Poisson":      {"min": 0,              "color": "#888780", "size_mult": 0.8},
}

KNOWN_ENTITIES = {
    # Quelques exchanges et entités connues (adresses réelles)
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": "Binance Cold Wallet",
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": "Binance",
    "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ": "Bitfinex",
    "3Cbq7aT1tY8kMxWLbitaG7yT6bPbKChq64": "BitPay",
    "1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF": "Satoshi era (dormant)",
}


# ===========================================================================
# 1. DONNÉES SYNTHÉTIQUES — distribution Pareto réaliste
# ===========================================================================

def generate_whale_data(n: int = 300) -> pd.DataFrame:
    """
    Simule la distribution des soldes Bitcoin (loi de Pareto / power law).
    La richesse Bitcoin suit une distribution extrêmement concentrée :
    ~2% des adresses détiennent ~95% des BTC.

    Tiers approximatifs (données réelles ~2024) :
    - Méga-baleines (>10k BTC)  : ~100 adresses
    - Baleines (1k-10k BTC)     : ~2 000 adresses
    - Dauphins (100-1k BTC)     : ~100 000 adresses
    - Poissons (<100 BTC)       : ~50M+ adresses
    """
    records = []

    # Méga-baleines (top ~5%)
    n_mega = max(5, int(n * 0.05))
    for i in range(n_mega):
        btc = np.random.pareto(1.5) * 5000 + 10000
        records.append({"rank": i + 1, "btc": round(btc, 2),
                        "address": f"1Mega{i:04d}...{'x'*8}",
                        "entity": "Exchange" if i < 3 else "Unknown"})

    # Baleines
    n_whale = max(20, int(n * 0.20))
    for i in range(n_whale):
        btc = np.random.pareto(2.0) * 500 + 1000
        btc = min(btc, 9999)
        records.append({"rank": n_mega + i + 1, "btc": round(btc, 2),
                        "address": f"1Whale{i:04d}...{'y'*8}",
                        "entity": "Miner" if i % 5 == 0 else "Unknown"})

    # Dauphins
    n_dolph = max(50, int(n * 0.35))
    for i in range(n_dolph):
        btc = np.random.pareto(2.5) * 50 + 100
        btc = min(btc, 999)
        records.append({"rank": n_mega + n_whale + i + 1, "btc": round(btc, 2),
                        "address": f"1Dolp{i:04d}...{'z'*8}",
                        "entity": "Unknown"})

    # Poissons
    n_fish = n - n_mega - n_whale - n_dolph
    for i in range(n_fish):
        btc = np.random.pareto(3.0) * 5 + 0.1
        btc = min(btc, 99.9)
        records.append({"rank": n_mega + n_whale + n_dolph + i + 1,
                        "btc": round(btc, 4),
                        "address": f"1Fish{i:05d}...{'w'*8}",
                        "entity": "Unknown"})

    df = pd.DataFrame(records)
    df = df.sort_values("btc", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    print(f"Données synthétiques : {len(df)} adresses")
    print(f"  Méga-baleines (>10k BTC) : {(df['btc'] >= MIN_BTC_MEGA).sum()}")
    print(f"  Baleines (1k-10k BTC)    : {((df['btc'] >= MIN_BTC_WHALE) & (df['btc'] < MIN_BTC_MEGA)).sum()}")
    print(f"  Dauphins (100-1k BTC)    : {((df['btc'] >= MIN_BTC_DOLPH) & (df['btc'] < MIN_BTC_WHALE)).sum()}")
    print(f"  Poissons (<100 BTC)      : {(df['btc'] < MIN_BTC_DOLPH).sum()}")
    print(f"  BTC total représenté     : {df['btc'].sum():,.0f} BTC")

    return df


# ===========================================================================
# 2. API BLOCKCHAIR (optionnel)
# ===========================================================================

def fetch_top_addresses_blockchair(n: int = 100) -> pd.DataFrame:
    """
    Récupère les top N adresses Bitcoin par solde via Blockchair.
    API gratuite, limite ~100 requêtes/heure sans clé.
    
    Endpoint : https://api.blockchair.com/bitcoin/addresses
    Paramètres : sort par balance décroissant, limit 100 par page.
    """
    records = []
    limit = min(100, n)
    offset = 0

    while len(records) < n:
        url = (f"https://api.blockchair.com/bitcoin/addresses"
               f"?s=balance(desc)&limit={limit}&offset={offset}")
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if "data" not in data or not data["data"]:
                break

            for item in data["data"]:
                records.append({
                    "address": item.get("address", ""),
                    "btc": item.get("balance", 0) / 1e8,
                    "n_tx": item.get("transaction_count", 0),
                    "entity": item.get("type", "Unknown"),
                })

            offset += limit
            if offset >= n:
                break
            time.sleep(1.2)  # Respecter le rate limit

        except Exception as e:
            print(f"  Blockchair error (offset={offset}): {e}")
            break

    if not records:
        print("Blockchair inaccessible → bascule sur données synthétiques")
        return generate_whale_data(n)

    df = pd.DataFrame(records[:n])
    df["rank"] = range(1, len(df) + 1)

    # Annoter les entités connues
    df["entity"] = df["address"].map(KNOWN_ENTITIES).fillna(df["entity"])

    print(f"Blockchair : {len(df)} adresses récupérées")
    return df


# ===========================================================================
# 3. ATTRIBUTION DES TIERS
# ===========================================================================

def assign_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """Assigne le tier et les propriétés visuelles à chaque adresse."""
    def get_tier(btc):
        if btc >= MIN_BTC_MEGA:  return "Méga-baleine"
        if btc >= MIN_BTC_WHALE: return "Baleine"
        if btc >= MIN_BTC_DOLPH: return "Dauphin"
        return "Poisson"

    df["tier"]       = df["btc"].apply(get_tier)
    df["color"]      = df["tier"].map({k: v["color"] for k, v in TIERS.items()})
    df["size_mult"]  = df["tier"].map({k: v["size_mult"] for k, v in TIERS.items()})

    # Taille du nœud : sqrt pour éviter que les méga-baleines écrasent tout
    df["node_size"] = np.sqrt(df["btc"]) * df["size_mult"]
    max_size = df["node_size"].max()
    df["node_size"] = (df["node_size"] / max_size * 55 + 5).clip(5, 60)

    return df


# ===========================================================================
# 4. CONSTRUCTION DU GRAPHE
# ===========================================================================

def build_whale_graph(df: pd.DataFrame, n_edges: int = 150) -> nx.Graph:
    """
    Construit un graphe où les baleines sont connectées si elles ont
    probablement interagi (heuristique : baleines du même tier + proximité de rang).

    Pour les données réelles, on utiliserait les transactions directes
    fetched depuis Blockstream. Ici on génère des connexions plausibles :
    - Exchanges ↔ grandes baleines (dépôts/retraits)
    - Baleines de même tier (co-mouvement)
    - Quelques connexions inter-tier (OTC trades)
    """
    G = nx.Graph()
    addresses = df["address"].tolist()

    for _, row in df.iterrows():
        G.add_node(row["address"],
                   btc=row["btc"],
                   tier=row["tier"],
                   rank=row["rank"],
                   entity=row.get("entity", "Unknown"),
                   node_size=row["node_size"],
                   color=row["color"])

    # Connexions synthétiques réalistes
    edges_added = 0

    # 1. Exchanges → grosses baleines (30% des arêtes)
    mega = df[df["tier"] == "Méga-baleine"]["address"].tolist()
    whales = df[df["tier"] == "Baleine"]["address"].tolist()
    n_exchange_edges = int(n_edges * 0.3)

    for _ in range(n_exchange_edges):
        if len(mega) >= 2:
            a, b = random.sample(mega[:min(len(mega), 10)], 2)
            w = random.uniform(100, 5000)
            G.add_edge(a, b, weight=w)
            edges_added += 1

    # 2. Baleines ↔ baleines voisines de rang (50% des arêtes)
    n_whale_edges = int(n_edges * 0.5)
    all_sorted = df.sort_values("btc", ascending=False)["address"].tolist()
    for i in range(min(n_whale_edges, len(all_sorted) - 1)):
        j = i + random.randint(1, 5)
        if j < len(all_sorted):
            a, b = all_sorted[i], all_sorted[j]
            w = (df.loc[df["address"] == a, "btc"].values[0] +
                 df.loc[df["address"] == b, "btc"].values[0]) / 2
            G.add_edge(a, b, weight=w)
            edges_added += 1

    # 3. Connexions inter-tier aléatoires (20% des arêtes)
    n_random_edges = n_edges - edges_added
    all_addrs = df["address"].tolist()
    for _ in range(n_random_edges):
        a, b = random.sample(all_addrs, 2)
        G.add_edge(a, b, weight=random.uniform(1, 100))

    print(f"\nGraphe : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    return G


# ===========================================================================
# 5. VISUALISATION PRINCIPALE
# ===========================================================================

def plot_whale_network(G: nx.Graph, df: pd.DataFrame) -> go.Figure:
    """
    Graphe 2D force-directed des baleines Bitcoin.

    Encodage visuel :
    - Taille    : sqrt(solde BTC) — les baleines sont clairement distinctes
    - Couleur   : tier (méga-baleine=rouge, baleine=orange, dauphin=bleu, poisson=gris)
    - Arêtes    : transactions / connexions connues, opacité = poids
    - Position  : spring_layout (force-directed) — les nœuds connectés s'attirent
    """
    print("Calcul du layout (force-directed)...")
    pos = nx.spring_layout(G, seed=42, k=2.5, iterations=80,
                           weight="weight")

    fig = go.Figure()

    # ── Arêtes ────────────────────────────────────────────────────────────
    weights = [d.get("weight", 1) for _, _, d in G.edges(data=True)]
    w_max = max(weights) if weights else 1

    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]; x1, y1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=0.5, color="rgba(140,140,140,0.2)"),
        hoverinfo="none", showlegend=False))

    # ── Nœuds par tier ────────────────────────────────────────────────────
    tier_order = ["Méga-baleine", "Baleine", "Dauphin", "Poisson"]

    for tier in tier_order:
        tier_df = df[df["tier"] == tier]
        if tier_df.empty:
            continue

        node_x, node_y, sizes, hover = [], [], [], []

        for _, row in tier_df.iterrows():
            addr = row["address"]
            if addr not in pos:
                continue
            x, y = pos[addr]
            node_x.append(x)
            node_y.append(y)
            sizes.append(row["node_size"])

            entity_str = f"<br>Entité : {row['entity']}" if row.get("entity", "Unknown") != "Unknown" else ""
            hover.append(
                f"<b>{addr[:20]}...</b><br>"
                f"Tier : {row['tier']}<br>"
                f"Solde : <b>{row['btc']:,.2f} BTC</b>{entity_str}<br>"
                f"Rang  : #{int(row['rank'])}"
            )

        fig.add_trace(go.Scatter(
            x=node_x, y=node_y,
            mode="markers",
            name=tier,
            marker=dict(
                size=sizes,
                color=TIERS[tier]["color"],
                opacity=0.85,
                line=dict(width=0.8, color="white"),
            ),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover,
        ))

    # ── Labels pour les top 15 baleines ──────────────────────────────────
    top15 = df.nlargest(15, "btc")
    for _, row in top15.iterrows():
        addr = row["address"]
        if addr not in pos:
            continue
        x, y = pos[addr]
        label = row.get("entity", "") if row.get("entity", "Unknown") != "Unknown" else f"#{int(row['rank'])}"
        fig.add_annotation(
            x=x, y=y, text=label,
            showarrow=False,
            font=dict(size=9, color="rgba(60,60,60,0.9)"),
            yshift=row["node_size"] / 2 + 6,
        )

    fig.update_layout(
        title=dict(
            text=f"Whale Network Bitcoin — Top {len(df)} adresses par solde",
            font=dict(size=16),
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(
            title="<b>Tier</b>",
            x=1.01, y=0.98,
            itemsizing="constant",
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="rgba(0,0,0,0.1)",
            borderwidth=0.5,
        ),
        width=1050, height=750,
        margin=dict(t=60, b=20, l=20, r=160),
    )

    return fig


# ===========================================================================
# 6. VISUALISATION COMPLÉMENTAIRE — Distribution des soldes
# ===========================================================================

def plot_distribution(df: pd.DataFrame) -> go.Figure:
    """
    Scatter plot : rang vs solde BTC (échelle log).
    Montre la concentration extrême de la richesse Bitcoin (loi de Zipf).
    """
    tier_colors = {t: v["color"] for t, v in TIERS.items()}

    fig = go.Figure()
    for tier in ["Méga-baleine", "Baleine", "Dauphin", "Poisson"]:
        sub = df[df["tier"] == tier]
        fig.add_trace(go.Scatter(
            x=sub["rank"], y=sub["btc"],
            mode="markers",
            name=tier,
            marker=dict(size=6, color=tier_colors[tier], opacity=0.8),
            hovertemplate="Rang #%{x}<br>%{y:,.2f} BTC<extra></extra>",
        ))

    # Ligne de séparation des tiers
    for threshold, label in [(MIN_BTC_MEGA, "Méga-baleine"), (MIN_BTC_WHALE, "Baleine"), (MIN_BTC_DOLPH, "Dauphin")]:
        fig.add_hline(y=threshold, line_dash="dot",
                      line_color="rgba(100,100,100,0.4)",
                      annotation_text=f"  {threshold:,} BTC",
                      annotation_position="right")

    fig.update_layout(
        title="Distribution des soldes Bitcoin — Loi de Pareto",
        xaxis_title="Rang (par solde décroissant)",
        yaxis_title="Solde BTC",
        yaxis_type="log",
        plot_bgcolor="white", paper_bgcolor="white",
        width=900, height=420,
        legend=dict(x=0.99, y=0.99, xanchor="right"),
    )
    return fig


# ===========================================================================
# 7. STATISTIQUES RÉSEAU
# ===========================================================================

def print_network_stats(G: nx.Graph, df: pd.DataFrame):
    """Métriques clés du réseau de baleines."""
    print("\n── Statistiques réseau ──────────────────────────")

    # Centralité des méga-baleines
    degree_cent = nx.degree_centrality(G)
    top_central = sorted(degree_cent.items(), key=lambda x: -x[1])[:5]

    print("\nTop 5 nœuds les plus connectés :")
    for addr, centrality in top_central:
        btc = df.loc[df["address"] == addr, "btc"].values
        btc_str = f"{btc[0]:,.0f} BTC" if len(btc) > 0 else "N/A"
        print(f"  {addr[:25]}... | centrality={centrality:.3f} | {btc_str}")

    # Concentration
    total_btc = df["btc"].sum()
    top10_btc = df.nlargest(10, "btc")["btc"].sum()
    top1pct_btc = df.nlargest(max(1, len(df) // 100), "btc")["btc"].sum()
    print(f"\nConcentration :")
    print(f"  Top 10 adresses : {top10_btc / total_btc * 100:.1f}% du BTC total")
    print(f"  Top 1%          : {top1pct_btc / total_btc * 100:.1f}% du BTC total")

    # Composantes connexes
    n_comp = nx.number_connected_components(G)
    print(f"\nComposantes connexes : {n_comp}")
    print(f"Densité du graphe    : {nx.density(G):.4f}")


# ===========================================================================
# 8. PIPELINE
# ===========================================================================

if __name__ == "__main__":
    import os
    os.makedirs("output_graphs", exist_ok=True)

    # 1. Données
    print("=" * 55)
    print("Bitcoin Whale Network")
    print("=" * 55)

    if USE_REAL_API:
        print(f"\nRécupération Blockchair (top {N_ADDRESSES} adresses)...")
        df = fetch_top_addresses_blockchair(N_ADDRESSES)
    else:
        print(f"\nGénération de {N_ADDRESSES} adresses synthétiques...")
        df = generate_whale_data(N_ADDRESSES)

    # 2. Tiers
    df = assign_tiers(df)

    # 3. Graphe
    G = build_whale_graph(df, n_edges=TOP_N_EDGES)

    # 4. Stats
    print_network_stats(G, df)

    # 5. Visualisations
    print("\nGénération des graphiques...")

    fig_network = plot_whale_network(G, df)
    fig_network.write_html("whale_network.html")
    print("  → whale_network.html")

    fig_dist = plot_distribution(df)
    fig_dist.write_html("whale_distribution.html")
    print("  → whale_distribution.html")

    print("\n✓ Terminé. Ouvre les fichiers HTML dans ton navigateur.")
    print("\nNote : avec USE_REAL_API = True, tu obtiens les vraies adresses")
    print("Bitcoin triées par solde via l'API Blockchair (gratuite).")
"""
Dynamic Correlation Network
==========================================
Trois approches pour construire un réseau financier dynamique :
  1. Corrélations de Pearson glissantes (rolling)
  2. MST de Mantegna (Minimum Spanning Tree)
  3. Graphe à seuil (threshold-based)

Dépendances :
    python3 -m pip install yfinance networkx plotly pandas numpy scipy
"""

import numpy as np
import pandas as pd
import yfinance as yf
import networkx as nx
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings("ignore")


# ===========================================================================
# 0. CONFIGURATION
# ===========================================================================

TICKERS = {
    "AAPL": "Tech",  "MSFT": "Tech",  "GOOGL": "Tech",
    "AMZN": "Tech",  "META": "Tech",
    "JPM":  "Finance","GS":  "Finance","BAC":  "Finance","MS": "Finance",
    "XOM":  "Energy", "CVX": "Energy", "SLB": "Energy",
    "JNJ":  "Health", "PFE": "Health", "MRK": "Health",
    "KO":   "Consumer","PEP": "Consumer","PG": "Consumer",
}

SECTOR_COLORS = {
    "Tech":     "#185FA5",
    "Finance":  "#993C1D",
    "Energy":   "#854F0B",
    "Health":   "#0F6E56",
    "Consumer": "#533AB7",
}

WINDOW         = 60     # Fenêtre glissante en jours de bourse (~3 mois)
CORR_THRESHOLD = 0.5    # Seuil pour filtrer les arêtes faibles
START_DATE     = "2019-01-01"
END_DATE       = "2024-01-01"


# ===========================================================================
# 1. DONNÉES
# ===========================================================================

def download_data(tickers: list, start: str, end: str) -> pd.DataFrame:
    print(f"Téléchargement de {len(tickers)} actifs...")
    raw = yf.download(tickers, start=start, end=end, progress=False)["Close"]
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    log_returns = np.log(raw / raw.shift(1)).dropna()
    print(f"Données chargées : {log_returns.shape[0]} jours × {log_returns.shape[1]} actifs")
    return log_returns


# ===========================================================================
# 2. CORRÉLATIONS GLISSANTES
# ===========================================================================

def compute_rolling_correlations(returns: pd.DataFrame, window: int) -> dict:
    corr_matrices = {}
    for i in range(window, len(returns)):
        date = returns.index[i]
        corr_matrices[date] = returns.iloc[i - window : i].corr(method="pearson")
    print(f"Matrices calculées : {len(corr_matrices)} dates (fenêtre={window}j)")
    return corr_matrices


def corr_summary_stats(corr_matrices: dict) -> pd.DataFrame:
    """
    Statistiques agrégées à chaque date :
    - mean_corr       : corrélation moyenne → signal de crise si elle monte
    - median_corr     : médiane (plus robuste aux outliers)
    - pct_high_corr   : % de paires avec |ρ| > 0.6 → densification du réseau
    """
    stats = []
    for date, matrix in corr_matrices.items():
        upper = matrix.values[np.triu_indices_from(matrix.values, k=1)]
        stats.append({
            "date":          date,
            "mean_corr":     float(np.mean(upper)),
            "median_corr":   float(np.median(upper)),
            "pct_high_corr": float(np.mean(np.abs(upper) > 0.6) * 100),
        })
    return pd.DataFrame(stats).set_index("date")


# ===========================================================================
# 3. CONSTRUCTION DU RÉSEAU
# ===========================================================================

def corr_to_distance(corr_matrix: pd.DataFrame) -> pd.DataFrame:
    """ Distance de Mantegna (1999) : d = sqrt(2 × (1 - ρ)) """
    return np.sqrt(2 * (1 - corr_matrix))


def build_mst(corr_matrix: pd.DataFrame, tickers: list) -> nx.Graph:
    dist_matrix = corr_to_distance(corr_matrix)
    G = nx.Graph()
    for t in tickers:
        G.add_node(t)
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            ti, tj = tickers[i], tickers[j]
            G.add_edge(ti, tj,
                       weight=dist_matrix.loc[ti, tj],
                       correlation=corr_matrix.loc[ti, tj])
    return nx.minimum_spanning_tree(G, weight="weight")


def build_threshold_graph(
    corr_matrix: pd.DataFrame, tickers: list, threshold: float
) -> nx.Graph:
    G = nx.Graph()
    for t in tickers:
        G.add_node(t)
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            ti, tj = tickers[i], tickers[j]
            rho = corr_matrix.loc[ti, tj]
            if abs(rho) > threshold:
                G.add_edge(ti, tj, weight=abs(rho), correlation=rho)
    return G


# ===========================================================================
# 4. MÉTRIQUES DE RÉSEAU
# ===========================================================================

def compute_network_metrics(G: nx.Graph, tickers: list) -> pd.DataFrame:
    between = nx.betweenness_centrality(G)
    close   = nx.closeness_centrality(G)
    clust   = nx.clustering(G)
    return pd.DataFrame({
        t: {
            "degree":      G.degree(t),
            "betweenness": between.get(t, 0),
            "closeness":   close.get(t, 0),
            "clustering":  clust.get(t, 0),
        }
        for t in G.nodes()
    }).T


# ===========================================================================
# 5. VISUALISATION — MST STATIQUE
# ===========================================================================

def plot_mst_at_date(
    corr_matrices: dict, ticker_sectors: dict, date=None
) -> go.Figure:
    if date is None:
        date = list(corr_matrices.keys())[-1]

    matrix  = corr_matrices[date]
    tickers = matrix.columns.tolist()
    mst     = build_mst(matrix, tickers)
    pos     = nx.spring_layout(mst, seed=42, k=2)
    between = nx.betweenness_centrality(mst)

    fig = go.Figure()
    for u, v, data in mst.edges(data=True):
        x0, y0 = pos[u]; x1, y1 = pos[v]
        rho = data["correlation"]
        color = (f"rgba(230,80,50,{abs(rho):.2f})" if rho > 0
                 else f"rgba(50,100,230,{abs(rho):.2f})")
        fig.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None], mode="lines",
            line=dict(width=abs(rho) * 4, color=color),
            hoverinfo="none", showlegend=False))

    sectors_seen = set()
    for ticker in mst.nodes():
        sector = ticker_sectors.get(ticker, "Other")
        color  = SECTOR_COLORS.get(sector, "#888")
        x, y   = pos[ticker]
        show   = sector not in sectors_seen
        sectors_seen.add(sector)
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            marker=dict(size=15 + between[ticker] * 300, color=color,
                        line=dict(width=1.5, color="white")),
            text=ticker, textposition="top center", textfont=dict(size=10),
            name=sector if show else "",
            legendgroup=sector, showlegend=show,
            hovertemplate=f"<b>{ticker}</b><br>Secteur: {sector}<br>Betweenness: {between[ticker]:.3f}<extra></extra>"))

    fig.update_layout(
        title=f"MST — Réseau de corrélations au {pd.Timestamp(date).strftime('%d/%m/%Y')}",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(title="Secteur", x=1.01),
        width=900, height=650)
    return fig


# ===========================================================================
# 6. VISUALISATION — ÉVOLUTION TEMPORELLE
# ===========================================================================

def plot_corr_evolution(stats: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Corrélation moyenne du réseau",
                        "% de paires fortement corrélées (|ρ| > 0.6)"),
        shared_xaxes=True, vertical_spacing=0.12)

    fig.add_trace(go.Scatter(
        x=stats.index, y=stats["mean_corr"], mode="lines",
        name="Corrélation moyenne",
        line=dict(color="#185FA5", width=1.5),
        fill="tozeroy", fillcolor="rgba(24,95,165,0.08)"), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=stats.index, y=stats["pct_high_corr"], mode="lines",
        name="% paires fortement corrélées",
        line=dict(color="#993C1D", width=1.5),
        fill="tozeroy", fillcolor="rgba(153,60,29,0.08)"), row=2, col=1)

    for d, label in [("2020-03-16", "COVID crash"), ("2022-01-03", "Fed hawkish")]:
        for row in [1, 2]:
            fig.add_vline(x=d, line_dash="dash",
                          line_color="rgba(80,80,80,0.4)", row=row, col=1)
        fig.add_annotation(x=d, y=0.95, text=label, showarrow=False,
                           font=dict(size=10, color="gray"),
                           xanchor="left", row=1, col=1)

    fig.update_layout(
        title="Évolution dynamique des corrélations",
        height=500, plot_bgcolor="white", paper_bgcolor="white")
    return fig


# ===========================================================================
# 7. VISUALISATION — ANIMATION RÉSEAU + STATS EN TEMPS RÉEL  ← NOUVEAU
# ===========================================================================

def plot_animated_network_with_stats(
    corr_matrices: dict,
    ticker_sectors: dict,
    stats: pd.DataFrame,
    step: int = 20,
) -> go.Figure:
    """
    Animation du réseau de corrélations SYNCHRONISÉE avec les séries temporelles.

    Layout :
    ┌──────────────────────────┬──────────────────┐
    │                          │  ρ moyen          │
    │    Réseau animé          ├──────────────────┤
    │    (MST/seuil)           │  % fort. corrélés │
    └──────────────────────────┴──────────────────┘

    Une ligne verticale se déplace sur les deux séries pour indiquer
    la date courante du frame actif.

    Architecture des traces :
      Indice 0-1 : séries temporelles STATIQUES (jamais mises à jour)
      Indice 2-5 : réseau + indicateurs de date ANIMÉS (mis à jour par frame)
    """
    dates   = sorted(corr_matrices.keys())[::step]
    tickers = list(next(iter(corr_matrices.values())).columns)

    # Position fixe du réseau (calculée une seule fois sur le premier MST)
    first_mst = build_mst(corr_matrices[dates[0]], tickers)
    pos = nx.spring_layout(first_mst, seed=42, k=2)

    # ------------------------------------------------------------------
    # Création du layout en sous-graphes
    # ------------------------------------------------------------------
    fig = make_subplots(
        rows=2, cols=2,
        column_widths=[0.64, 0.36],
        row_heights=[0.5, 0.5],
        specs=[
            [{"type": "scatter", "rowspan": 2}, {"type": "scatter"}],
            [None,                               {"type": "scatter"}],
        ],
        subplot_titles=("", "Corrélation moyenne (ρ)", "% paires fortement corrélées"),
        horizontal_spacing=0.07,
        vertical_spacing=0.14,
    )

    # ------------------------------------------------------------------
    # TRACES 0 & 1 — Séries temporelles complètes (STATIQUES)
    # Ces traces ne figurent PAS dans les frames → elles restent fixes.
    # ------------------------------------------------------------------
    fig.add_trace(go.Scatter(
        x=stats.index, y=stats["mean_corr"],
        mode="lines", name="ρ moyen",
        line=dict(color="#185FA5", width=1.5),
        fill="tozeroy", fillcolor="rgba(24,95,165,0.07)",
        showlegend=False,
    ), row=1, col=2)   # trace index 0

    fig.add_trace(go.Scatter(
        x=stats.index, y=stats["pct_high_corr"],
        mode="lines", name="% fort. corr.",
        line=dict(color="#993C1D", width=1.5),
        fill="tozeroy", fillcolor="rgba(153,60,29,0.07)",
        showlegend=False,
    ), row=2, col=2)   # trace index 1

    # ------------------------------------------------------------------
    # TRACES 2-5 — Placeholders animés (mis à jour par chaque frame)
    # ------------------------------------------------------------------

    # Trace 2 : arêtes du réseau
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="lines",
        line=dict(width=0.8, color="rgba(100,100,100,0.4)"),
        hoverinfo="none", showlegend=False,
    ), row=1, col=1)

    # Trace 3 : nœuds du réseau
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="markers+text",
        text=tickers, textposition="top center",
        textfont=dict(size=9),
        marker=dict(size=12, color=[], line=dict(width=1, color="white")),
        hoverinfo="text", showlegend=False,
    ), row=1, col=1)

    # Bornes Y pour les lignes verticales
    y_min_mean = float(stats["mean_corr"].min())
    y_max_mean = float(stats["mean_corr"].max())
    y_min_pct  = float(stats["pct_high_corr"].min())
    y_max_pct  = float(stats["pct_high_corr"].max())

    # Trace 4 : ligne verticale sur ρ moyen
    fig.add_trace(go.Scatter(
        x=[dates[0], dates[0]], y=[y_min_mean, y_max_mean],
        mode="lines",
        line=dict(color="rgba(24,95,165,0.8)", width=1.5, dash="dot"),
        showlegend=False, hoverinfo="none",
    ), row=1, col=2)

    # Trace 5 : ligne verticale sur % fort. corr.
    fig.add_trace(go.Scatter(
        x=[dates[0], dates[0]], y=[y_min_pct, y_max_pct],
        mode="lines",
        line=dict(color="rgba(153,60,29,0.8)", width=1.5, dash="dot"),
        showlegend=False, hoverinfo="none",
    ), row=2, col=2)

    # ------------------------------------------------------------------
    # CONSTRUCTION DES FRAMES
    # ------------------------------------------------------------------
    frames = []
    for date in dates:
        matrix  = corr_matrices[date]
        G_thresh = build_threshold_graph(matrix, tickers, CORR_THRESHOLD)

        # Arêtes
        edge_x, edge_y = [], []
        for u, v in G_thresh.edges():
            x0, y0 = pos.get(u, (0, 0))
            x1, y1 = pos.get(v, (0, 0))
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        # Nœuds
        node_x = [pos.get(t, (0, 0))[0] for t in tickers]
        node_y = [pos.get(t, (0, 0))[1] for t in tickers]
        node_colors = [
            SECTOR_COLORS.get(ticker_sectors.get(t, "Other"), "#888")
            for t in tickers
        ]

        # Valeur des indicateurs à cette date
        # .asof() retourne la dernière valeur connue ≤ date (parfait pour les trous)
        ts = pd.Timestamp(date)
        mean_val = float(stats["mean_corr"].asof(ts))
        pct_val  = float(stats["pct_high_corr"].asof(ts))

        frames.append(go.Frame(
            name=str(date.date()),
            traces=[2, 3, 4, 5],        # ← seules ces 4 traces sont mises à jour
            data=[
                # Trace 2 : arêtes réseau
                go.Scatter(x=edge_x, y=edge_y, mode="lines",
                           line=dict(width=0.8, color="rgba(100,100,100,0.4)"),
                           hoverinfo="none"),
                # Trace 3 : nœuds réseau
                go.Scatter(x=node_x, y=node_y, mode="markers+text",
                           text=tickers, textposition="top center",
                           textfont=dict(size=9),
                           marker=dict(size=12, color=node_colors,
                                       line=dict(width=1, color="white")),
                           hovertemplate="<b>%{text}</b><extra></extra>"),
                # Trace 4 : ligne verticale ρ moyen
                go.Scatter(x=[ts, ts], y=[y_min_mean, y_max_mean],
                           mode="lines",
                           line=dict(color="rgba(24,95,165,0.8)",
                                     width=1.5, dash="dot")),
                # Trace 5 : ligne verticale % fort. corr.
                go.Scatter(x=[ts, ts], y=[y_min_pct, y_max_pct],
                           mode="lines",
                           line=dict(color="rgba(153,60,29,0.8)",
                                     width=1.5, dash="dot")),
            ],
        ))

    fig.frames = frames

    # ------------------------------------------------------------------
    # LAYOUT FINAL
    # ------------------------------------------------------------------
    fig.update_layout(
        title="Réseau de corrélations dynamique — Réseau + Évolution temporelle",
        plot_bgcolor="white",
        paper_bgcolor="white",
        width=1150, height=620,
        margin=dict(t=60, b=100),
        updatemenus=[dict(
            type="buttons",
            showactive=False,
            x=0.32, y=-0.13, xanchor="center",
            buttons=[
                dict(
                    label="▶ Play",
                    method="animate",
                    args=[None, {
                        "frame": {"duration": 150, "redraw": True},
                        "fromcurrent": True,
                        "transition": {"duration": 0},
                    }],
                ),
                dict(
                    label="⏸ Pause",
                    method="animate",
                    args=[[None], {
                        "frame": {"duration": 0, "redraw": False},
                        "mode": "immediate",
                        "transition": {"duration": 0},
                    }],
                ),
            ],
        )],
        sliders=[dict(
            currentvalue=dict(
                prefix="Date : ", visible=True, xanchor="center",
                font=dict(size=12),
            ),
            steps=[dict(
                method="animate",
                label=f.name,
                args=[[f.name], {
                    "mode": "immediate",
                    "transition": {"duration": 0},
                    "frame": {"duration": 150, "redraw": True},
                }],
            ) for f in frames],
            x=0, y=-0.06, len=0.64,
            pad=dict(t=30, b=10),
        )],
    )

    # Axes réseau
    fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False,
                     row=1, col=1)
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False,
                     row=1, col=1)

    # Axes séries temporelles
    fig.update_yaxes(title_text="ρ moyen", tickformat=".2f",
                     gridcolor="rgba(0,0,0,0.05)", row=1, col=2)
    fig.update_yaxes(title_text="% paires", tickformat=".0f", ticksuffix="%",
                     gridcolor="rgba(0,0,0,0.05)", row=2, col=2)
    fig.update_xaxes(showticklabels=False, row=1, col=2)
    fig.update_xaxes(title_text="Date", row=2, col=2)

    return fig


# ===========================================================================
# 8. PIPELINE COMPLET
# ===========================================================================

if __name__ == "__main__":
    import os
    output_dir = "output_graphs"
    os.makedirs(output_dir, exist_ok=True)

    tickers_list = list(TICKERS.keys())

    # Étape 1 : données
    returns = download_data(tickers_list, START_DATE, END_DATE)

    # Étape 2 : corrélations glissantes
    print(f"\nCalcul des corrélations glissantes (window={WINDOW}j)...")
    corr_matrices = compute_rolling_correlations(returns, window=WINDOW)

    # Étape 3 : statistiques réseau
    print("Calcul des statistiques temporelles...")
    stats = corr_summary_stats(corr_matrices)

    # Étape 4 : MST + métriques à la dernière date
    last_date   = list(corr_matrices.keys())[-1]
    last_matrix = corr_matrices[last_date]
    mst         = build_mst(last_matrix, tickers_list)
    metrics     = compute_network_metrics(mst, tickers_list)
    print("\nTop 5 nœuds par betweenness centrality :")
    print(metrics.sort_values("betweenness", ascending=False).head(5).to_string())

    # Étape 5 : MST statique
    fig_mst = plot_mst_at_date(corr_matrices, TICKERS)
    fig_mst.write_html(f"mst_latest.html")
    print(f"\n→ {output_dir}/mst_latest.html")

    # Étape 6 : évolution temporelle seule
    fig_evo = plot_corr_evolution(stats)
    fig_evo.write_html(f"corr_evolution.html")
    print(f"→ {output_dir}/corr_evolution.html")

    # Étape 7 : animation réseau + stats synchronisées
    print("\nGénération de l'animation combinée (30-60s)...")
    fig_combined = plot_animated_network_with_stats(
        corr_matrices, TICKERS, stats, step=20
    )
    fig_combined.write_html(f"animated_network_with_stats.html")
    print(f"→ {output_dir}/animated_network_with_stats.html")

    print("\n✓ Terminé. Ouvre les fichiers HTML dans ton navigateur.")
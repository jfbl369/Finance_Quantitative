"""
Graph Attention Network (GAT) — Détection de Régimes de Marché
==============================================================
Pipeline complet :
  1. Features par actif : rendement, volatilité, RSI, beta marché
  2. Graphe de corrélations glissant (60j) → structure PyG à chaque date
  3. Labels automatiques VIX : 4 régimes (calme / normal / stress / crise)
  4. GAT 2 couches + global mean pooling → embedding de graphe
  5. Classification supervisée avec gestion du déséquilibre de classes
  6. Extraction et analyse des poids d'attention par régime
  7. Backtest d'une stratégie conditionnelle au régime prédit

Installation (dans ton .venv) :
  python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
  python3 -m pip install torch_geometric
  python3 -m pip install yfinance plotly pandas numpy scikit-learn

Sur Mac M1/M2 :
  python3 -m pip install torch torch_geometric  (fonctionne directement)
"""

import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.metrics import classification_report
from sklearn.preprocessing import StandardScaler
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import torch
import torch.nn as nn
import torch.nn.functional as F

warnings.filterwarnings("ignore")

try:
    from torch_geometric.data import Data
    from torch_geometric.loader import DataLoader
    from torch_geometric.nn import GATConv, global_mean_pool
except ImportError:
    print("ERREUR : torch_geometric non trouvé.")
    print("Installe-le avec :")
    print("  python3 -m pip install torch_geometric")
    raise

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)


# ===========================================================================
# 0. CONFIGURATION
# ===========================================================================

TICKERS = [
    # Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    # Finance
    "JPM", "GS", "BAC", "MS", "WFC",
    # Énergie
    "XOM", "CVX", "COP",
    # Santé
    "JNJ", "PFE", "UNH",
    # Consommation / Défensif
    "KO", "PEP", "PG", "WMT",
    # Référence marché
    "SPY",
]

START     = "2008-01-01"
END       = "2026-01-01"
WINDOW    = 60     # fenêtre glissante (jours de bourse)
CORR_THR  = 0.30   # seuil de corrélation pour créer une arête
N_FEATS   = 5     # features par nœud
N_CLASSES = 4     # nb de régimes
EPOCHS    = 60
LR        = 3e-4
BATCH     = 32
HIDDEN    = 32    # features cachées GAT
HEADS     = 4     # têtes d'attention

# Régimes VIX (seuils standards utilisés par les traders)
REGIMES = {
    0: {"name": "Calme",  "vix_max": 15,  "color": "#1D9E75", "weight": 1.00},
    1: {"name": "Normal", "vix_max": 20,  "color": "#185FA5", "weight": 0.80},
    2: {"name": "Stress", "vix_max": 30,  "color": "#EF9F27", "weight": 0.40},
    3: {"name": "Crise",  "vix_max": 999, "color": "#993C1D", "weight": 0.00},
}
REGIME_NAMES   = {r: v["name"]  for r, v in REGIMES.items()}
REGIME_COLORS  = {r: v["color"] for r, v in REGIMES.items()}
REGIME_WEIGHTS = {r: v["weight"] for r, v in REGIMES.items()}


# ===========================================================================
# 1. DONNÉES
# ===========================================================================

def download_data() -> tuple[pd.DataFrame, pd.Series]:
    print("Téléchargement des données (yfinance)...")
    prices = yf.download(TICKERS, start=START, end=END, progress=False)["Close"]
    vix    = yf.download("^VIX",  start=START, end=END, progress=False)["Close"]

    if isinstance(prices.columns, pd.MultiIndex):
        prices.columns = prices.columns.get_level_values(0)
    if isinstance(vix, pd.DataFrame):
        vix = vix.squeeze()

    # Conserver uniquement les colonnes avec ≥ 90% de données
    prices = prices.dropna(axis=1, thresh=int(len(prices) * 0.9))
    prices = prices.ffill().bfill()
    vix    = vix.reindex(prices.index).ffill().bfill()

    print(f"Actifs retenus : {[c for c in prices.columns if c != 'SPY']}")
    print(f"Période        : {prices.index[0].date()} → {prices.index[-1].date()}"
          f" ({len(prices)} jours)")
    return prices, vix


# ===========================================================================
# 2. FEATURE ENGINEERING
# ===========================================================================

def compute_features(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    5 features par actif, capturant des dimensions complémentaires :

    f0 — Rendement 5j    : signal de momentum court-terme
    f1 — Volatilité 20j  : niveau de risque instantané (annualisé)
    f2 — Momentum 60j    : tendance moyen-terme (fenêtre = WINDOW)
    f3 — RSI-14          : sur/sous-achat, normalisé en [0, 1]
    f4 — Beta 60j vs SPY : sensibilité au risque systémique

    Chaque feature est calculée pour tous les actifs à toutes les dates.
    La normalisation (StandardScaler) est faite lors de la construction du dataset.
    """
    log_ret = np.log(prices / prices.shift(1))

    f0 = log_ret.rolling(5).sum()
    f1 = log_ret.rolling(20).std() * np.sqrt(252)
    f2 = log_ret.rolling(60).sum()

    # RSI-14 (Wilder smoothing simplifié → rolling mean)
    delta = log_ret
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    f3    = (100 - 100 / (1 + rs)) / 100  # [0, 1]

    # Beta = cov(actif, marché) / var(marché)
    spy_ret = log_ret.get("SPY", log_ret.mean(axis=1))
    f4 = pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
    for col in prices.columns:
        cov = log_ret[col].rolling(60).cov(spy_ret)
        var = spy_ret.rolling(60).var()
        f4[col] = (cov / var.replace(0, np.nan)).clip(-3, 3)

    return {"f0": f0, "f1": f1, "f2": f2, "f3": f3, "f4": f4}


# ===========================================================================
# 3. LABELS VIX → RÉGIMES
# ===========================================================================

def get_vix_labels(vix: pd.Series) -> pd.Series:
    """
    Convertit le niveau VIX en label de régime (0–3).

    Seuils VIX standards (approximatifs, utilisés par les praticiens) :
    ─ VIX < 15         : complacence, marchés calmes, faible prime de risque
    ─ VIX 15–20        : conditions normales
    ─ VIX 20–30        : stress accru, incertitude macro significative
    ─ VIX > 30         : panique, choc systémique (COVID-19 = 82, GFC = 80)
    """
    labels = pd.Series(np.nan, index=vix.index, dtype="Int64")
    labels[vix < 15]                       = 0
    labels[(vix >= 15) & (vix < 20)]      = 1
    labels[(vix >= 20) & (vix < 30)]      = 2
    labels[vix >= 30]                      = 3
    return labels


# ===========================================================================
# 4. DATASET PYTORCH GEOMETRIC
# ===========================================================================

def build_pyg_dataset(
    prices: pd.DataFrame,
    features: dict,
    labels: pd.Series,
) -> tuple[list, list]:
    """
    Construit une liste d'objets PyG Data, un par date.

    Chaque Data contient :
    ┌────────────────────────────────────────────────────────────────┐
    │  x          [N_actifs × N_FEATS]  — features normalisées       │
    │  edge_index [2 × N_arêtes]        — paires corrélées           │
    │  edge_attr  [N_arêtes × 1]        — valeur de corrélation      │
    │  y          [1]                   — label régime (0–3)          │
    └────────────────────────────────────────────────────────────────┘

    La corrélation est calculée sur les WINDOW jours précédant la date t.
    Une arête (i, j) est créée si |ρ_{ij}| ≥ CORR_THR.
    """
    log_ret  = np.log(prices / prices.shift(1))
    tickers  = [c for c in prices.columns if c != "SPY"]
    N        = len(tickers)
    scaler   = StandardScaler()

    dataset, dates = [], []

    for date in prices.index[WINDOW:]:
        if date not in labels.index or pd.isna(labels[date]):
            continue

        loc = prices.index.get_loc(date)
        window_ret = log_ret.iloc[loc - WINDOW: loc][tickers]

        if window_ret.isnull().sum().sum() > N * 5:
            continue

        # ── Arêtes (corrélation glissante) ──────────────────────────
        corr = window_ret.corr().fillna(0).values
        src, dst, weights = [], [], []
        for i in range(N):
            for j in range(i + 1, N):
                rho = corr[i, j]
                if abs(rho) >= CORR_THR:
                    src  += [i, j]
                    dst  += [j, i]
                    weights += [rho, rho]

        if len(src) == 0:
            continue

        edge_index = torch.tensor([src, dst], dtype=torch.long)
        edge_attr  = torch.tensor(weights, dtype=torch.float).unsqueeze(1)

        # ── Features des nœuds ───────────────────────────────────────
        feat_matrix = np.stack([
            np.nan_to_num(features[fk].loc[date, tickers].values, nan=0.0)
            for fk in ["f0", "f1", "f2", "f3", "f4"]
        ], axis=1)  # (N, 5)

        x = torch.tensor(
            scaler.fit_transform(feat_matrix),
            dtype=torch.float,
        )

        y = torch.tensor([int(labels[date])], dtype=torch.long)

        dataset.append(Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y))
        dates.append(date)

    # Distribution des classes
    all_y = [d.y.item() for d in dataset]
    print(f"\nDataset : {len(dataset)} graphes")
    for r, info in REGIMES.items():
        n = all_y.count(r)
        print(f"  {info['name']:8s} (VIX seuil {info['vix_max']:>3}) : "
              f"{n:4d} ({n / len(all_y) * 100:.1f}%)")

    return dataset, dates


# ===========================================================================
# 5. MODÈLE GAT
# ===========================================================================

class GATRegimeDetector(nn.Module):
    """
    Architecture GAT pour la classification de régimes de marché.

    Couche 1 : GATConv(5 → 32, 4 têtes, concat)  → 128 features/nœud
    ELU + Dropout(0.3)
    Couche 2 : GATConv(128 → 32, 1 tête, mean)   →  32 features/nœud
    ELU
    Global mean pool                               →  32 features/graphe
    MLP(32 → 16 → 4)                              →  logits de régime

    ── Pourquoi GAT et non GCN ?
    Les poids d'attention α_{ij} ∈ [0,1] sont appris dynamiquement :
    pendant une crise, le modèle apprend que TOUS les voisins comptent
    (attention uniforme = co-mouvement total).
    En régime calme, il se concentre sur les pairs sectoriels.
    Ce différentiel d'attention est le signal de détection de régime.

    ── Rôle de edge_attr (corrélation)
    Passer la corrélation en edge feature permet au GAT d'pondérer
    l'attention non seulement par la structure du graphe mais aussi
    par la force du lien — une corrélation de 0.9 compte plus que 0.3.
    """
    def __init__(self):
        super().__init__()
        self.gat1 = GATConv(
            N_FEATS, HIDDEN,
            heads=HEADS, concat=True, dropout=0.3, edge_dim=1,
        )
        self.gat2 = GATConv(
            HIDDEN * HEADS, HIDDEN,
            heads=1, concat=False, dropout=0.3, edge_dim=1,
        )
        self.classifier = nn.Sequential(
            nn.Linear(HIDDEN, HIDDEN // 2),
            nn.ELU(),
            nn.Dropout(0.2),
            nn.Linear(HIDDEN // 2, N_CLASSES),
        )

    def forward(
        self, x, edge_index, edge_attr, batch,
        return_attention: bool = False,
    ):
        # ── GAT layer 1
        if return_attention:
            x, (_, alpha1) = self.gat1(
                x, edge_index, edge_attr,
                return_attention_weights=True,
            )
        else:
            x      = self.gat1(x, edge_index, edge_attr)
            alpha1 = None

        x = F.elu(x)
        x = F.dropout(x, p=0.3, training=self.training)

        # ── GAT layer 2
        if return_attention:
            x, (_, alpha2) = self.gat2(
                x, edge_index, edge_attr,
                return_attention_weights=True,
            )
        else:
            x      = self.gat2(x, edge_index, edge_attr)
            alpha2 = None

        x = F.elu(x)

        # ── Graph-level pooling
        x = global_mean_pool(x, batch)

        # ── Classification
        logits = self.classifier(x)

        return (logits, alpha1, alpha2) if return_attention else logits


# ===========================================================================
# 6. ENTRAÎNEMENT
# ===========================================================================

def compute_class_weights(dataset: list) -> torch.Tensor:
    """
    Poids inversement proportionnels à la fréquence de chaque classe.
    Évite que le modèle ignore les régimes rares (crise = <10% des jours).
    w_i = N / (K × count_i)
    """
    counts = torch.zeros(N_CLASSES)
    for d in dataset:
        counts[d.y.item()] += 1
    return len(dataset) / (N_CLASSES * counts.clamp(min=1))


def train_model(
    train_data: list,
    val_data: list,
) -> tuple[GATRegimeDetector, dict]:

    model     = GATRegimeDetector()
    weights   = compute_class_weights(train_data)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    train_loader = DataLoader(train_data, batch_size=BATCH, shuffle=True)
    val_loader   = DataLoader(val_data,   batch_size=BATCH, shuffle=False)

    best_val_acc = 0.0
    best_state   = None
    history      = {k: [] for k in ["train_loss", "train_acc", "val_loss", "val_acc"]}

    print(f"\nEntraînement ({EPOCHS} epochs, {len(train_data)} graphes)...")

    for epoch in range(1, EPOCHS + 1):
        # ── Train
        model.train()
        t_loss = t_correct = t_total = 0
        for batch in train_loader:
            optimizer.zero_grad()
            logits = model(batch.x, batch.edge_index, batch.edge_attr, batch.batch)
            loss   = criterion(logits, batch.y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            t_loss    += loss.item() * len(batch)
            t_correct += (logits.argmax(1) == batch.y).sum().item()
            t_total   += len(batch)

        # ── Validation
        model.eval()
        v_loss = v_correct = v_total = 0
        with torch.no_grad():
            for batch in val_loader:
                logits  = model(batch.x, batch.edge_index, batch.edge_attr, batch.batch)
                v_loss    += criterion(logits, batch.y).item() * len(batch)
                v_correct += (logits.argmax(1) == batch.y).sum().item()
                v_total   += len(batch)

        tl = t_loss / t_total
        ta = t_correct / t_total
        vl = v_loss / v_total
        va = v_correct / v_total

        if va > best_val_acc:
            best_val_acc = va
            best_state   = {k: v.clone() for k, v in model.state_dict().items()}

        for key, val in zip(
            ["train_loss", "train_acc", "val_loss", "val_acc"], [tl, ta, vl, va]
        ):
            history[key].append(val)

        scheduler.step()

        if epoch % 10 == 0:
            print(f"  Epoch {epoch:3d}/{EPOCHS} | "
                  f"train  loss={tl:.3f}  acc={ta:.1%} | "
                  f"val    loss={vl:.3f}  acc={va:.1%}")

    print(f"\nMeilleure val accuracy : {best_val_acc:.1%}")
    model.load_state_dict(best_state)
    return model, history


# ===========================================================================
# 7. ÉVALUATION
# ===========================================================================

def evaluate_model(
    model: GATRegimeDetector,
    test_data: list,
    test_dates: list,
) -> tuple[list, list, np.ndarray]:

    model.eval()
    loader = DataLoader(test_data, batch_size=1, shuffle=False)

    preds, true_labels, probs = [], [], []
    with torch.no_grad():
        for batch in loader:
            logits = model(batch.x, batch.edge_index, batch.edge_attr, batch.batch)
            p      = F.softmax(logits, dim=1).squeeze().numpy()
            preds.append(logits.argmax(1).item())
            true_labels.append(batch.y.item())
            probs.append(p)

    print("\n── Classification Report ──────────────────────────────────────")
    print(classification_report(
        true_labels, preds,
        target_names=[f"{r['name']} ({r['vix_max']})" for r in REGIMES.values()],
        zero_division=0,
    ))

    return preds, true_labels, np.array(probs)


# ===========================================================================
# 8. ANALYSE DES POIDS D'ATTENTION
# ===========================================================================

def analyze_attention(
    model: GATRegimeDetector,
    dataset: list,
    tickers: list,
) -> dict:
    """
    Extrait et agrège les poids d'attention α_{ij} par régime.

    α_{ij} ∈ [0, 1] : contribution normalisée de l'actif j
    pour construire la représentation de l'actif i.

    Interprétation financière :
    ─ Crise (régime 3) : α uniformes → co-mouvement total, diversification nulle
    ─ Calme (régime 0) : α concentrés → chaque actif suit ses pairs sectoriels
    ─ Écart-type de α  : mesure la "sélectivité" du modèle → faible en crise

    Cette analyse constitue la "explainability" du GAT : on peut répondre
    à "quelles connexions ont compté pour ce signal de régime ?"
    """
    model.eval()
    loader = DataLoader(dataset, batch_size=1, shuffle=False)

    regime_mean_attn = {r: [] for r in range(N_CLASSES)}
    regime_std_attn  = {r: [] for r in range(N_CLASSES)}

    with torch.no_grad():
        for data in loader:
            logits, alpha1, _ = model(
                data.x, data.edge_index, data.edge_attr,
                data.batch, return_attention=True,
            )
            regime = data.y.item()
            # alpha1 : [n_edges, n_heads] → moyenne sur les têtes
            attn = alpha1.mean(dim=1).numpy()
            regime_mean_attn[regime].append(attn.mean())
            regime_std_attn[regime].append(attn.std())

    print("\n── Poids d'attention moyens par régime ────────────────────────")
    print(f"  {'Régime':<20} {'α moyen':>10} {'σ(α)':>10}  Interprétation")
    print("  " + "-" * 65)
    for r, info in REGIMES.items():
        means = regime_mean_attn[r]
        stds  = regime_std_attn[r]
        if means:
            m = np.mean(means)
            s = np.mean(stds)
            interp = ("← Attention sélective" if s > 0.08
                      else "← Attention uniforme (co-mouvement)")
            print(f"  {info['name']:<20} {m:>10.4f} {s:>10.4f}  {interp}")

    return regime_mean_attn


# ===========================================================================
# 9. VISUALISATIONS
# ===========================================================================

def plot_training(history: dict) -> go.Figure:
    epochs = list(range(1, len(history["train_loss"]) + 1))
    fig    = make_subplots(rows=1, cols=2,
                           subplot_titles=("Cross-Entropy Loss", "Accuracy"))

    for name, color, dash in [("train", "#185FA5", "solid"), ("val", "#993C1D", "dot")]:
        fig.add_trace(go.Scatter(x=epochs, y=history[f"{name}_loss"],
                                 name=f"{name} loss",
                                 line=dict(color=color, dash=dash, width=1.5)),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=epochs, y=history[f"{name}_acc"],
                                 name=f"{name} acc",
                                 line=dict(color=color, dash=dash, width=1.5)),
                      row=1, col=2)

    fig.update_yaxes(tickformat=".0%", row=1, col=2)
    fig.update_layout(title="Courbes d'entraînement du GAT",
                      height=360, plot_bgcolor="white", paper_bgcolor="white")
    return fig


def plot_regime_timeline(
    dates: list, preds: list, true_labels: list, probs: np.ndarray
) -> go.Figure:
    """
    Timeline des régimes prédits vs labels VIX réels.
    Opacité des marqueurs = confiance du modèle (softmax max).
    """
    df = pd.DataFrame({
        "date": dates, "pred": preds, "true": true_labels,
        **{f"p{r}": probs[:, r] for r in range(N_CLASSES)},
    })

    fig = go.Figure()

    # Régimes prédits (marqueurs colorés)
    for r, info in REGIMES.items():
        sub = df[df["pred"] == r]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["date"], y=[r] * len(sub),
            mode="markers",
            name=info["name"],
            marker=dict(
                size=7, color=info["color"],
                opacity=sub[f"p{r}"].clip(0.4, 1.0).tolist(),
                symbol="square",
            ),
        ))

    # Ground truth VIX (ligne pointillée)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["true"],
        mode="lines",
        line=dict(color="rgba(80,80,80,0.4)", width=1, dash="dot"),
        name="VIX réel",
    ))

    fig.update_layout(
        title="Timeline des régimes de marché — GAT vs VIX",
        yaxis=dict(tickvals=list(range(N_CLASSES)),
                   ticktext=[v["name"] for v in REGIMES.values()]),
        plot_bgcolor="white", paper_bgcolor="white",
        height=420, width=1000,
        legend=dict(x=1.01, y=0.99),
    )
    return fig


def plot_attention_by_regime(regime_attention: dict) -> go.Figure:
    """
    Boxplot des poids d'attention par régime.
    Un σ(α) faible en crise confirme la thèse : l'attention devient uniforme
    quand tout se corrèle (signal de détection de crise).
    """
    fig = go.Figure()
    for r, info in REGIMES.items():
        vals = regime_attention[r]
        if vals:
            fig.add_trace(go.Box(
                y=vals, name=info["name"],
                marker_color=info["color"], boxmean="sd",
                showlegend=False,
            ))

    fig.update_layout(
        title="Distribution des poids d'attention α par régime",
        yaxis_title="Poids d'attention moyen (α)",
        plot_bgcolor="white", paper_bgcolor="white",
        height=380, width=700,
    )
    return fig


def plot_backtest(
    dates: list, preds: list, prices: pd.DataFrame
) -> go.Figure:
    """
    Stratégie conditionnelle au régime prédit par le GAT :
    ─ Calme  (régime 0) : 100% long SPY
    ─ Normal (régime 1) :  80% long SPY + 20% cash
    ─ Stress (régime 2) :  40% long SPY + 60% cash
    ─ Crise  (régime 3) :   0% (cash total, pas de short)

    Signal appliqué avec 1 jour de lag (évite le look-ahead bias).
    Comparé à un buy-and-hold SPY.
    """
    spy_prices = prices["SPY"].reindex(dates).ffill()
    spy_ret    = spy_prices.pct_change().fillna(0.0)

    regime_s     = pd.Series(preds, index=dates)
    alloc        = regime_s.shift(1).map(REGIME_WEIGHTS).fillna(1.0)
    strategy_ret = spy_ret * alloc

    spy_cum  = (1 + spy_ret).cumprod()
    strat_cum = (1 + strategy_ret).cumprod()

    def sharpe(r, n=252):
        mu, sigma = r.mean() * n, r.std() * np.sqrt(n)
        return mu / sigma if sigma > 0 else 0

    def max_drawdown(cum):
        peak = cum.cummax()
        dd   = (cum - peak) / peak
        return dd.min()

    spy_sr, strat_sr = sharpe(spy_ret), sharpe(strategy_ret)
    spy_dd, strat_dd = max_drawdown(spy_cum), max_drawdown(strat_cum)

    fig = go.Figure()

    # Zones de crise (fond rouge)
    crisis_start = None
    for i, (date, r) in enumerate(zip(dates, preds)):
        if r == 3 and crisis_start is None:
            crisis_start = date
        if r != 3 and crisis_start is not None:
            fig.add_vrect(x0=crisis_start, x1=dates[i - 1],
                          fillcolor="rgba(153,60,29,0.08)",
                          layer="below", line_width=0)
            crisis_start = None

    fig.add_trace(go.Scatter(x=dates, y=spy_cum,
                             name=f"Buy & Hold SPY  (Sharpe={spy_sr:.2f}, MDD={spy_dd:.1%})",
                             line=dict(color="#888780", width=1.5)))
    fig.add_trace(go.Scatter(x=dates, y=strat_cum,
                             name=f"Stratégie GAT   (Sharpe={strat_sr:.2f}, MDD={strat_dd:.1%})",
                             line=dict(color="#185FA5", width=2)))

    fig.update_layout(
        title="Backtest — Stratégie conditionnelle au régime GAT vs Buy & Hold SPY",
        yaxis_title="Performance cumulée (base 1)",
        plot_bgcolor="white", paper_bgcolor="white",
        height=460, width=1000,
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.85)"),
    )
    return fig


# ===========================================================================
# 10. PIPELINE COMPLET
# ===========================================================================

if __name__ == "__main__":
    os.makedirs("output_graphs", exist_ok=True)

    # ── 1. Données ──────────────────────────────────────────────────────────
    prices, vix = download_data()
    tickers = [c for c in prices.columns if c != "SPY"]

    # ── 2. Features & labels ────────────────────────────────────────────────
    print("\nCalcul des features...")
    features = compute_features(prices)
    labels   = get_vix_labels(vix)

    vix_dist = labels.value_counts().sort_index()
    print("\nDistribution VIX sur toute la période :")
    for r, n in vix_dist.items():
        print(f"  {REGIMES[r]['name']:8s} : {n:4d} jours ({n/len(labels)*100:.1f}%)")

    # ── 3. Dataset PyG ──────────────────────────────────────────────────────
    print("\nConstruction du dataset...")
    dataset, dates = build_pyg_dataset(prices, features, labels)

    # Split chronologique strict (pas de mélange pour éviter le data leakage)
    n       = len(dataset)
    n_train = int(n * 0.80)
    n_val   = int(n * 0.10)

    train_data = dataset[:n_train]
    val_data   = dataset[n_train: n_train + n_val]
    test_data  = dataset[n_train + n_val:]
    test_dates = dates[n_train + n_val:]

    print(f"\nSplit chronologique → train={len(train_data)} | "
          f"val={len(val_data)} | test={len(test_data)}")

    # ── 4. Entraînement ─────────────────────────────────────────────────────
    model, history = train_model(train_data, val_data)

    # ── 5. Évaluation ───────────────────────────────────────────────────────
    preds, true_labels, probs = evaluate_model(model, test_data, test_dates)

    # ── 6. Attention ────────────────────────────────────────────────────────
    regime_attn = analyze_attention(model, test_data, tickers)

    # ── 7. Sauvegarde du modèle ─────────────────────────────────────────────
    torch.save(model.state_dict(), "gat_regime_model.pt")

    # ── 8. Visualisations ───────────────────────────────────────────────────
    print("\nGénération des graphiques...")

    plot_training(history).write_html("gat_training.html")
    print("  → gat_training.html")

    plot_regime_timeline(test_dates, preds, true_labels, probs).write_html(
        "gat_regime_timeline.html")
    print("  → gat_regime_timeline.html")

    plot_attention_by_regime(regime_attn).write_html(
        "gat_attention.html")
    print("  → gat_attention.html")

    plot_backtest(test_dates, preds, prices).write_html(
        "gat_backtest.html")
    print("  → gat_backtest.html")

    print("\n✓ Terminé.")

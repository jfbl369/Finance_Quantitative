# Roadmap de préparation — Akuna Virtual Quant Trading Challenge

**Objectif :** arriver le 17 août avec une infrastructure et des compétences telles que les 5–8 h soient consacrées à *exécuter et optimiser*, pas à apprendre ou à coder l'infra.

**Principe directeur :** tout ce que tu développes avant l'examen est une **brique réutilisable** le jour J. Chaque module ci-dessous indique explicitement *à quoi il sert pendant le challenge*.

> Hypothèse de travail : l'instrument simulé est probablement une **option** (Akuna est un options market-maker). Les modules 1–3 (logique de MM, inventaire, sélection adverse) valent quel que soit l'actif. Les modules 4–6 (options) sont à prioriser si tu confirmes que ce sont des options ; sinon ils restent un bonus solide.

---

## Vue d'ensemble : les 8 modules

| # | Module | Ce que tu codes | Rôle le jour J |
|---|--------|-----------------|----------------|
| 0 | Infrastructure (sandbox) | Carnet d'ordres + simulateur + harness | Comprendre l'API d'Akuna en minutes, tester offline |
| 1 | MM de base : capturer le spread | Bot baseline symétrique | Ta première soumission rentable |
| 2 | Gestion d'inventaire (Avellaneda-Stoikov) | Skew des cotations | Ne pas exploser sur un mouvement de prix |
| 3 | Sélection adverse / flux toxique | Signal d'imbalance + élargissement | Éviter de se faire ramasser |
| 4 | Pricing d'options + Greeks | Pricer Black-Scholes + Greeks | Coter une option correctement |
| 5 | Volatilité implicite | Solveur IV + courbe de vol | Coter en vol, gérer le vega |
| 6 | Delta-hedging | Hedger automatique | Rester delta-neutre, profiter du spread |
| 7 | Itération rapide | Grid-search + logging + checklist | Tuner vite pendant le chrono |

---

## Module 0 — L'infrastructure : ta sandbox

C'est le socle. Sans elle, tu ne peux rien tester avant le jour J. C'est aussi ton meilleur investissement : Akuna te fournira un moteur, mais avoir construit le tien te fait comprendre instantanément les données qu'ils te donnent.

### 0.1 Théorie — Comment fonctionne un carnet d'ordres (order book)

Un carnet d'ordres a deux côtés :
- **Bids** (achats) : les prix auxquels des gens veulent acheter, triés du plus haut au plus bas.
- **Asks / Offers** (ventes) : les prix auxquels des gens veulent vendre, triés du plus bas au plus haut.

Trois prix clés :
- **Best bid** : le meilleur prix d'achat (le plus haut).
- **Best ask** : le meilleur prix de vente (le plus bas).
- **Mid-price** = (best bid + best ask) / 2 → l'estimation naïve de la « vraie » valeur.
- **Spread** = best ask − best bid → ce que capte le market-maker.

**Exemple chiffré.** Carnet :

```
ASKS    100.20  x150
        100.10  x80      ← best ask
        --------------
        99.90   x100     ← best bid
BIDS    99.80   x200
```

- Mid = (99.90 + 100.10)/2 = **100.00**
- Spread = 100.10 − 99.90 = **0.20**

Un **ordre marché** (market order) consomme la liquidité affichée immédiatement : un achat marché de 50 « lève » 50 unités à 100.10. Un **ordre limite** (limit order) se pose dans le carnet et attend d'être exécuté.

**Règle de matching : price-time priority.** On sert d'abord le meilleur prix ; à prix égal, le premier arrivé (priorité de file). C'est crucial : poster tôt à un bon prix te place devant dans la queue.

### 0.2 Pratique — Ce que tu codes

1. Une classe `OrderBook` : deux structures triées (bids, asks), méthodes `add_limit_order`, `cancel`, `match_market_order`.
2. Un **simulateur de marché** : un « vrai prix » qui suit une marche aléatoire (random walk) + des *noise traders* qui envoient des ordres marché/limites aléatoires autour de ce prix.
3. Une **interface bot** standardisée : `on_market_update(book_state) -> [quotes]`. Ton bot reçoit l'état, renvoie ses cotations. C'est exactement le pattern qu'Akuna utilisera.

### 0.3 Lien avec l'examen

Akuna te donnera un SDK où tu remplis une fonction « à chaque tick → renvoie tes cotations ». Si tu as déjà ce pattern en tête, tu lis leur doc en 10 minutes au lieu d'une heure, et tu peux **rejouer offline** des scénarios pour déboguer.

---

## Module 1 — Market-making de base : capturer le spread

### 1.1 Théorie — D'où vient le profit

Le market-maker ne parie **pas** sur la direction. Il poste un bid et un ask autour de sa **fair value** (sa meilleure estimation de la vraie valeur), et gagne le spread sur chaque aller-retour.

Notons :
- `S` = fair value
- `δ` = demi-spread (distance entre la fair value et chaque cotation)
- Bid = `S − δ`, Ask = `S + δ`, spread total = `2δ`

**Exemple chiffré.** Fair value S = 100, δ = 0.10 :
- Tu postes : achat à **99.90**, vente à **100.10**.
- Quelqu'un te vend à 99.90 → tu détiens un actif valant 100 → **+0.10** latent.
- Quelqu'un t'achète à 100.10 → tu vends → **+0.10** encaissé.
- Aller-retour complet : **+0.20** (= le spread), sans pari directionnel.

**L'arbitrage fondamental :**
- Spread serré → beaucoup de volume capté, mais peu de marge par trade et plus d'exposition au risque.
- Spread large → grosse marge par trade, mais peu de fills.
- La **probabilité d'être exécuté décroît** quand tu t'éloignes du mid.

### 1.2 Pratique — Ce que tu codes

Un bot baseline qui :
1. Estime la fair value (au début : simplement le mid-price).
2. Poste bid = fair − δ, ask = fair + δ, avec δ fixe.
3. Reposte / annule à chaque tick.

Mesure son PnL dans ta sandbox. C'est ta référence : tout module suivant doit faire *mieux* que ce baseline.

### 1.3 Lien avec l'examen

C'est ta **première soumission**. Stratégie gagnante : avoir d'abord quelque chose de simple et rentable, *puis* l'améliorer. Beaucoup de participants n'arrivent même pas à un bot stable — un baseline propre te place déjà au-dessus de la moyenne.

---

## Module 2 — Gestion d'inventaire : le modèle Avellaneda-Stoikov

C'est **le** module qui sépare les gagnants. Un bot symétrique (module 1) explose dès qu'il accumule une grosse position et que le prix bouge contre lui.

### 2.1 Théorie — Le problème de l'inventaire

Si tout le monde te vend, tu accumules une position **longue** `q`. Si le prix chute ensuite, tu perds gros sur ton stock. Il faut donc **décourager** d'accumuler davantage et **inciter** à te débarrasser de ton stock.

L'idée d'Avellaneda-Stoikov : ne pas coter autour du mid, mais autour d'un **prix de réservation** `r` qui se décale selon ton inventaire.

**Prix de réservation :**

```
r = s − q · γ · σ² · (T − t)
```

- `s` = mid-price
- `q` = ton inventaire (positif = long, négatif = short)
- `γ` = ton aversion au risque (paramètre à tuner)
- `σ²` = variance du prix
- `(T − t)` = temps restant

**Spread optimal :**

```
δ = γ · σ² · (T − t) + (2/γ) · ln(1 + γ/k)
```

- `k` = un paramètre lié à la profondeur/intensité du carnet.

Puis : bid = `r − δ/2`, ask = `r + δ/2`.

**Exemple chiffré.** s = 100, σ² = 0.04, γ = 0.1, (T−t) = 1 :
- Inventaire neutre `q = 0` → r = 100 − 0 = 100 → cotations centrées sur 100.
- Inventaire long `q = +10` → r = 100 − 10·0.1·0.04·1 = 100 − 0.04 = **99.96** → tes deux cotations se décalent vers le bas. Résultat : ton **ask devient plus attractif** (les gens t'achètent ton stock) et ton **bid moins attractif** (on arrête de te vendre). Tu te dé-risques automatiquement.

C'est ça, le **skew** d'inventaire : tu inclines tes prix dans le sens qui réduit ta position.

### 2.2 Pratique — Ce que tu codes

1. Suivre `q` (ton inventaire courant) dans le bot.
2. Calculer `r` et `δ` à chaque tick avec les formules ci-dessus.
3. Exposer `γ` et `k` comme paramètres réglables.
4. Comparer le PnL et l'**inventaire max** vs le baseline : tu dois voir l'inventaire rester borné et le PnL plus stable (meilleur Sharpe).

### 2.3 Lien avec l'examen

Pendant le challenge, un mouvement de prix soudain ruine les bots naïfs. Avec le skew, ton bot reste autour de la neutralité et **survit** aux chocs → ton PnL ne se fait pas anéantir d'un coup. C'est souvent ce qui décide du classement.

---

## Module 3 — Sélection adverse et flux toxique

### 3.1 Théorie — Pourquoi on se fait ramasser

Quand quelqu'un te trade dessus, deux cas :
- **Trader non informé** (liquidité, bruit) → bonne nouvelle, tu gagnes ton spread.
- **Trader informé** → il sait que le prix va bouger contre toi. Tu viens d'acheter juste avant une baisse. C'est la **sélection adverse**.

Intuition (modèle de Glosten-Milgrom) : ton spread doit couvrir le coût moyen de trader contre des informés. Plus le flux est « toxique », plus tu dois élargir.

**Signal pratique : l'order flow imbalance (OFI) / pression du carnet.**

```
imbalance = (volume_bid − volume_ask) / (volume_bid + volume_ask)
```

- Imbalance > 0 → forte pression à l'achat → le prix va probablement monter → tu ne veux pas être short, et tu peux relever ta fair value.
- Imbalance < 0 → pression à la vente → prix va baisser.

**Le micro-price** (plus malin que le mid) pondère le mid par l'imbalance :

```
micro_price = (best_ask · vol_bid + best_bid · vol_ask) / (vol_bid + vol_ask)
```

**Exemple chiffré.** best_bid = 99.90 (vol 200), best_ask = 100.10 (vol 50) :
- Mid = 100.00.
- micro_price = (100.10·200 + 99.90·50)/(250) = (20020 + 4995)/250 = **100.06**.
- Interprétation : beaucoup plus d'acheteurs → la « vraie » valeur penche vers 100.06, pas 100.00. Coter autour du micro-price te protège.

### 3.2 Pratique — Ce que tu codes

1. Calculer l'imbalance et le micro-price à chaque tick.
2. Remplacer le mid par le micro-price comme fair value.
3. Quand l'imbalance dépasse un seuil (flux suspect) → **élargir le spread** ou te retirer d'un côté.

### 3.3 Lien avec l'examen

Tu affrontes les modèles d'Akuna et d'autres bots — donc des contreparties potentiellement *informées*. Détecter le flux toxique et reculer au bon moment évite l'hémorragie silencieuse qui plombe le PnL.

---

## Module 4 — Pricing d'options et Greeks *(prioritaire si options)*

### 4.1 Théorie — Black-Scholes en bref

Pour coter une option, il faut savoir combien elle vaut. La formule de Black-Scholes pour un call :

```
C = S·N(d1) − K·e^(−rT)·N(d2)
d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)
d2 = d1 − σ√T
```

- `S` = prix du sous-jacent, `K` = strike, `r` = taux, `T` = maturité, `σ` = volatilité, `N` = loi normale cumulée.

**Les Greeks** mesurent la sensibilité du prix de l'option :
- **Delta (Δ)** = ∂C/∂S → sensibilité au sous-jacent. Un call ATM a Δ ≈ 0.5.
- **Gamma (Γ)** = ∂Δ/∂S → vitesse de variation du delta.
- **Vega (ν)** = ∂C/∂σ → sensibilité à la volatilité. **Le Greek central du métier d'options MM.**
- **Theta (Θ)** = ∂C/∂t → érosion temporelle.

**Exemple chiffré.** S=100, K=100, r=0, T=0.25, σ=0.20 :
- d1 = [0 + (0 + 0.02)·0.25]/(0.20·0.5) = 0.005/0.10 = 0.05
- d2 = 0.05 − 0.10 = −0.05
- N(0.05) ≈ 0.520, N(−0.05) ≈ 0.480
- C ≈ 100·0.520 − 100·0.480 = 52.0 − 48.0 = **4.0**
- Delta ≈ N(d1) ≈ **0.52** (proche de 0.5, cohérent pour de l'ATM).

### 4.2 Pratique — Ce que tu codes

1. Une fonction `black_scholes(S, K, r, T, sigma, type)` → prix.
2. Les Greeks analytiques : delta, gamma, vega, theta.
3. Vérifie-les par différences finies (recalcule le prix avec S+ε et compare la pente) — bon réflexe de validation.

### 4.3 Lien avec l'examen

Si tu cotes des options, c'est non négociable : tu ne peux pas poster un bid/ask sensé sans connaître la valeur théorique. Les Greeks te disent *quel risque* tu prends à chaque fill.

---

## Module 5 — Volatilité implicite et surface de vol

### 5.1 Théorie — Coter en vol, pas en prix

Les options MM ne raisonnent pas en prix mais en **volatilité implicite** (IV) : la valeur de σ qui, injectée dans Black-Scholes, redonne le prix de marché observé. On l'obtient en **inversant** BS numériquement (Newton-Raphson ou bissection, car pas de formule fermée).

La vol n'est pas constante selon le strike : c'est le **smile / skew** de volatilité (les options loin de la monnaie ont une IV plus élevée). Coter, c'est gérer une **courbe** d'IV cohérente.

**Exemple chiffré (intuition de l'inversion).** Le marché affiche un call ATM à 4.0 (cas du module 4). Tu cherches le σ qui donne 4.0 : tu testes σ=0.20 → prix 4.0 → IV = **20 %**. Si demain le call cote 4.4 sans que S ne bouge, l'IV a grimpé (~22 %) : la demande de vol a augmenté.

### 5.2 Pratique — Ce que tu codes

1. Un solveur `implied_vol(price, S, K, r, T)` (Newton, avec fallback bissection si ça diverge).
2. Construire/ajuster une **courbe d'IV** simple par strike.
3. Coter tes options en posant un bid/ask **autour de ta courbe d'IV**, puis reconvertir en prix.

### 5.3 Lien avec l'examen

C'est le langage natif d'un options market-maker. Gérer ton exposition **vega** (combien tu gagnes/perds si la vol bouge) est aussi central que gérer l'inventaire pour une action.

---

## Module 6 — Delta-hedging et gestion du risque

### 6.1 Théorie — Rester delta-neutre

En cotant des options, tu accumules une exposition directionnelle (un delta net). Tu ne veux **pas** parier sur la direction → tu la neutralises en tradant le sous-jacent : c'est le **delta-hedging dynamique**.

**Exemple chiffré.** Tu vends 10 calls de delta 0.5 → ton delta net = −10·0.5 = **−5** (tu es short 5 « équivalents sous-jacent »). Pour neutraliser, tu **achètes 5 unités** du sous-jacent → delta net ≈ 0. Si S bouge, gain sur l'un compense la perte sur l'autre.

Le piège : le delta change (gamma) → il faut **re-hedger** régulièrement. Plus tu hedges souvent, plus tu es neutre mais plus tu paies de coûts de transaction. Arbitrage gamma/theta classique.

### 6.2 Pratique — Ce que tu codes

1. Un calcul du **delta net du portefeuille** à chaque tick.
2. Un **auto-hedger** : si |delta net| dépasse un seuil → trade le sous-jacent pour revenir vers 0.
3. Mesure l'impact sur le PnL : moins de variance, profit qui vient du spread/vol et non du pari directionnel.

### 6.3 Lien avec l'examen

Ça te permet de gagner ton spread *proprement*. Sans hedge, un mouvement du sous-jacent transforme ton activité de MM en pari accidentel — exactement ce qu'un classement basé sur le profit punit.

---

## Module 7 — Itération rapide : ton kit d'exécution

### 7.1 Théorie — Optimiser sans surajuster

Le jour J, le gain vient du **réglage** (γ, k, seuils, largeur de spread), pas de l'écriture de nouveau code. Mais attention à l'**overfitting** : un réglage qui domine ta sandbox peut échouer contre les bots d'Akuna. Vise des paramètres **robustes** (qui marchent bien sur plusieurs scénarios), pas optimaux sur un seul.

Métriques à suivre :
- **PnL total** (le classement).
- **Sharpe** (PnL / volatilité du PnL) → la régularité.
- **Inventaire max** → ton exposition au pire moment.
- **Fill rate** → combien de tes cotations sont exécutées.

### 7.2 Pratique — Ce que tu codes

1. Un **harness de grid-search** : balaie γ, k, seuils sur plusieurs scénarios de marché, sort un tableau de métriques.
2. Du **logging** propre (chaque trade, chaque cotation) pour déboguer vite.
3. Des **templates de code** prêts : fonctions vectorisées, structure du bot, snippets — pour ne rien réécrire pendant le chrono.
4. Une **checklist d'exécution** physique à côté de toi.

### 7.3 Lien avec l'examen

Pendant 5–8 h, ta boucle sera : *lire les règles → câbler ton bot dans leur API → lancer → lire les métriques → ajuster un paramètre → relancer*. Avoir tout ça prêt, c'est gagner des heures que les autres passeront à débugger.

---

## Planning suggéré (≈ 7 semaines, fin juin → 17 août)

| Semaine | Focus | Livrable |
|---------|-------|----------|
| 1 (30 juin) | Module 0 | Sandbox : carnet + simulateur + interface bot |
| 2 | Modules 0→1 | Baseline symétrique rentable + harness de métriques |
| 3 | Module 2 | Bot Avellaneda-Stoikov, inventaire borné |
| 4 | Module 3 | Micro-price + signal d'imbalance + élargissement |
| 5 | Modules 4→5 | Pricer BS + Greeks + solveur IV |
| 6 | Module 6 | Auto-hedger delta, portefeuille neutre |
| 7 (11–16 août) | Module 7 + révision | Grid-search, templates, checklist, répétition générale |
| **17–21 août** | **CHALLENGE** | **Soumission(s)** |

> Adapté à ton profil : avance **un module à la fois**, valide chaque brique par un test chiffré dans la sandbox avant de passer à la suivante. Si une semaine glisse, sacrifie d'abord les modules 4–6 (options) en gardant 0–3, qui constituent un bot solide quel que soit l'instrument.

---

## Synthèse : ce que tu fais PENDANT l'examen (et la brique qui le rend possible)

| Étape jour J | Brique préparée qui sert |
|--------------|--------------------------|
| Comprendre l'API/SDK d'Akuna | Module 0 (tu connais déjà le pattern carnet + on_tick) |
| Poster un premier bot rentable | Module 1 (baseline prêt à recâbler) |
| Survivre aux mouvements de prix | Module 2 (skew d'inventaire) |
| Éviter de te faire ramasser | Module 3 (micro-price, détection de flux) |
| Coter des options correctement | Modules 4–5 (BS, Greeks, IV) |
| Rester delta-neutre | Module 6 (auto-hedger) |
| Optimiser dans le temps imparti | Module 7 (grid-search, templates, checklist) |

**Le fil rouge :** chaque heure investie avant le 17 août retire une tâche de ta charge le jour J. Tu n'apprends rien pendant le challenge — tu exécutes une mécanique que tu maîtrises déjà.

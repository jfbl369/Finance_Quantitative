# Calcul Stochastique
[CEREMADE - Dauphine: Programmation Dynamique](https://www.ceremade.dauphine.fr/~carlier/progdyn.pdf)



# Commodities
## I) Reading
NIVEAU 1 – Comprendre les bases des marchés du gaz et de l’électricité
- "Fundamentals of Natural Gas" – Vivek Chandra \\
- "Electricity Markets: Pricing, Structures and Economics" – Chris Harris

NIVEAU 2 – Apprendre les méthodes de trading et la structure des marchés dérivés énergie
- "Energy and Power Risk Management" – Alexander Eydeland & Krzysztof Wolyniec
- "Power System Economics" – Steven Stoft
- "Natural Gas Trading in North America" – David DeLucia

NIVEAU 3 – Approche avancée : modélisation des prix et stratégies quantitatives
- "Commodity Option Pricing: A Practitioner's Guide" – Iain Clark
- "Modelling Energy Markets for Price Forecasting and Risk Management" – Derek W. Bunn
- "The Economics of Commodity Markets" – Julien Chevallier & Florian Ielpo

## II) Projects
Niveau 1 – Projets de base (0 à 1 mois)
- Construction d’une courbe forward simple
À partir des prix forwards (ex : baseload power 2024, Q3-24, etc.), construis une courbe.
Visualise l’effet de saisonnalité, et compare à la courbe actuelle.
Objectif : comprendre la structure forward (contango / backwardation).

- Simulateur de PnL d’un portefeuille gaz/élec
Crée un fichier Excel ou script Python avec : 
3 positions (spot, forward, option)
Un mark-to-market quotidien
Affiche l’évolution du PnL et décompose : effet prix, effet volume, effet base.

Niveau 2 – Projets intermédiaires (1 à 3 mois)
Objectif : développer une vraie logique de trading et de risque

- Simulation de stratégie de hedging avec produits forward
Exemple : tu vends 100 MW chaque heure cet hiver, comment tu te hedges aujourd’hui avec les produits disponibles ?
Objectif : construire un hedge efficace avec des produits calendaires et mensuels.

- Étude du spark spread (Power vs Gas)
Récupère les données spot gaz et power + prix du CO2.
Calcule le spark spread avec un rendement de 50 %.
Identifie les périodes où le spread est positif = arbitrage production.
C’est une base très utilisée dans le desk power/gaz.

- Étude de corrélation entre prix du gaz et météo (température / HDD)
Objectif : construire un modèle simple expliquant le lien entre froid et hausse des prix.
Tu peux utiliser des données historiques météo + prix TTF ou PEG.

Niveau 3 – Projets avancés (3 à 6 mois)
Objectif : construire un vrai asset de démonstration pour ton CV / entretien

- Backtest d’une stratégie de swing trading sur le gaz spot
Règle simple : achat si le gaz spot baisse sous la moyenne 5 jours.
Tu backtestes la stratégie et affiches le gain cumulé.
Objectif : montrer ton autonomie et ton raisonnement de trader.

- Modèle de prévision de prix day-ahead (gaz ou power)
Utilise une régression linéaire ou un modèle XGBoost
Variables explicatives : demande, température, production renouvelable
Tu testes la performance du modèle sur un an.

- Optimisation d’un stockage de gaz (valeur temps / arbitrage)
Construis un modèle qui simule l’achat et la vente d’un stockage en fonction des spreads spot/forward.
Objectif : estimer la “valeur d’un stockage” sur 12 mois.

## Certifications spécialisées énergie / commodities
- ICE Education – Energy Derivatives & Trading Certificate
(par l’opérateur ICE – très reconnu pour les produits gaz/power)
- EEX Academy – Power & Gas Markets
(European Energy Exchange, offre des modules très concrets et reconnus en Europe)
- IFP School – MOOCs en Energy Trading / Market Fundamentals
(prestige académique, très bien vu dans les CV)

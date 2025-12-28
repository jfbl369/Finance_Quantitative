# Experts
- Helyette Geman

# Commodities
## I) Reading

###TOP 3
- "The Economics of Commodity Markets" – Julien Chevallier & Florian Ielpo
Pourquoi c’est parfait pour toi :
Écrit par un professeur de Dauphine, très clair et structuré.
Accessible pour les non-mathématiciens : il t’introduit à la structure des marchés commodities, les notions d’offre/demande, stockage, théorie du contango/backwardation, etc.
Tu verras comment on modélise les prix des futures, les stratégies de couverture et les fondamentaux des marchés physiques.

Ce que tu y gagnes :
Solide base pour comprendre les prix du pétrole, du gaz, du blé, etc.
Application directe à la compréhension d’un desk de trading commodities.

Niveau : intermédiaire, très lisible même sans background math lourd.

- "Energy and Power Risk Management" - Alexander Eydeland
Pourquoi ce livre est clé :
C’est le best-seller des desks énergie. Très utilisé par les traders en power & gas.
Il explique les risques liés au trading d’électricité, de gaz, de spreads, les options swing, etc.
Tu y verras les méthodes de modélisation des prix (avec sauts, mean-reverting), la valorisation des contrats complexes, et les méthodes de simulation Monte Carlo.
Ce que tu y gagnes :
Une compréhension très concrète de ce que fait un quant ou un trader structuré dans l’énergie.
Le lien entre maths et métier, sans exagérer le niveau théorique.

Niveau : intermédiaire à avancé, mais chaque concept est expliqué progressivement.

- "Financial Modelling with Jump Processes" -  Rama Cont, Peter Tankov

Pourquoi c’est pertinent pour ton ambition :
Coécrit par Peter Tankov (prof ENSAE), spécialiste des produits dérivés sur commodities.
C’est LA référence sur les modèles stochastiques avec discontinuités (jumps), très utilisés en commodities (électricité, pétrole…).
Ce livre t'apprend à modéliser les dynamiques de prix réalistes : processus de Poisson, modèles de Lévy, calibration, pricing.

Ce que tu y gagnes :
Un niveau technique fort, mais qui te met au niveau des recruteurs en hedge fund ou chez les traders quant énergie.
Tu gagnes une crédibilité technique immédiate si tu maîtrises ne serait-ce que 2 chapitres.

Niveau : avancé – à lire doucement, mais avec des chapitres isolés très puissants.

###LISTE PAR NIVEAU
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

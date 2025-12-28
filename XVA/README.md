# 📘 Portfolio XVA – Projets Python

Ce dépôt rassemble une série de projets Python liés au **Credit Valuation Adjustment (CVA)** et à la **gestion du risque de crédit sur dérivés**, développés dans le cadre de ma transition du back-office vers un poste de **Trader XVA**.

Les projets sont classés du plus simple au plus avancé pour refléter ma montée en compétences sur le sujet.

---

## 🟢 Niveau Débutant

### 1. `expected-exposure-simulator`
📊 Simulation de l’Expected Exposure (EE), Effective EE, EPE et PFE d’un produit dérivé (ex: IRS ou FX forward) à l’aide de Monte Carlo.

### 2. `credit-spread-calculator`
🧮 Calculateur de credit spread à partir des inputs fondamentaux : Probabilité de défaut (PD), taux de recouvrement (LGD) et maturité.

### 3. `simple-cva-engine`
📈 Moteur de calcul du CVA unilatéral basé sur la formule :  
\( \text{CVA} = \sum \text{EE}_t \cdot \text{PD}_t \cdot \text{LGD} \cdot \text{DF}_t \)

---

## 🟡 Niveau Intermédiaire

### 4. `cds-pd-bootstrapper`
🔢 Bootstrap de courbe de probabilité de défaut à partir des prix CDS, en appliquant les principes d’équilibre des flux du contrat CDS.

### 5. `bilateral-cva-evaluator`
🔄 Implémentation du calcul bilatéral CVA – DVA, en tenant compte de la probabilité de défaut des deux contreparties.

### 6. `wrong-way-risk-simulator`
⚠️ Simulation d’un dérivé avec risque de Wrong-Way Risk (WWR), où l’exposition augmente quand la qualité de crédit se détériore.

---

## 🔴 Niveau Avancé

### 7. `cva-hedging-simulator`
🛡️ Simulation complète de la couverture dynamique de la CVA à l’aide de CDS + hedge du sous-jacent (delta-hedging), incluant les coûts de transaction.

### 8. `cva-stress-tester`
📉 Moteur de stress testing du CVA face à des chocs sur spreads, recouvrements et expositions (y compris sauts de marché).

### 9. `cva-cds-feedback-loop`
📊 Modélisation de la boucle de rétroaction entre CVA et prix CDS : l’achat de protection CDS impacte lui-même les spreads du marché.

---

## 🎯 Objectif final

Ces projets ont pour but de démontrer ma compréhension technique et quantitative des problématiques XVA, avec un focus sur la **mesure du risque, le pricing, et la couverture dynamique**. Ils sont conçus pour soutenir ma candidature à un poste de **Trader XVA** ou au sein d’un **CVA Desk**.


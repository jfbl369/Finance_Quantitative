# Calcul Stochastique
## Niveau 1:
- [Calcul stochastique appliqué à la finance - Romuald ELIE & Idris KHARROUBI](https://media.licdn.com/dms/document/media/v2/D561FAQGkpnciH34wow/feedshare-document-pdf-analyzed/B56ZX8NrxWHQAc-/0/1743693225499?e=1745452800&v=beta&t=pkq1tyCMaQfOir1MxrlLLt2LVgJHJKBq2vyjaV9Mt54)



## Niveau 3:
- [CEREMADE - Dauphine: Programmation Dynamique](https://www.ceremade.dauphine.fr/~carlier/progdyn.pdf)
- Nonlinear Option Pricing - Julien Guyon, Pierre Henry-Labordere



# Probabilité
- [Advanced Probability - Alexander Sokol & Anders Rønn-Nielsen](https://media.licdn.com/dms/document/media/v2/D4D1FAQGS4DFnCmZWaQ/feedshare-document-pdf-analyzed/B4DZYXLix0H4AY-/0/1744145684241?e=1745452800&v=beta&t=weTCeC2jQhBsoRznDtf6EL1_B6kLyahVz0w61aKDgeo)



 # 🚀 Projets Python en Finance Quantitative
 
 Bienvenue sur mon portfolio de projets Python appliqués à la finance quantitative.  
 Ces projets sont classés **du plus fondamental au plus avancé**, avec pour objectif de montrer une progression complète vers les compétences attendues en **trading quantitatif**, **modélisation stochastique**, **XVA**, et **pricing avancé**.
 
 ---
 
 ## 🔹 Niveau 1 — Fondations indispensables
 
 ### 1. Mouvement brownien et géométrique
 - Simulation de trajectoires de \( W_t \sim \mathcal{N}(0, t) \)
 - Génération de paths pour le mouvement brownien géométrique \( S_t = S_0 e^{(\mu - \frac{1}{2}\sigma^2)t + \sigma W_t} \)
 - Visualisation graphique dynamique des trajectoires
 
 ### 2. Modèle binomial de Cox-Ross-Rubinstein (1 période puis T périodes)
 - Pricing d’options européennes via arbre binaire
 - Calcul de la mesure risque-neutre
 - Couverture via portefeuille delta-simple
 
 ### 3. Monte Carlo — Pricing d’un call européen
 - Génération de 100 000 trajectoires lognormales
 - Estimation empirique du prix de l’option
 - Comparaison avec la formule de Black-Scholes
 
 ### 4. Vérification empirique de la martingale sous la mesure \( \mathbb{Q} \)
 - Simulation d’espérance conditionnelle
 - Comparaison \( \mathbb{E}^\mathbb{Q}[S_t/(1+r)^t] = S_0 \)
 
 ---
 
 ## 🔹 Niveau 2 — Techniques de pricing
 
 ### 5. Formule de Black-Scholes via Feynman-Kac
 - Simulation de l’espérance sous \( \mathbb{Q} \)
 - Connexion entre EDP et pricing probabiliste
 
 ### 6. Couverture dynamique par delta-hedging
 - Rebalancement du portefeuille dans un environnement discret
 - Analyse des erreurs de couverture selon le pas de temps
 
 ### 7. Backtest d’une stratégie de couverture complète
 - Rebalancement toutes les 24h
 - Ajout de coûts de transaction
 - Analyse du PnL, drawdown et efficacité
 
 ---
 
 ## 🔹 Niveau 3 — Produits dérivés complexes
 
 ### 8. Option barrière up-and-out (binomial)
 - Conditions de knockout implémentées dans l’arbre
 - Pricing par backward induction
 
 ### 9. Options path-dependent (asiatique, lookback)
 - Moyenne glissante \( \bar{S}_T \) ou maximum historique \( \max S_t \)
 - Simulation par Monte Carlo
 
 ### 10. Option américaine (binomial)
 - Résolution rétrograde de l’arbre
 - Implémentation de l’exercice optimal
 - Visualisation de la frontière d’exercice
 
 ---
 
 ## 🔹 Niveau 4 — Marchés incomplets & contrôle stochastique
 
 ### 11. Modèle à volatilité stochastique (type Heston simplifié)
 - Simulation de deux processus corrélés
 - Impact de la corrélation sur le pricing
 
 ### 12. Problème de Merton — Portefeuille optimal
 - Résolution par dualité
 - Simulation de richesse terminale sous \( U(x) = \frac{x^q}{q} \)
 - Implémentation de la stratégie \( \phi_t = \text{proportion optimale de richesse} \)
 
 ### 13. Produit avec taux d’intérêt stochastique (Vasicek)
 - Processus d’Ornstein-Uhlenbeck pour \( r_t \)
 - Pricing via changement de numéraire
 - Implémentation du 0-coupon comme instrument de couverture
 
 ---
 
 ## 🔹 Niveau 5 — Projets premium desk quant / hedge fund
 
 ### 14. Value-at-Risk (VaR)
 - Méthodes : Historique, Paramétrique (normale), Monte Carlo
 - Backtest des violations
 - Construction du plot de Kupiec test
 
 ### 15. Pricer multi-actifs corrélés (modèle Black-Scholes 2D)
 - Matrice de covariance simulée
 - Pricing d’options panier
 - Implémentation de Girsanov multivarié
 
 ### 16. Mini-engine XVA (simplifié)
 - Calcul d’Expected Exposure
 - Pricing avec CVA (Credit Valuation Adjustment)
 - Modélisation du Wrong-Way Risk

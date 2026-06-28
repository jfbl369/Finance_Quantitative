## Le carnet d'ordres

Un carnet a **deux côtés** :
- **Bids** (achats) : prix où des gens veulent *acheter*, triés du plus haut au plus bas.
- **Asks** (ventes) : prix où des gens veulent *vendre*, triés du plus bas au plus haut.

Prix clés :
- **Best bid** = meilleur achat (le plus haut). **Best ask** = meilleure vente (le plus bas).
- **Mid** = (best bid + best ask) / 2 → estimation naïve de la « vraie » valeur.
- **Spread** = best ask − best bid → ce que capte le market-maker.

```
ASKS    100.20  x150
        100.10  x80      <- best ask
        --------------
        99.90   x100     <- best bid
BIDS    99.80   x200
```

- Mid = (99.90 + 100.10)/2 = **100.00**, Spread = **0.20**.

**Règle de matching : price-time priority.** On sert d'abord le meilleur prix ; à prix égal, le premier arrivé (priorité de file FIFO). Poster tôt à un bon prix = être devant dans la queue.

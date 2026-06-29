`deque` se prononce « deck » et veut dire **double-ended queue** — « file à double extrémité » en français.

C'est une structure de la bibliothèque standard Python (`from collections import deque`). Sa particularité : on peut ajouter **et** retirer des éléments **aux deux bouts** (tête et queue) très rapidement, en **O(1)**.

## Pourquoi pas une simple liste ?

Une liste Python (`[]`) est rapide pour ajouter/retirer **à la fin**, mais **lente au début** : retirer le premier élément (`list.pop(0)`) oblige Python à décaler tous les autres d'un cran → O(n).

La `deque`, elle, retire en tête aussi vite qu'en queue. D'où son nom.

```python
from collections import deque

d = deque([10, 20, 30])
d.append(40)        # ajoute à la fin    → deque([10, 20, 30, 40])
d.appendleft(5)     # ajoute au début    → deque([5, 10, 20, 30, 40])
d.popleft()         # retire le premier  → 5   (rapide, O(1))
d.pop()             # retire le dernier  → 40
```

## Le lien avec le carnet d'ordres

C'est exactement ce qu'il faut pour modéliser la **priorité temps** (FIFO — *First In, First Out*).

À un prix donné, les ordres sont servis **dans leur ordre d'arrivée** : le premier arrivé est le premier exécuté. Concrètement :

- **un nouvel ordre arrive** au prix 100.0 → on l'ajoute **en queue** (`append`),
- **un ordre s'exécute** (match) → on prend celui **en tête** (`popleft`), le plus ancien.

```python
self.bids[100.0] = deque([Order(id=0), Order(id=3)])
#                          ^^^^^^^^^^^  arrivé en premier → exécuté en premier
```

Avec une liste classique, le `popleft` lors de chaque exécution serait en O(n) — pénalisant quand un niveau de prix contient des centaines d'ordres. La `deque` garde ça en O(1). C'est le bon outil pour une file d'attente, et un carnet d'ordres *est* une collection de files d'attente (une par prix).

Petit moyen mnémotechnique : pense à une **file d'attente à la boulangerie** où, en plus, on pourrait aussi servir ou faire entrer quelqu'un par l'arrière — les deux bouts sont accessibles instantanément.
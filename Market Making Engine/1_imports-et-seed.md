# Imports & graine aléatoire (cellule de setup)

Avant de coder, on **importe** les modules nécessaires, puis on **fixe le hasard**.

```python
import random
import math
from dataclasses import dataclass, field
from collections import deque

random.seed(42)  # reproductibilité : enlève cette ligne pour du vrai aléa
print('Setup OK')
```

## La boîte à outils, ligne par ligne

### `import random`
Module de **nombres aléatoires**. Sert à *simuler le marché* : le « vrai prix » qui bouge au hasard (`random.gauss`), les noise traders qui achètent/vendent au hasard (`random.choice`, `random.randint`), les quantités aléatoires (`random.uniform`). Sans lui, le marché serait figé.

### `import math`
Les **fonctions mathématiques** de base (`sqrt`, `exp`, `log`…). Peu utilisé au Module 0, mais indispensable plus tard : Black-Scholes (Module 4) a besoin de `exp`, `log`, `sqrt` et de la loi normale. On l'importe d'avance.

### `from dataclasses import dataclass, field`
`dataclass` est un **raccourci** pour créer de petites classes « porte-données » sans code répétitif :

```python
@dataclass
class Order:
    id: int
    side: str
    price: float
    qty: int
```

Python génère tout seul le constructeur, l'affichage, etc. C'est la « petite fiche » `Order`. (`field` est importé pour plus tard, si on veut des valeurs par défaut complexes — pas encore utilisé.)

### `from collections import deque`
La **file d'attente FIFO** (« dèque »). Range les ordres au même prix avec la priorité temps : on ajoute à droite (`.append`), on sert à gauche (`.popleft`). C'est le cœur de la priorité **prix-temps**.

## `random.seed(42)` — la reproductibilité

Le hasard d'un ordinateur est *pseudo-aléatoire* : une suite calculée à partir d'un point de départ, la **graine** (seed). En la fixant à `42`, **chaque exécution produit exactement la même suite** de nombres « au hasard ».

Pourquoi ? Pour **déboguer** : si le bot fait −500 € au tick 237, on peut rejouer la *même* partie autant de fois que nécessaire. Sans graine fixe, chaque run serait différent et impossible à reproduire.

> Le `42` est arbitraire (clin d'œil geek) ; n'importe quel entier marche. Enlève la ligne pour du vrai hasard à chaque run.

## `print('Setup OK')`
Une **confirmation visuelle** que la cellule s'est exécutée sans erreur. Si tu vois `Setup OK`, les imports sont bons.

## En résumé
On déballe 4 outils — `random` (vie du marché), `math` (formules), `dataclass` (fiches), `deque` (files) — on fige le hasard pour rejouer à l'identique, et on affiche un témoin.

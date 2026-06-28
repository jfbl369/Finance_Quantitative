« fill » est un mot de jargon trading. Voici ce qu'il veut dire.

## Un « fill » = une exécution

Un **fill**, c'est le compte-rendu d'un ordre qui **a été exécuté** (« rempli »). Quand un ordre marché vient consommer des fiches du carnet, chaque fiche touchée génère un fill : « telle fiche a été servie, à tel prix, pour telle quantité ».

C'est le **reçu de la transaction**. Mon `print` dit littéralement « voici qui a été servi par cet ordre marché ».

## On décode la ligne affichée

```
Fills (qui a ete servi) : [(0, 'noise', 99.9, 100), (1, 'noise', 99.9, 20)]
```

Rappel du contexte : quelqu'un a envoyé un **sell marché de 120** → ça tape les BIDS (les acheteurs), meilleur prix d'abord (99.90), où la file était `[ #0(x100) -> #1(x50) ]`.

C'est une **liste de 2 fills** (2 fiches touchées). Chaque fill est un tuple de 4 champs :

| | `order_id` | `owner` | `price` | `qty` |
|---|---|---|---|---|
| Fill 1 | `0` | `'noise'` | `99.9` | `100` |
| Fill 2 | `1` | `'noise'` | `99.9` | `20` |

- **`order_id`** : quelle fiche a été touchée (`#0` puis `#1`).
- **`owner`** : à qui appartenait la fiche (`'noise'` ou `'bot'`).
- **`price`** : à quel prix la transaction s'est faite (99.90).
- **`qty`** : combien d'unités de cette fiche ont été consommées.

**Lecture en français :** « les 120 à vendre ont d'abord vidé `#0` (100 unités à 99.90), puis pris 20 unités sur `#1` (qui passe de 50 à 30). Total servi = 100 + 20 = 120. ✅ »

## Pourquoi ce champ `owner` est crucial

C'est exactement ce qui sert dans la boucle de simulation (section 5). Quand un ordre marché tape le carnet, **ton bot a besoin de savoir si c'est *lui* qui a été exécuté** : il regarde `owner == 'bot'` dans la liste des fills, et si oui il met à jour son inventaire et son cash via `on_fill`. Sans le fill, le bot ne saurait jamais qu'il vient d'acheter ou de vendre.

> En résumé : `add_limit_order` te donne un **reçu de dépôt** (un `id`), et `match_market_order` te renvoie des **reçus d'exécution** (des fills). C'est le vocabulaire standard que tu retrouveras tel quel dans le SDK d'Akuna.
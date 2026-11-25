# Ruleset du moteur

## Référence par défaut

Le moteur implémente le Mille Bornes Classique Dujardin, édition 2025,
référence produit `1130300292`. La notice décrit une course de 2 à 4 joueurs,
une main initiale de 6 cartes, un objectif de 1 000 km et un maximum de deux
cartes 200 km. Les règles de cette édition n'exigent pas de Feu Vert pour poser
la première carte Borne ; après un danger, la Parade correspondante suffit à
repartir.

L'identifiant de règles persisté est `mille-bornes-v1`, aligné sur le champ
`Game.ruleset_version` déjà présent côté Django. Une évolution incompatible des
règles ou du catalogue devra créer une nouvelle version au lieu de réinterpréter
les snapshots existants.

La même notice propose séparément le jeu en équipes de 2 pour 4 à 8 personnes.
Cette variante d'équipe n'est pas implémentée ici : le périmètre demandé est
de 2 à 4 joueurs individuels, avec une zone et un score par siège.

Le sabot contient 106 cartes jouables. Les 4 cartes mémo sont des aides de jeu,
pas des cartes à distribuer :

| Famille | Cartes | Quantités |
|---|---|---|
| Bornes | 25, 50, 75, 100, 200 km | 10, 10, 10, 12, 4 |
| Attaques | Limite de vitesse, Feu rouge, Panne d'essence, Crevaison, Accident | 4, 5, 3, 3, 3 |
| Parades | Fin de limite, Feu vert, Essence, Roue de secours, Réparations | 6, 14, 6, 6, 6 |
| Bottes | Véhicule prioritaire, Citerne, Increvable, As du volant | 1 chacune |

Le Coup-Fourré est une réponse immédiate à l'attaque correspondante : la Botte
neutralise le danger, le joueur pioche pour reconstituer sa main puis pioche
pour rejouer immédiatement. Le barème de l'édition 2025 ne donne pas de points
bonus chiffrés pour le Coup-Fourré ; le score de base exposé par le moteur est
donc la distance parcourue en kilomètres.

La partie s'arrête dès qu'un joueur atteint exactement 1 000 km. Si le sabot ne
contient plus de carte Borne à la fin d'une action qui termine un tour (ou d'une
fenêtre de réponse), le joueur ou les joueurs ayant parcouru le plus de
kilomètres gagnent. En cas d'égalité, le moteur conserve tous les gagnants.

## Variantes configurables

`RulesConfig` permet notamment de :

- demander un Feu Vert avant la première carte Borne (`start_requires_green_light`) ;
- demander un Feu Vert après une réparation (`require_green_after_repair`) ;
- désactiver la fin lorsque le sabot n'a plus de carte Borne ;
- autoriser la défausse volontaire lorsqu'une autre carte est jouable ;
- modifier l'objectif, la limite, la taille initiale de main et le nombre maximal
  de cartes 200 km.

Par défaut, les paramètres correspondent à l'édition 2025 : départ sans Feu
Vert, pas de Feu Vert supplémentaire après une réparation, fin lorsque le
sabot n'a plus de Bornes, défausse seulement si aucune carte n'est jouable.
Le moment du test de fin par épuisement est une décision d'implémentation : il
est évalué à la fin du tour/réponse afin que le joueur puisse terminer son
action en cours.

La notice 2025 ne définit ni barème cumulatif détaillé ni départage en cas
d'égalité au kilométrage. Le moteur n'invente pas de bonus ou de départage ;
les scores retournés sont des kilomètres et les égalités sont des ex æquo.

# Moteur Mille Bornes

Ce paquet ne dépend que de la bibliothèque standard Python. Il n'importe ni
Django, ni DRF, ni Channels et peut être appelé par les services REST, le
consumer WebSocket ou le bot solo.

## Usage minimal

```python
from domain.game_engine import ActionType, apply_action, new_game, state_to_dict

state = new_game(["participant-1", "participant-2"])
drawn = apply_action(state, player_id="participant-1", action=ActionType.DRAW)
state = drawn.state

# Une commande reçue du client ne contient qu'une intention. Le moteur vérifie
# le joueur actif, la carte réellement en main, la cible et les règles.
transition = apply_action(
    state,
    player_id="participant-1",
    action=ActionType.PLAY,
    card_id="identifiant-de-carte",
)
server_snapshot = state_to_dict(transition.state)
```

`legal_plays(state, player_id)` peut alimenter l'interface ou l'IA, mais cette
liste n'est jamais une autorisation : chaque commande passe encore par
`apply_action`. Une commande invalide lève `RuleViolation` (avec un code stable)
et ne modifie pas l'état fourni.

## Intégration Django prévue

Le service de `apps.games` doit charger **l'état persistant** de `Game.state`,
reconstruire le `GameState` avec `state_from_dict`, et dériver l'identifiant du
joueur de l'utilisateur authentifié et de son siège. Il appelle ensuite
`apply_action`, sérialise le nouvel état avec `state_to_dict`, écrit snapshot,
événements et version dans une transaction, puis diffuse après commit.

Le client ne doit jamais envoyer un snapshot à appliquer, un kilométrage à
enregistrer, ni un indicateur « action légale ». Seuls les identifiants de
commande/carte/cible sont recevables, et ils sont tous revalidés à partir de
l'état chargé depuis PostgreSQL. L'état complet contient les mains et la
pioche : ne pas le sérialiser directement vers un joueur. Construire une
projection par participant et ne transmettre que sa main ; les événements
`card.drawn` sont marqués comme privés pour le joueur concerné.

`new_game(..., seed=...)` et `new_game(..., deck=...)` facilitent les tests et
simulations reproductibles. En production, omettre ces paramètres pour
mélanger le sabot avec le générateur système.

Voir [RULESET.md](RULESET.md) pour le ruleset et les choix de variante.

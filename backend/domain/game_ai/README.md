# Intelligence artificielle Mille Bornes

Ce paquet Python pur utilise le moteur de `domain.game_engine`. Il ne dépend
pas de Django, de DRF, de Channels ni du frontend.

## Décision et confidentialité

`build_observation(state, bot_id)` transforme l'état serveur en observation
limitée : la main du bot, les plateaux publics, les tailles de main et le nombre
de cartes restantes dans la pioche. La stratégie ne reçoit ni les mains
adverses, ni les identités des cartes de la pioche. Elle reçoit également les
coups jouables produits par `legal_plays`; ce sont des suggestions, pas une
autorisation.

Chaque décision est convertie en commande et passe immédiatement par
`apply_action`. Le moteur reste l'autorité et valide à nouveau le tour, la carte,
la cible, les dangers et toutes les règles.

## Difficultés

- **Facile** : choisit aléatoirement parmi les commandes légales.
- **Normale** : privilégie les kilomètres, les réparations et les attaques
  contre les adversaires en tête ; elle évite de défausser les cartes utiles.
- **Difficile** : ajoute la pression de course, l'urgence de fin de partie et
  une estimation du risque de Coup-Fourré à partir des seules cartes visibles,
  tailles de main et cartes inconnues.

Les classes de stratégie peuvent être étendues ou remplacées dans
`strategies.py`. Toute nouvelle stratégie doit consommer `GameObservation` et les
coups candidats, jamais `GameState`.

## Tour automatique et délai

Après chaque commande qui modifie l'état, le service de partie appelle
`drive_automatic_turn` avec sa table serveur des participants-bots. Le
dispatcher laisse les tours humains inchangés et lance le bon bot quand un bot
est actif ou doit répondre à une attaque. Le runner joue la pioche, les actions
et les réponses Coup-Fourré jusqu'à ce que le bot n'ait plus la main.
`AIConfig.thinking_delay_seconds` permet de régler le délai ; `on_transition`
permet à l'application de persister et diffuser chaque transition. Comme le
runner est asynchrone, le délai ne bloque pas la boucle d'événements Channels.

```python
import asyncio

from domain.game_ai import AIConfig, Difficulty, drive_automatic_turn

state = asyncio.run(
    drive_automatic_turn(
        state,
        {
            bot_id: AIConfig(
                difficulty=Difficulty.HARD,
                thinking_delay_seconds=0.8,
                seed=1234,
            )
        },
    )
)
```

Les tests règlent le délai à zéro et injectent une graine ou un générateur
`random.Random` pour rendre les choix reproductibles.

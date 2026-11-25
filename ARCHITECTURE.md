# Architecture — jeu de cartes en ligne inspiré de Mille Bornes

## 1. État du workspace et périmètre

À l’étape d’architecture initiale, le workspace ne contenait aucun code source ni fichier de projet. Le backend Django, le paquet indépendant `backend/domain/game_engine/` et le multijoueur Channels/Redis ont depuis été ajoutés. Les salons, snapshots privés, commandes de partie, reconnexion, présence, abandon et résultats sont branchés aux services transactionnels. L’intégration automatique du bot solo et son interface de commandes restent distinctes.

Le jeu sera une application web responsive avec :

- des parties solo contre des bots ;
- des parties en ligne de 2 à 4 joueurs et des salons privés rejoints par code ;
- des comptes, un historique et des statistiques ;
- un moteur de jeu faisant autorité côté serveur.

**Hypothèse de départ :** une partie occupe de 2 à 4 sièges. En solo, un siège est humain et les autres sont des bots ; en multijoueur, les sièges sont humains. Le ruleset par défaut Dujardin Classique 2025 et ses variantes configurables sont documentés dans `backend/domain/game_engine/RULESET.md`; les règles et choix de score sont sérialisables avec la partie.

## 2. Architecture générale

Monorepo à deux applications, avec PostgreSQL comme source de vérité durable et Redis pour les fonctions temps réel éphémères.

```text
Navigateur
  React / TypeScript
      │ HTTPS : comptes, salons, historique, statistiques, snapshots
      ▼
  Django REST Framework ───── PostgreSQL
      │                           ▲
      │ WebSocket                 │ état et événements persistés
      ▼                           │
  Django Channels ──────────── Redis
      │
      └── services applicatifs ── moteur de jeu pur Python
```

Principes structurants :

1. **Le serveur est autoritaire.** Le navigateur affiche l’état et envoie des intentions (« jouer cette carte »), jamais un nouvel état calculé par le client.
2. **Le moteur de règles est indépendant de Django.** Il reçoit un état et une commande, vérifie la légalité, puis retourne une transition déterministe. Il est testable sans base de données ni WebSocket.
3. **REST et WebSocket appellent les mêmes services applicatifs.** Cela évite des règles différentes entre solo, multijoueur et reconnexion.
4. **Redis n’est pas la source de vérité.** Il sert au channel layer, à la présence et aux tickets WebSocket temporaires. Une reconnexion reconstruit l’affichage depuis PostgreSQL.
5. **Chaque joueur ne reçoit que sa projection d’état.** Les mains adverses, la pioche et les données internes du bot ne sont jamais envoyées dans un message global.

### Authentification et temps réel

DRF fournit l’API et des JWT (par exemple avec SimpleJWT). Le jeton de renouvellement devrait être conservé dans un cookie `HttpOnly`, `Secure` en production, avec protection CSRF ; le jeton d’accès reste en mémoire côté navigateur.

Le navigateur ne pouvant pas définir librement un en-tête `Authorization` lors d’une connexion WebSocket native, l’API délivre un **ticket WebSocket à usage unique et de courte durée**. Le client l’échange pour ouvrir la socket ; on évite ainsi de placer un JWT durable dans l’URL. Le ticket et la socket sont vérifiés avant d’autoriser l’accès au groupe d’une partie.

Pour une action, le client envoie un `request_id` et la `state_version` qu’il a observée. Le service verrouille la partie dans une transaction, valide la version et l’action, persiste l’état et l’événement, puis publie la mise à jour via `transaction.on_commit`. Une commande répétée est idempotente ; une version périmée provoque un refus et l’envoi d’un snapshot récent.

## 3. Modèle de données proposé

Les identifiants principaux seront des UUID. Les contraintes d’unicité, clés étrangères et index seront définis avec les modèles Django.

| Entité | Rôle et données principales |
|---|---|
| `User` | Utilisateur personnalisé : email normalisé et unique, nom d’affichage, mot de passe Django, dates et état du compte. |
| `Game` | Une salle et sa partie persistante : propriétaire, mode (`solo`/`multiplayer`), état (`waiting`/`active`/`finished`/`cancelled`), capacité de 2–4 sièges, `ruleset_version`, `state_version`, horodatages, snapshot JSONB. Pour un salon privé, stocker le condensat du code d’invitation et son expiration, pas le code en clair. |
| `GameParticipant` | Siège d’une partie : utilisateur nullable pour un bot, numéro de siège, type (`human`/`bot`), difficulté du bot, résultat et score final. Contraintes : un siège par partie, un utilisateur au plus une fois par partie. |
| `GameEvent` | Journal append-only : partie, numéro de séquence, acteur, `request_id` client pour l’idempotence, type, charge utile publique, charges utiles privées par participant et date. Une contrainte unique sur la partie, l’acteur et le `request_id` empêche de rejouer une commande acceptée ; les charges utiles privées sont projetées avant toute réponse client. |
| `PlayerStats` | Agrégat recalculable par utilisateur : parties terminées, victoires, scores cumulés/meilleurs et date de mise à jour. Les résultats des parties terminées restent la source de vérité. |

Le catalogue des cartes et leurs quantités sont des **données de règles versionnées dans le code**, et non des lignes modifiables par les joueurs. Le snapshot JSONB contient l’état privé complet nécessaire à la reprise (mains, pioche, défausse, état de route, tour, etc.) ; il n’est jamais sérialisé directement vers le client. Les événements distinguent explicitement contenu public et contenu privé.

Le code d’invitation sera aléatoire, suffisamment difficile à deviner, limité par expiration/capacité et protégé contre les tentatives répétées. Il donne accès à un salon, mais ne remplace pas l’authentification.

## 4. Applications Django et responsabilités

| Application / paquet | Responsabilités |
|---|---|
| `config` | Settings par environnement, configuration DRF/Channels, `urls.py`, ASGI, routage et initialisation du channel layer Redis. |
| `apps.accounts` | Modèle utilisateur, inscription, profil, endpoints JWT, paramètres et permissions liées au compte. |
| `apps.games` | Modèles `Game`, `GameParticipant`, `GameEvent` ; création/rejointure de salons, codes privés, démarrage, actions, snapshots et finalisation. Les vues REST et consumers délèguent à ses services applicatifs. |
| `domain.game_engine` | Paquet Python pur : cartes, règles versionnées, transitions, actions légales, calcul du score et tests de règles. Aucune dépendance à Django, Redis ou Channels. |
| `domain.ai` | Stratégie déterministe/heuristique des bots, appelée par les mêmes services et soumise aux mêmes validations que les joueurs. Pas de décision de jeu dans le client. |
| `apps.realtime` | Consumers Channels, autorisation de socket, ticket à usage unique, groupes par partie, présence et diffusion des événements. N’implémente pas les règles. |
| `apps.statistics` | API d’historique et statistiques ; agrégats mis à jour de façon idempotente à la fin d’une partie et reconstruisibles depuis les résultats. |

## 5. Structure de dossiers cible

```text
.
├── ARCHITECTURE.md
├── README.md
├── docker-compose.yml             # PostgreSQL, Redis, services de développement
├── .env.example
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/                    # Router, providers, configuration
│       ├── features/
│       │   ├── auth/
│       │   ├── lobby/              # Création/rejointure de salon
│       │   ├── game/               # Plateau, main, actions, socket
│       │   ├── history/
│       │   └── profile/
│       ├── shared/                 # UI, Axios, types, utilitaires
│       └── main.tsx
├── backend/
│   ├── manage.py
│   ├── pyproject.toml
│   ├── config/                     # settings, urls, asgi
│   ├── apps/
│   │   ├── accounts/
│   │   ├── games/
│   │   ├── realtime/
│   │   └── statistics/
│   ├── domain/
│   │   ├── game_engine/
│   │   └── ai/
│   └── tests/
└── docs/
    ├── ruleset.md                  # Règles et variantes retenues
    └── api.md
```

Le frontend utilisera React, TypeScript, Vite, Tailwind CSS, React Router et Axios. Zustand est retenu pour l’état d’interface partagé et l’état de socket/partie côté client ; il ne sera pas une seconde source de vérité métier. Les écrans et composants seront organisés par fonctionnalité.

Le backend utilisera Python, Django, Django REST Framework, Django Channels, Redis, PostgreSQL et JWT. Les versions, dépendances exactes, migrations et commandes de développement seront fixées lors de l’étape de bootstrap.

## 6. Fonctionnalités et dépendances

| Fonctionnalité | Dépend de |
|---|---|
| Inscription, connexion, profil | `accounts`, PostgreSQL, JWT, validation et limitation de débit |
| Création/jointure par invitation | Authentification, `games`, génération/expiration de code, places disponibles |
| Règles, tour, score et fin de partie | `domain.game_engine`, catalogue et version du ruleset |
| Partie solo contre IA | Moteur, sièges bot, `domain.ai`, persistance et interface de jeu |
| Multijoueur live (2–4) | Salons/participants, moteur, Channels, Redis, contrôle de concurrence et projection privée |
| Reconnexion/reprise | Snapshot PostgreSQL, `state_version`, journal d’événements et ticket/socket réauthentifiée |
| Historique et statistiques | Résultats persistés, finalisation idempotente, endpoints `statistics` |
| Interface responsive | Design system Tailwind, routes React, états de chargement/erreur/hors ligne et accessibilité |

## 7. Plan de développement

1. **Décisions produit et règles** — le ruleset par défaut est confirmé dans `backend/domain/game_engine/RULESET.md`. Les choix de format d'équipes, durée des tours et comportement des bots restent à confirmer.
2. **Socle du monorepo** — initialiser Vite/React/TypeScript/Tailwind et Django, configuration d’environnement, Docker Compose PostgreSQL/Redis, contrôles de santé, lint et tests de base.
3. **Comptes et contrats API** — utilisateur personnalisé, JWT, cookie de renouvellement sécurisé, profil, conventions d’erreur et tests d’API.
4. **Moteur de jeu (implémenté)** — catalogue, état, actions légales, transitions, scoring distance et tests unitaires pytest ; reste à faire l'intégration avec les services de partie.
5. **Salons et persistance** — modèles/migrations, création et jointure par code, capacité, transactions, snapshots et journal.
6. **Tranche verticale solo** — plateau responsive, actions REST au départ, bot heuristique, résultat sauvegardé ; valider l’expérience et les règles avant de généraliser.
7. **Multijoueur temps réel (implémenté)** — tickets WebSocket, Channels/Redis, commandes versionnées/idempotentes, projections privées, présence, reconnexion, abandon et tests des consommateurs/services.
8. **Historique et statistiques** — liste/détail de parties, agrégats, pagination et tests d’idempotence.
9. **Durcissement et livraison** — tests end-to-end, sécurité des salons, rate limiting, observabilité, migrations de production, sauvegardes PostgreSQL et déploiement.

Chaque étape doit livrer des tests adaptés : règles en tests unitaires purs, services avec tests transactionnels, endpoints avec tests API, puis flux WebSocket et scénarios navigateur. Le lancement de la phase 2 dépend de la validation du ruleset ; le multijoueur dépend du moteur et du cycle salon/partie, pas d’une réimplémentation des règles dans React.

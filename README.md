# Mille Bornes — backend

Le backend Django fournit les comptes, les salons et leur cycle de vie, l’historique/statistiques et le multijoueur temps réel avec Django Channels et Redis. Le moteur pur de règles dans `backend/domain/game_engine/` valide les commandes côté serveur ; l’état complet reste en base et chaque socket reçoit une projection qui masque les mains adverses. Le mode solo conserve ses routes existantes et initialise le même état moteur, tandis que les commandes WebSocket sont réservées aux parties multijoueur.

## Démarrage avec Docker

Prérequis : Docker avec le plugin Compose.

```bash
cp .env.example .env
# Remplacer DJANGO_SECRET_KEY et les mots de passe dans .env.
docker compose up --build
```

## Tester le moteur de jeu

Depuis `backend/`, installez les dépendances de développement et exécutez les
tests du domaine sans démarrer Django, PostgreSQL ou Redis :

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/test_game_engine.py
```

Le ruleset par défaut et ses variantes sont décrits dans
[`backend/domain/game_engine/RULESET.md`](backend/domain/game_engine/RULESET.md).

L’API est disponible sur `http://localhost:8000/api/v1/`. Au démarrage local, le conteneur applique les migrations puis lance Daphne (HTTP + WebSocket).

Créer un compte administrateur :

```bash
docker compose exec api python manage.py createsuperuser
```

## Endpoints

Toutes les routes ci-dessous sont préfixées par `/api/v1/`.

| Méthode | Route | Accès / rôle |
|---|---|---|
| `GET` | `health/` | Santé du service |
| `GET` | `auth/csrf/` | Initialise le cookie CSRF pour les appels navigateur |
| `POST` | `auth/register/` | Créer un compte |
| `POST` | `auth/login/` | Connexion ; renvoie un access JWT et pose un refresh HttpOnly |
| `POST` | `auth/refresh/` | Renouveler l’access JWT avec le cookie refresh |
| `POST` | `auth/logout/` | Révoquer le refresh et supprimer son cookie |
| `GET`, `PATCH` | `auth/me/` | Lire ou modifier son nom d’affichage |
| `GET`, `POST` | `games/` | Lister les salons publics disponibles / créer un salon |
| `GET` | `games/mine/` | Lister ses propres parties |
| `GET` | `games/{id}/` | Détail ; une partie privée est réservée à ses participants |
| `POST` | `games/{id}/join/` | Rejoindre ; le code est requis pour un salon privé |
| `POST` | `games/{id}/leave/` | Quitter un salon en attente ; l’hôte est transféré |
| `PATCH` | `games/{id}/ready/` | Modifier son état prêt/non prêt |
| `POST` | `games/{id}/start/` | Démarrer (hôte uniquement, joueurs humains prêts) |
| `POST` | `games/{id}/ws-ticket/` | Obtenir un ticket WebSocket bref et à usage unique |
| `GET` | `history/` | Historique personnel des parties terminées |
| `GET` | `stats/me/` | Statistiques personnelles |

Les réponses utilisent JSON. Les actions de salon et de jeu sont atomiques et journalisées. Le WebSocket est authentifié par ticket bref à usage unique ; il transmet un snapshot à la connexion/reconnexion, la présence, les événements et les coups multijoueur validés par le moteur. Un abandon pendant une partie annule la course tout en conservant son état. Les codes d’invitation ne sont stockés qu’en condensat et ne sont renvoyés qu’à la création.

## Exemple de parcours API

1. `POST /auth/register/` avec `{"email":"joueur@example.com","display_name":"Joueur","password":"..."}`.
2. Pour un navigateur, appeler `GET /auth/csrf/` avec les cookies activés ; conserver le cookie `csrftoken` et envoyer sa valeur dans l’en-tête `X-CSRFToken` pour login/refresh/logout.
3. `POST /auth/login/` avec email/mot de passe. Garder l’`access` renvoyé en mémoire ; le cookie `refresh_token` est HttpOnly.
4. Sur les appels protégés, envoyer `Authorization: Bearer <access>`.
5. `POST /games/` avec `{"mode":"multiplayer","visibility":"private","max_players":4}`. Copier le `invite_code` renvoyé : il n’est pas récupérable ensuite.
6. Les autres joueurs appellent `POST /games/{id}/join/` avec `{"invite_code":"..."}`. Chacun peut appeler `PATCH /games/{id}/ready/` avec `{"is_ready":true}` ; l’hôte appelle ensuite `POST /games/{id}/start/`.

Pour le WebSocket, appeler `POST /games/{id}/ws-ticket/`, puis ouvrir le chemin renvoyé en ajoutant `?ticket=<ticket>`. Le ticket expire rapidement et ne peut être consommé qu’une fois. Le serveur envoie `lobby.snapshot` dans un salon et `game.snapshot` pendant une partie ; les changements sont envoyés sous `game.event`. Les commandes de partie utilisent `game.action` avec `request_id`, `state_version`, `action` (`draw`, `play`, `discard` ou `pass`) et, si nécessaire, `card_id`/`target_player_id`. Un abandon est envoyé avec `game.abandon`. En cas de version périmée, le serveur renvoie une erreur et un snapshot à jour.

Exemple `curl` minimal (remplacer les valeurs et recopier le `csrfToken`, l’`access` et le code d’invitation renvoyés) :

```bash
curl -i http://localhost:8000/api/v1/health/

# Inscription
curl -i -X POST http://localhost:8000/api/v1/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"joueur@example.com","display_name":"Joueur","password":"Valid-password-481!Card"}'

# Obtenir le cookie et le jeton CSRF
curl -s -c /tmp/mille-bornes-cookies.txt \
  http://localhost:8000/api/v1/auth/csrf/

# Connexion : envoyer la valeur csrfToken dans X-CSRFToken
curl -i -X POST http://localhost:8000/api/v1/auth/login/ \
  -b /tmp/mille-bornes-cookies.txt -c /tmp/mille-bornes-cookies.txt \
  -H 'Content-Type: application/json' \
  -H 'X-CSRFToken: <csrfToken>' \
  -d '{"email":"joueur@example.com","password":"Valid-password-481!Card"}'

# Créer un salon privé avec le jeton access renvoyé par login
curl -i -X POST http://localhost:8000/api/v1/games/ \
  -H 'Authorization: Bearer <access>' \
  -H 'Content-Type: application/json' \
  -d '{"mode":"multiplayer","visibility":"private","max_players":4}'

# Consulter son profil
curl -i http://localhost:8000/api/v1/auth/me/ \
  -H 'Authorization: Bearer <access>'
```

## Tests et commandes utiles

Avec les services Compose lancés :

```bash
docker compose exec api python manage.py check
docker compose exec api python manage.py test
docker compose exec api python manage.py makemigrations --check --dry-run
```

Pour un démarrage local sans Docker, installer `backend/requirements.txt`, lancer PostgreSQL et Redis, puis définir les variables de `.env.example` (notamment les hôtes `127.0.0.1`) avant `python backend/manage.py migrate` et `daphne -p 8000 --bind 127.0.0.1 config.asgi:application` depuis `backend/`.

**Production :** remplacer les secrets de développement, définir `DJANGO_DEBUG=false`, activer les cookies Secure et HTTPS, ajuster les origines CORS/CSRF, et exécuter les migrations comme étape de déploiement contrôlée plutôt qu’à chaque démarrage de worker.

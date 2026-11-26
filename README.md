# Mille Bornes - Jeu de Cartes en Ligne

Mille Bornes est un jeu de cartes classique français développé avec **React** (frontend), **Django** (backend), **PostgreSQL** (base de données), **Redis** (cache/WebSockets) et **Nginx** (reverse proxy).

## 🚀 Démarrage Rapide

### Prérequis
- Docker 24+ et Docker Compose 2+
- 2 GB RAM minimum
- Ports 80, 443, 5173, 8000, 5432, 6379 disponibles

### Installation en Production

```bash
# 1. Cloner le dépôt
git clone <repository-url>
cd 1kb

# 2. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos valeurs (IMPORTANT: changer tous les mots de passe!)

# 3. Générer les certificats SSL (auto-signés pour test, ou utiliser Let's Encrypt)
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem \
  -subj "/CN=yourdomain.com"

# 4. Lancer les services
docker compose up -d --build

# 5. Vérifier les logs
docker compose logs -f
```

### Développement Local

```bash
# 1. Configurer l'environnement de développement
cp .env.development .env

# 2. Lancer avec hot-reloading
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d --build

# 3. Accéder à l'application
# Frontend: http://localhost:5173
# API: http://localhost:8000/api/v1/
# Admin Django: http://localhost:8000/admin/
```

## 📁 Structure du Projet

```
1kb/
├── backend/                 # Django API
│   ├── apps/
│   │   ├── accounts/       # Authentification JWT
│   │   ├── games/          # Logique de jeu, parties
│   │   ├── realtime/       # WebSockets (Django Channels)
│   │   └── statistics/     # Stats & Leaderboard
│   ├── config/             # Settings Django
│   ├── domain/             # Moteur de jeu pur (Python)
│   │   ├── game_engine/    # Règles, état, transitions
│   │   └── game_ai/        # IA pour mode solo
│   ├── Dockerfile          # Image production
│   └── requirements.txt
├── frontend/               # React + Vite
│   ├── src/
│   │   ├── features/       # Pages & composants
│   │   ├── shared/         # API, types, composants UI
│   ├── nginx.conf          # Config nginx (prod)
│   ├── Dockerfile          # Image production
│   └── Dockerfile.dev      # Image développement
├── nginx/                  # Reverse proxy production
│   ├── nginx.conf
│   ├── proxy_params
│   └── ssl/                # Certificats SSL
├── init-scripts/           # Scripts d'init PostgreSQL
├── docker-compose.yml      # Production
├── docker-compose.override.yml  # Développement
├── .env.example            # Template variables
├── .env.development        # Variables dev
└── README.md
```

## 🔧 Configuration

### Variables d'Environnement Principales

| Variable | Description | Défaut | Requis |
|----------|-------------|--------|--------|
| `DJANGO_SECRET_KEY` | Clé secrète Django (50+ chars) | - | **Oui** |
| `DJANGO_DEBUG` | Mode debug | `false` | Non |
| `DJANGO_ALLOWED_HOSTS` | Hosts autorisés (CSV) | `localhost,127.0.0.1` | Non |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | - | **Oui** |
| `POSTGRES_DB` | Nom de la base | `millebornes` | Non |
| `POSTGRES_USER` | Utilisateur PostgreSQL | `millebornes` | Non |
| `FRONTEND_ORIGINS` | Origines CORS (CSV) | `http://localhost:5173` | Non |
| `CSRF_TRUSTED_ORIGINS` | Origins CSRF (CSV) | `http://localhost:5173` | Non |
| `REDIS_URL` | URL Redis | `redis://redis:6379/0` | Non |

### Génération de Secrets

```bash
# Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# PostgreSQL password
openssl rand -base64 32

# JWT signing (utilise DJANGO_SECRET_KEY)
```

## 🐳 Commandes Docker Utiles

### Gestion des Services
```bash
# Démarrer en production
docker compose up -d

# Démarrer en développement (avec hot-reload)
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d

# Arrêter
docker compose down

# Arrêter + supprimer volumes (⚠️ perte données)
docker compose down -v

# Redémarrer un service
docker compose restart api

# Voir les logs
docker compose logs -f api
docker compose logs -f --tail=100 postgres
```

### Base de Données
```bash
# Migrations
docker compose exec api python manage.py migrate

# Créer migration
docker compose exec api python manage.py makemigrations

# Superuser Django
docker compose exec api python manage.py createsuperuser

# Shell Django
docker compose exec api python manage.py shell

# Backup PostgreSQL
docker compose exec postgres pg_dump -U millebornes millebornes > backup.sql

# Restore
docker compose exec -T postgres psql -U millebornes millebornes < backup.sql
```

### Cache & Redis
```bash
# Vider le cache Redis
docker compose exec redis redis-cli FLUSHALL

# Info Redis
docker compose exec redis redis-cli INFO
```

### Frontend
```bash
# Build production local
cd frontend && pnpm run build

# Preview build
cd frontend && pnpm run preview

# Type checking
cd frontend && pnpm run typecheck
```

## 🌐 Architecture Réseau

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│    Nginx    │────▶│   Frontend  │
│  (Browser)  │     │  (SSL/Proxy)│     │  (React)    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌─────────┐ ┌──────────┐ ┌──────────┐
         │  API    │ │  Redis   │ │PostgreSQL│
         │ (Django)│ │(Cache/WS)│ │  (Data)  │
         └─────────┘ └──────────┘ └──────────┘
```

### Ports
| Service | Port Interne | Port Externe (Prod) | Port Externe (Dev) |
|---------|-------------|---------------------|-------------------|
| Nginx   | 80, 443     | 80, 443             | -                 |
| Frontend| 80          | via Nginx           | 5173              |
| API     | 8000        | via Nginx           | 8000              |
| PostgreSQL| 5432      | -                   | 5432              |
| Redis   | 6379        | -                   | 6379              |

## 🔐 Sécurité

### Production
- ✅ HTTPS obligatoire (Nginx + SSL)
- ✅ Cookies Secure + HttpOnly + SameSite=Lax
- ✅ CSRF protection
- ✅ CORS restrictif
- ✅ Rate limiting (API + Auth)
- ✅ Headers de sécurité (HSTS, CSP, X-Frame-Options)
- ✅ Utilisateur non-root dans containers
- ✅ Secrets via variables d'environnement

### Authentification
- JWT Access Token (15 min) + Refresh Token (7 jours, rotation)
- Blacklist des tokens révoqués
- Mots de passe hashés (PBKDF2 Django)

## 🧪 Tests

```bash
# Backend tests
docker compose exec api python -m pytest tests/ -v
docker compose exec api python manage.py test

# Frontend tests (si configurés)
cd frontend && pnpm run test
```

## 📊 Monitoring & Logs

```bash
# Health checks
curl https://yourdomain.com/health
curl https://yourdomain.com/api/health

# Logs structurés
docker compose logs --since=1h api | jq .

# Métriques Redis
docker compose exec redis redis-cli INFO stats
```

## 🔄 Déploiement Continu (CI/CD)

Exemple GitHub Actions :
```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build & Push
        run: |
          docker compose -f docker-compose.yml build
          docker compose -f docker-compose.yml push
      - name: Deploy to server
        run: ssh user@server "cd /app && docker compose pull && docker compose up -d"
```

## 🐛 Dépannage

### Problèmes Courants

| Problème | Solution |
|----------|----------|
| `Connection refused` PostgreSQL | Attendre healthcheck, vérifier `POSTGRES_PASSWORD` |
| `CSRF Failed` | Vérifier `CSRF_TRUSTED_ORIGINS` et `FRONTEND_ORIGINS` |
| WebSocket ne connecte pas | Vérifier proxy Nginx `/ws/` et `VITE_WS_BASE_URL` |
| Migrations échouent | `docker compose exec api python manage.py migrate --fake-initial` |
| Static files 404 | `docker compose exec api python manage.py collectstatic --noinput` |

### Logs de Debug
```bash
# Activer debug Django
docker compose exec api python -c "import os; os.environ['DJANGO_DEBUG']='true'"

# Vérifier config Django
docker compose exec api python manage.py check --deploy
```

## 📝 Licence

Ce projet est sous licence MIT. Voir `LICENSE` pour plus de détails.

## 🤝 Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amazing-feature`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

---

**Mille Bornes** - Prenez la route, à votre rythme ! 🚗💨
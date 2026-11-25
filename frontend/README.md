# Mille Bornes — Frontend

Interface React, TypeScript et Vite. Le frontend utilise Tailwind CSS, React
Router, Axios et Zustand.

## Lancer en développement

Prérequis : Node.js et pnpm.

```bash
pnpm install
cp .env.example .env
pnpm dev
```

Vite démarre sur `http://localhost:5173`.

## Configuration

Dans `.env`, configurez l'URL de base de l'API Django :

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Le frontend envoie les requêtes avec les cookies nécessaires au renouvellement
JWT et au contrôle CSRF. Pour le lobby en temps réel, l'URL WebSocket est déduite
de `VITE_API_BASE_URL` ; `VITE_WS_BASE_URL` peut la remplacer si nécessaire.

## Vérifications

```bash
pnpm typecheck
pnpm build
```

L'écran de jeu est encore une prévisualisation : il sera relié au moteur lorsque
l'API de partie et ses actions seront disponibles. Les règles du jeu ne sont pas
implémentées dans le frontend.

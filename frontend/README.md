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
JWT et au contrôle CSRF. Le lobby et les parties multijoueur utilisent le
WebSocket authentifié ; son URL est déduite de `VITE_API_BASE_URL`.
`VITE_WS_BASE_URL` peut la remplacer si nécessaire.

## Vérifications

```bash
pnpm typecheck
pnpm build
```

Le plateau multijoueur reçoit les snapshots et événements du serveur et envoie
uniquement des commandes ; le serveur valide chaque coup. L'écran solo conserve
son aperçu tant que l'intégration des tours d'IA n'est pas exposée. Aucune règle
du jeu n'est implémentée dans React.

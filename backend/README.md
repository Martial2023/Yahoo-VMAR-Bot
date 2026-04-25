# BotVMAR — Backend

Bot Yahoo Finance qui scrape la page communauté du ticker VMAR et y commente / répond via OpenRouter.

Worker Python + API de contrôle FastAPI dans le **même process**. La DB Postgres est **gérée par le frontend Next.js (Prisma)** ; le backend ne fait que la lire/écrire.

## Stack

- Python 3.11+
- Playwright (navigation furtive Yahoo)
- asyncpg (Postgres)
- FastAPI + uvicorn (API control)
- OpenRouter (génération texte)
- aiosmtplib (alertes email)

## Architecture

```
backend/src/botvmar/
├── main.py            # entry point — lance worker + API ensemble
├── worker.py          # boucle de cycles (asyncio.Event pour trigger)
├── api.py             # FastAPI : /trigger-cycle /reload-config /status /stop
├── state.py           # asyncio.Event partagés worker <-> API
├── config/
│   ├── env.py         # secrets + infra depuis .env
│   └── runtime.py     # bot_settings depuis Postgres (cache)
├── db/
│   ├── pool.py
│   └── repositories/  # settings, comments, activities, runs
├── browser/           # Playwright + stealth + session storage
├── scraper/comments.py
├── poster/actions.py
├── ai/responder.py    # prompts dynamiques depuis bot_settings
├── services/bot_service.py  # orchestration d'un cycle complet
└── utils/             # logger + notifier (Telegram + SMTP)
```

## Endpoints API

Toutes les routes (sauf `/health`) requièrent le header `Authorization: Bearer <API_TOKEN>`.

| Méthode | Route             | Description                                 |
|---------|-------------------|---------------------------------------------|
| GET     | `/health`         | probe sans auth                             |
| GET     | `/status`         | snapshot des settings runtime               |
| POST    | `/trigger-cycle`  | réveille le worker pour exécuter un cycle   |
| POST    | `/reload-config`  | recharge `bot_settings` depuis Postgres     |
| POST    | `/stop`           | demande un shutdown gracieux                |

## Installation rapide (Ubuntu VPS)

```bash
cd backend
./install.sh
nano .env       # DATABASE_URL, API_TOKEN, OPENROUTER_KEY, SMTP_*
```

Puis appliquer le schéma Prisma + seed depuis le frontend (`pnpm prisma migrate deploy && pnpm prisma db seed`), puis :

```bash
source .venv/bin/activate
xvfb-run python scripts/login.py     # login Yahoo manuel
python -m botvmar.main               # lance worker + API
```

## Schéma DB attendu (Prisma — côté frontend)

Voir [prisma_schema_reference.prisma](prisma_schema_reference.prisma). Tables nécessaires :

- `bot_settings` — singleton de config tunable
- `seen_comments` — IDs de commentaires déjà traités
- `bot_activities` — log événementiel (scrape / reply / post / error)
- `bot_runs` — agrégat par cycle pour les graphes du dashboard

Better Auth gère ses propres tables (`User`, `Session`, etc.) — le backend ne s'en occupe pas.

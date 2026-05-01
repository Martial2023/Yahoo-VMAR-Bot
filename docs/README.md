# Documentation BotVMAR

| Document | Pour qui | Contenu |
|---|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Tous devs | Vue d'ensemble, schéma DB, cycle d'exécution, isolation des erreurs |
| [ADDING_A_PLATFORM.md](./ADDING_A_PLATFORM.md) | Dev qui ajoute une plateforme | Tutoriel pas-à-pas : adapter → registry → seed → tests |
| [REDDIT_SETUP.md](./REDDIT_SETUP.md) | Ops | Création app Reddit, credentials, première mise en route |
| [DEPLOYMENT.md](../DEPLOYMENT.md) | Ops | Procédure de déploiement frontend (Vercel) + backend (VPS Ubuntu) |
| [Rapport projet](../rapport_projet.txt) | Stakeholders | Synthèse non-technique pour le supérieur / client |

## Démarrage rapide

```bash
# Backend (worker + API)
cd backend
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -e .
playwright install chromium
python -m botvmar.main

# Frontend (dashboard)
cd frontend
pnpm install
pnpm prisma migrate deploy   # applique le schéma
pnpm prisma db seed          # crée bot_settings + platform_settings
pnpm dev
```

## Plateformes supportées

| Plateforme | Statut | Méthode | Adapter |
|---|---|---|---|
| Yahoo Finance | ✅ Production | Playwright + cookies | `adapters/yahoo_finance/` |
| Reddit | 🟢 Code prêt — en attente credentials | OAuth API (asyncpraw) | `adapters/reddit/` |
| StockTwits | ⏳ Phase 6 | Playwright (scraping) | *à créer* |
| Seeking Alpha | ⏳ Phase 7 | Playwright (scraping) | *à créer* |
| Investing.com | ⏳ Phase 8 | Playwright (scraping) | *à créer* |

## Roadmap

Voir `rapport_projet.txt` pour la motivation produit. La feuille de route
technique :

1. **Phase 1** ✅ Refactoring : `PlatformAdapter`, orchestrateur, schéma
   multi-plateforme.
2. **Phase 2** Scheduling par slots horaires + mode test/whitelist.
3. **Phase 3** RedditAdapter (API officielle).
4. **Phase 4** Frontend : pages Settings/Whitelist/Schedule par plateforme.
5. **Phase 5** Déploiement Reddit en mode test.
6. **Phases 6-8** StockTwits / Seeking Alpha / Investing.com (scraping).

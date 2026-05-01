# BotVMAR — Architecture multi-plateforme

> Audience : développeurs travaillant sur le projet, ou repreneurs futurs.
> Mis à jour : 2026-04-29.

## 1. Vue d'ensemble

BotVMAR est un système de présence automatisée pour le ticker VMAR
(Vision Marine Technologies). Il scrape des plateformes financières,
génère des réponses contextuelles via IA et publie de manière autonome.

L'architecture est organisée autour d'**adapters de plateforme** : chaque
plateforme (Yahoo Finance, Reddit, …) implémente une interface commune
`PlatformAdapter`, et un orchestrateur exécute toutes les plateformes
activées de façon **isolée et parallèle**.

```
                     ┌─────────────────────┐
                     │   Dashboard Vercel  │
                     │   (Next.js 16)      │
                     └──────────┬──────────┘
                                │ Bearer
                                ▼
   ┌───────────────────────────────────────────────────────────┐
   │                VPS Ubuntu (FastAPI + worker)              │
   │                                                            │
   │   worker.run()                                             │
   │      └── bot_service.run_cycle()       ← orchestrateur     │
   │             ├── platform_runner(yahoo)  asyncio.gather     │
   │             ├── platform_runner(reddit) (parallèle,        │
   │             └── platform_runner(...)     isolé/erreurs)    │
   │                                                            │
   │   Adapters :  YahooFinanceAdapter (Playwright)             │
   │               RedditAdapter (OAuth API)                    │
   │               StockTwitsAdapter (Playwright) — à venir     │
   │               …                                            │
   └───────────────────────┬───────────────────────────────────┘
                           │
                           ▼
                  ┌────────────────┐         ┌──────────────┐
                  │ PostgreSQL Neon│         │  OpenRouter  │
                  └────────────────┘         └──────────────┘
```

## 2. Composants principaux

### 2.1 Adapters de plateforme

`backend/src/botvmar/adapters/`

Chaque adapter implémente `PlatformAdapter` (`adapters/base.py`) :

| Méthode | Rôle |
|---|---|
| `init()` | Ouvre les ressources (browser, OAuth, …) |
| `cleanup()` | Ferme les ressources, idempotent, ne raise jamais |
| `health()` | Probe rapide (optionnel) |
| `fetch_posts(ticker)` | Retourne des `Post` normalisés |
| `reply_to(post, text)` | Répond à un post — return `bool` |
| `create_post(ticker, text)` | Publie un nouveau post — return `bool` |
| `should_skip_author(author)` | Skip-list par plateforme |

Les adapters convertissent les données brutes de leur plateforme vers
le `Post` dataclass commun, et inversement traduisent les actions du
domaine (`reply_to`, `create_post`) en appels Playwright/REST/etc.

**Adapters disponibles** :

- `yahoo_finance/` — Playwright + cookies sauvegardés
- `reddit/` — OAuth API officielle (asyncpraw) — adapter + client + filters
- `stocktwits/` *(planifié, Phase 6)* — Playwright
- `seeking_alpha/` *(planifié, Phase 7)* — Playwright
- `investing/` *(planifié, Phase 8)* — Playwright

### 2.2 Orchestrateur

`backend/src/botvmar/services/bot_service.py`

`run_cycle()` :

1. Charge les `PlatformConfig` activées depuis Postgres
2. Lance `platform_runner.run_platform_cycle()` pour chacune dans
   `asyncio.gather(return_exceptions=True)`
3. Une plateforme en panne ne bloque jamais les autres :
   - `platform_runner` catch déjà toutes les erreurs et les log
   - `bot_service._run_one_safely` est un filet de sécurité supplémentaire

### 2.3 Per-platform runner

`backend/src/botvmar/services/platform_runner.py`

`run_platform_cycle(platform_config)` exécute le pipeline pour UNE plateforme :

1. Build adapter via `adapters.registry.build_adapter()`
2. `adapter.init()` (auth/session)
3. `adapter.fetch_posts(ticker)`
4. Filtrer les posts déjà vus (`seen_comments`)
5. **Mode test** : ne répondre qu'aux auteurs whitelistés
6. Pour chaque nouveau post :
   - `should_skip_author()` ? skip
   - `len(text) < min_post_length` ? skip
   - Générer la réponse via `ai.responder.generate_reply()`
   - `adapter.reply_to(post, text)`
   - Logger le résultat dans `bot_activities`
7. Optionnel : `adapter.create_post()` (post proactif si quota dispo)
8. `adapter.cleanup()` (toujours, dans `finally`)

### 2.4 Configuration

| Source | Contenu | Fréquence de lecture |
|---|---|---|
| `.env` (`config/env.py`) | Secrets, DSN Postgres, credentials SMTP | au démarrage |
| `bot_settings` (`config/runtime.py`) | Réglages globaux : kill switch, modèle IA, prompts par défaut | début de chaque cycle |
| `platform_settings` (`config/platforms.py`) | Réglages par plateforme : enabled, mode, quotas, slots, prompts override, credentials, config | début de chaque cycle |
| `whitelisted_authors` | Auteurs autorisés en mode test | début de chaque cycle |

### 2.5 Schéma de base de données

| Table | Rôle | Colonnes clés |
|---|---|---|
| `bot_settings` | Singleton — réglages globaux | `id=1`, `bot_enabled`, `ai_model`, `ai_temperature`, prompts par défaut |
| `platform_settings` | Une ligne par plateforme | `platform`, `enabled`, `mode`, `max_replies_per_day`, `max_posts_per_day`, `schedule_slots`, `credentials`, `config` |
| `whitelisted_authors` | Auteurs autorisés en mode test | `(platform, author_handle)` unique |
| `seen_comments` | Dédup des posts traités | `id`, **`platform`** (default `yahoo_finance`) |
| `bot_activities` | Audit trail granulaire | `type`, `status`, `platform`, `comment_id`, `content`, `error_msg`, `metadata` |
| `bot_runs` | Une ligne par cycle par plateforme | `platform`, `started_at`, `comments_scraped`, `replies_posted`, `posts_published`, `errors_count` |

> Toutes les colonnes `platform` ajoutées à des tables existantes ont
> `DEFAULT 'yahoo_finance'` pour préserver les données antérieures.

## 3. Cycle d'exécution typique

```
worker.run() (boucle infinie)
    │
    ├── run_cycle(triggered_by="schedule")
    │       │
    │       ├── load BotSettings  (kill switch global)
    │       ├── load PlatformSettings WHERE enabled = true
    │       │
    │       ├── asyncio.gather:
    │       │     ├── run_platform_cycle(yahoo_finance)
    │       │     │     ├── adapter.init()
    │       │     │     ├── adapter.fetch_posts("VMAR")
    │       │     │     ├── filter_new(posts)
    │       │     │     ├── for post:
    │       │     │     │     ├── checks (skip / length / whitelist)
    │       │     │     │     ├── generate_reply()
    │       │     │     │     ├── adapter.reply_to()
    │       │     │     │     └── log activity
    │       │     │     ├── (optionally) adapter.create_post()
    │       │     │     └── adapter.cleanup()
    │       │     │
    │       │     └── run_platform_cycle(reddit)
    │       │           (same pipeline, different adapter)
    │       │
    │       └── runs.finish() pour chaque plateforme
    │
    └── sleep jusqu'au prochain slot
```

## 4. Mode test vs production

`platform_settings.mode` contrôle la sécurité opérationnelle :

| Mode | Comportement |
|---|---|
| `test` | Ne répond qu'aux auteurs présents dans `whitelisted_authors` (même `platform`). Les posts proactifs restent autorisés (quota usuel). |
| `production` | Répond à tout le monde, hors `should_skip_author()`. |

Toujours commencer une nouvelle plateforme en `test` avec une whitelist
restreinte (ton compte de test), puis basculer en `production` après
validation.

## 5. Scheduling

`backend/src/botvmar/scheduling/slots.py`

Chaque plateforme définit ses propres slots horaires dans
`platform_settings.schedule_slots` (liste de `"HH:MM"`, timezone serveur).
Le worker tick toutes les 30 secondes ; à chaque tick :

1. Vide tout déclenchement manuel pendant (`/trigger-cycle{/platform}`) et
   l'exécute immédiatement.
2. Vérifie le kill switch global (`bot_settings.bot_enabled`).
3. Pour chaque plateforme `enabled`, regarde si `now` tombe dans la fenêtre
   `[slot, slot + jitter_min)` ET que **aucun run n'a démarré dans cette
   fenêtre** (vérifié via `MAX(bot_runs.started_at) WHERE platform = ?`).
4. Lance `run_cycle(only_platforms=[...])` pour les plateformes éligibles.

Cette logique garantit qu'un slot est honoré au plus une fois par jour
même si le worker redémarre, et permet à plusieurs plateformes d'avoir
des cadences indépendantes.

| Champ DB | Rôle |
|---|---|
| `schedule_slots` | `["09:00", "14:00", "19:00"]` |
| `schedule_jitter_min` | Largeur de la fenêtre (par défaut 10 min) |

> ⚠️ Les slots sont interprétés dans la timezone du serveur (UTC sur le VPS
> de production). Si un opérateur saisit `"09:00"` depuis un dashboard à
> Paris, ce sera 09:00 UTC = 11:00 Paris en été.

## 6. Skip rules

`backend/src/botvmar/scheduling/skip_rules.py`

Avant de générer une réponse, le runner applique 5 filtres dans cet ordre :

| # | Source | Effet | `bot_activities.error_msg` |
|---|---|---|---|
| 1 | `adapter.should_skip_author()` | Liste hardcodée par adapter (compte officiel) | `skip_author_builtin` |
| 2 | `platform_settings.config.skipAuthors` | Liste éditable depuis le dashboard | `skip_author_config` |
| 3 | `platform_settings.config.skipKeywords` | Substring lowercase sur le texte | `skip_keyword` |
| 4 | `platform_settings.min_post_length` | Posts trop courts | `too_short` |
| 5 | `mode = "test"` + `whitelisted_authors` | Mode test : auteur non whitelisté | `not_whitelisted` |

Tout post skippé écrit une entrée `bot_activities` avec `status='skipped'`
et le code de raison ci-dessus, ce qui rend les filtres entièrement
auditables depuis le dashboard.

## 7. Isolation des erreurs

Trois niveaux de protection :

1. **Dans l'adapter** : les méthodes `reply_to` / `create_post` retournent
   `False` au lieu de raise sur les échecs utilisateur (sélecteur introuvable,
   bouton désactivé, etc.). Seuls `init()` peut raise (`PlatformAuthError`)
   pour signaler une session morte.
2. **Dans `platform_runner`** : try/except global autour de tout le cycle.
   `PlatformError` et `Exception` sont attrapés, loggés dans `bot_activities`
   (`type=error`), et notifiés (email/Telegram).
3. **Dans `bot_service`** : `_run_one_safely()` enveloppe `platform_runner`
   dans un dernier try/except. `asyncio.gather(return_exceptions=True)` garantit
   qu'une crash ne propage pas dans la boucle principale.

→ **Une plateforme qui plante n'arrête jamais les autres.**

## 8. Ajouter une nouvelle plateforme

1. **Créer le dossier adapter** :
   ```
   backend/src/botvmar/adapters/<name>/
       __init__.py        # exporte la classe
       adapter.py         # implémente PlatformAdapter
       (...autres fichiers spécifiques)
   ```

2. **Implémenter `PlatformAdapter`** dans `adapter.py` :
   - définir `name` (= valeur en BD) et `display_name`
   - `init()` / `cleanup()` / `fetch_posts()` / `reply_to()` / `create_post()`
   - convertir les données brutes en `Post` (id stable, platform, author, text…)

3. **Enregistrer dans le registry** : ajouter une entrée à
   `adapters/registry.py:_REGISTRY`.

4. **Seed Prisma** : ajouter une `prisma.platformSettings.upsert(...)` dans
   `frontend/prisma/seed.ts` avec `enabled: false` par défaut.

5. **Tester en mode `test`** avec une whitelist restreinte.

6. **Mettre à jour la doc** (cette page + README).

## 9. Migration DB

Quand le schéma Prisma change :

```bash
# Côté frontend
cd frontend
pnpm prisma migrate dev --name <description>
pnpm prisma db seed     # si nouveau seed
```

Sur le VPS, après pull :

```bash
cd frontend
pnpm install
pnpm prisma migrate deploy   # applique les migrations en prod
```

Le backend Python ne génère pas de migration : il consomme uniquement le
schéma déjà appliqué.

## 10. Contrôle via API

| Endpoint | Méthode | Rôle |
|---|---|---|
| `/health` | GET | Liveness probe (sans auth) |
| `/status` | GET | État courant + plateformes activées et leurs slots |
| `/trigger-cycle` | POST | Déclenche un cycle immédiat (toutes les plateformes activées) |
| `/trigger-cycle/{platform}` | POST | Déclenche un cycle immédiat pour une seule plateforme |
| `/reload-config` | POST | Recharge `bot_settings` + `platform_settings` |
| `/stop` | POST | Demande un arrêt gracieux |

> Tous les endpoints (sauf `/health`) requièrent `Authorization: Bearer <API_TOKEN>`.

## 11. Variables d'environnement

`backend/.env` :

```ini
DATABASE_URL=postgresql://...
API_TOKEN=...
OPENROUTER_KEY=...

# Yahoo Finance
YAHOO_EMAIL=...
YAHOO_PASSWORD=...
SESSION_FILE=sessions/yahoo_session.json

# Reddit (Phase 3 — à compléter)
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USERNAME=...
REDDIT_PASSWORD=...
REDDIT_USER_AGENT=BotVMAR/0.1 by yourRedditUsername

# SMTP / Telegram alertes
SMTP_HOST=...
TELEGRAM_BOT_TOKEN=...
```

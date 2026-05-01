# Ajouter une nouvelle plateforme

Guide pas-à-pas pour intégrer une plateforme supplémentaire (StockTwits,
Seeking Alpha, Investing.com, etc.) dans BotVMAR.

## Pré-requis

- Comprendre l'interface `PlatformAdapter` (voir `backend/src/botvmar/adapters/base.py`).
- Avoir un compte de test sur la plateforme cible.
- Identifier la stratégie d'accès :
  - **API officielle** (Reddit) — privilégié quand disponible.
  - **Scraping Playwright** (Yahoo Finance, StockTwits, Seeking Alpha) — sinon.

## Étape 1 — Créer le package adapter

```
backend/src/botvmar/adapters/<name>/
    __init__.py          # exporte la classe principale
    adapter.py           # implémente PlatformAdapter
    client.py            # (optionnel) wrapper API/HTTP
    scraper.py           # (optionnel) logique de scraping
    poster.py            # (optionnel) logique de publication
```

`<name>` doit être en `lower_snake_case` et identique à la valeur stockée
dans `platform_settings.platform`.

## Étape 2 — Implémenter l'interface

```python
# adapters/<name>/adapter.py

from botvmar.adapters.base import PlatformAdapter, Post, PlatformAuthError
from botvmar.config.platforms import PlatformConfig
from botvmar.utils.logger import get_logger

logger = get_logger("adapter.<name>")


class MyPlatformAdapter(PlatformAdapter):
    name = "<name>"
    display_name = "<Name>"

    def __init__(self, config: PlatformConfig) -> None:
        self._config = config
        # Init internal state (clients, browser handles, etc.)

    async def init(self) -> None:
        # OAuth, login, browser launch, ...
        # Raise PlatformAuthError if creds are bad.
        ...

    async def cleanup(self) -> None:
        # Close everything, NEVER raise.
        ...

    async def fetch_posts(self, ticker: str) -> list[Post]:
        # Return posts mentioning `ticker`.
        # Use Post(id=..., platform=self.name, author=..., text=..., ...).
        ...

    async def reply_to(self, post: Post, text: str) -> bool:
        # Return True on success, False on user-level failure.
        ...

    async def create_post(self, ticker: str, text: str) -> bool:
        ...

    def should_skip_author(self, author: str) -> bool:
        # Optional: filter official accounts, blocked users, etc.
        return False
```

### Conseils

- **`Post.id`** doit être stable et unique pour la plateforme. Privilégier
  l'ID natif (Reddit submission id, Yahoo post UUID). Sinon, utiliser un hash
  déterministe `(author, text[:200])`.
- **`Post.raw`** est ton bac à sable pour stocker tout ce dont tu as besoin
  pour répondre plus tard (sélecteurs DOM, objets API). Ce champ n'est pas
  persisté.
- **`reply_to` / `create_post`** ne doivent JAMAIS raise sur des erreurs
  utilisateur (élément introuvable, rate limit single-call) — return `False`.
- **`init` peut raise `PlatformAuthError`** quand la session est cassée :
  l'orchestrateur loggera et passera à la plateforme suivante.

## Étape 3 — Enregistrer dans le registry

`backend/src/botvmar/adapters/registry.py` :

```python
def _build_my_platform(config: PlatformConfig) -> PlatformAdapter:
    from botvmar.adapters.my_platform import MyPlatformAdapter
    return MyPlatformAdapter(config=config)


_REGISTRY: dict[str, Callable[[PlatformConfig], PlatformAdapter]] = {
    "yahoo_finance": _build_yahoo_finance,
    "reddit": _build_reddit,
    "my_platform": _build_my_platform,   # ← ajouté
}
```

L'import est fait dans la closure pour éviter de charger les dépendances
optionnelles (Playwright, asyncpraw, …) au démarrage du processus.

## Étape 4 — Seed Prisma

`frontend/prisma/seed.ts` — ajouter un upsert :

```ts
await prisma.platformSettings.upsert({
  where: { platform: "my_platform" },
  update: {},
  create: {
    platform: "my_platform",
    displayName: "My Platform",
    enabled: false,             // off until creds are configured
    mode: "test",               // start safe
    replyEnabled: true,
    postEnabled: false,         // posting est risqué — activer plus tard
    ticker: "VMAR",
    maxRepliesPerDay: 5,
    maxPostsPerDay: 1,
    minPostLength: 30,
    scheduleSlots: ["10:00", "16:00"],
    scheduleJitterMin: 15,
    replyPrompt: MY_PLATFORM_REPLY_PROMPT,
    postPrompt: MY_PLATFORM_POST_PROMPT,
    config: {
      // Tout ce dont l'adapter a besoin :
      // listes de tags, URL de base, etc.
    },
  },
});
```

Puis `pnpm prisma db seed` pour appliquer.

## Étape 5 — Configurer les credentials

Dans le dashboard (Settings → My Platform), saisir :

- les identifiants nécessaires (OAuth client_id/secret, API key, login/password)
  → stockés dans `platform_settings.credentials` (JSONB).
- les paramètres spécifiques (sub-forums, tags) → `platform_settings.config`.

L'adapter lit ces valeurs depuis `self._config.credentials` et `self._config.config`.

## Étape 6 — Tester en mode `test`

1. Ajouter ton handle de test dans la whitelist :
   ```sql
   INSERT INTO whitelisted_authors (platform, author_handle, note)
   VALUES ('my_platform', 'mon_handle_de_test', 'compte de validation');
   ```
2. Activer la plateforme : `enabled = true`, `mode = test`.
3. Déclencher un cycle manuel : `POST /trigger-cycle/my_platform` (ou
   `POST /trigger-cycle` pour toutes).
4. Surveiller `bot_activities` :
   ```sql
   SELECT type, status, error_msg, content, created_at
   FROM bot_activities
   WHERE platform = 'my_platform'
   ORDER BY created_at DESC
   LIMIT 50;
   ```

## Étape 7 — Basculer en `production`

Quand les tests sont satisfaisants :

- Vérifier que `bot_runs` n'a aucun cycle `failed` récent.
- Vérifier que les réponses générées sont qualitatives (`bot_activities.content`).
- Mettre `mode = production` dans le dashboard.
- Augmenter progressivement les quotas.

## Anti-patterns à éviter

- **Catcher silencieusement les erreurs d'auth.** Toujours raise
  `PlatformAuthError` dans `init()` pour notifier l'opérateur.
- **Sleep dans `reply_to` / `create_post`.** Le délai inter-réponses est géré
  par `platform_runner.py` (`asyncio.sleep(60..180)`).
- **Mutate `Post.raw` après `fetch_posts`.** Le runner peut filtrer/réordonner :
  garde `raw` immuable hors de l'adapter.
- **Hardcoder un ticker.** Toujours utiliser `platform_config.ticker`.
- **Importer le module adapter au top du registry.** Utiliser une closure pour
  l'import lazy → un Playwright manquant ne casse pas le démarrage.

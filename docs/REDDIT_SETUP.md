# Reddit setup — credentials & first run

Étape par étape pour mettre en route le `RedditAdapter` (Phase 3).

## 1. Créer une "script-type" app Reddit

1. Va sur **https://www.reddit.com/prefs/apps** (logué avec le compte Reddit
   du bot — pas ton compte perso).
2. Tout en bas, clic sur **"are you a developer? create an app..."**.
3. Remplis le formulaire :
   - **name** : `BotVMAR`
   - **type** : **script** *(impératif — c'est le seul mode qui supporte le
     `username` + `password` dans `asyncpraw`)*
   - **description** : `Internal bot for community engagement on r/stocks subs`
   - **about url** : laisser vide
   - **redirect uri** : `http://localhost:8080` (obligatoire pour valider le
     formulaire, jamais utilisé en mode script)
4. Clique **create app**.

Tu obtiens deux secrets :
- **client_id** : la chaîne sous le nom de l'app (juste à côté de "personal use script")
- **client_secret** : la valeur du champ `secret`

## 2. Renseigner `.env`

Dans `backend/.env`, ajoute :

```ini
REDDIT_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxx
REDDIT_CLIENT_SECRET=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
REDDIT_USERNAME=ton_pseudo_reddit_du_bot
REDDIT_PASSWORD=ton_mot_de_passe_reddit_du_bot
REDDIT_USER_AGENT=BotVMAR/0.1 (by /u/ton_pseudo_reddit_du_bot)
```

> ⚠️ Le user agent **doit** suivre exactement le format
> `<platform>:<app_id>:<version> (by /u/<username>)` ou une variante. Reddit
> bloque les requêtes avec un user agent générique (`Python/requests`).
> ⚠️ Si le compte Reddit a la **2FA activée**, désactive-la pour les
> script-apps (Reddit ne supporte pas le 2FA pour ce mode), ou utilise
> `password=<motdepasse>:<code-2fa>` (TOTP, change toutes les 30s — non
> viable en prod). On recommande un compte dédié au bot **sans 2FA**.

## 3. Configurer la plateforme dans la base

La ligne `platform_settings` pour Reddit existe déjà (créée par le seed)
avec `enabled = false`. Vérifie / ajuste les paramètres via SQL ou via la
page Settings du dashboard (Phase 4.1) :

```sql
UPDATE platform_settings
SET
  enabled = true,                                 -- activer
  mode = 'test',                                   -- garder en test au début
  schedule_slots = ARRAY['10:00', '16:00'],        -- slots UTC
  schedule_jitter_min = 15,
  max_replies_per_day = 5,
  max_posts_per_day = 1,
  config = '{
    "subreddits": ["pennystocks", "stocks", "wallstreetbets"],
    "searchQueries": ["VMAR", "Vision Marine"],
    "fetchLimit": 25,
    "listing": "new",
    "postSubreddit": "pennystocks",
    "skipAuthors": ["AutoModerator"],
    "skipKeywords": ["pump", "moon", "🚀"]
  }'::jsonb
WHERE platform = 'reddit';
```

Champs `config` reconnus par l'adapter :

| Clé | Type | Effet |
|---|---|---|
| `subreddits` | `string[]` | Subs scannés à chaque cycle |
| `searchQueries` | `string[]` | Mots-clés alternatifs (en plus du ticker) |
| `fetchLimit` | `int` (défaut 25) | Nombre de submissions tirées par sub |
| `listing` | `"new" \| "hot" \| "top" \| "rising"` (défaut `new`) | Type de listing |
| `postSubreddit` | `string` | Sub cible pour `create_post` (défaut : 1er de `subreddits`) |
| `skipAuthors` | `string[]` | Auteurs skip-listés (en plus de `AutoModerator` et du compte du bot lui-même) |
| `skipKeywords` | `string[]` | Mots-clés à éviter dans le texte du post |

## 4. Ajouter ton handle de test à la whitelist

Tant que `mode = 'test'`, le bot ne répondra qu'aux auteurs whitelistés.
Avant le premier cycle :

```sql
INSERT INTO whitelisted_authors (platform, author_handle, note, created_at)
VALUES
  ('reddit', 'ton_compte_reddit_de_test', 'test sandbox', NOW());
```

## 5. Smoke test

Depuis `backend/`, vérifie que les credentials marchent et que le filtre
attrape les bonnes submissions **sans rien poster** :

```bash
python -m scripts.reddit_test
```

Sortie attendue :
```
✓ Logged in to Reddit as the configured user
✓ Subreddits configured: ['pennystocks', 'stocks', 'wallstreetbets']
✓ Search keywords: ['VMAR', 'Vision Marine']
  Ticker: VMAR

✓ N matching submission(s) found:
  - r/pennystocks [some_user] reddit_t3_xxxxxxx
      Title de la submission ...
      https://www.reddit.com/r/...
```

Pour tester le posting réel d'une réponse (à utiliser sur une submission de
TON sub privé, jamais sur un sub public) :

```bash
python -m scripts.reddit_test --reply 1abcdef "test reply from BotVMAR"
```

## 6. Premier cycle managé via le worker

```bash
# Trigger manuel ciblé Reddit
curl -X POST http://localhost:8000/trigger-cycle/reddit \
  -H "Authorization: Bearer $API_TOKEN"

# Surveiller les activités
psql "$DATABASE_URL" -c "
  SELECT type, status, error_msg, content, created_at
  FROM bot_activities
  WHERE platform = 'reddit'
  ORDER BY created_at DESC
  LIMIT 20;
"
```

## 7. Bascule en `production`

Quand les tests sont satisfaisants (au moins 1 semaine en mode test sans
`failed` dans `bot_runs`) :

```sql
UPDATE platform_settings SET mode = 'production' WHERE platform = 'reddit';
```

Puis monter progressivement les quotas (`max_replies_per_day`,
`max_posts_per_day`).

## Anti-shadowban — bonnes pratiques

- **Karma** : poster/commenter un peu manuellement avec le compte avant
  d'activer le bot. Reddit shadowban les comptes neuf qui posent du contenu
  généré.
- **Diversité** : varier les sub-reddits, varier les types d'action (reply
  > submit), varier les heures. Les slots horaires ±jitter du scheduler
  servent exactement à ça.
- **Ne jamais répondre 2× sous la même submission** dans un même cycle.
  L'adapter ne le fait pas, mais évite-le aussi en manuel.
- **Surveiller** régulièrement que tes posts apparaissent quand tu navigues
  Reddit en non-loggé (un shadowban masque le contenu aux autres mais te le
  laisse visible quand tu es loggé sur ton compte).

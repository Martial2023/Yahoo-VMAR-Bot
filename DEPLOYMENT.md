# Déploiement BotVMAR

| Composant | Hébergement | Auto-deploy |
|---|---|---|
| Frontend Next.js | Vercel | Auto (Git connect) |
| Backend Python | VPS Ubuntu 22.04+ | GitHub Actions → SSH |
| Postgres | Neon (managed) | — |

## Architecture du déploiement

```
git push main
   ├─ vercel : build & deploy frontend
   └─ GitHub Actions :
        SSH au VPS
        ├─ git pull
        └─ backend/deploy.sh
              ├─ pip install -r requirements.txt
              ├─ playwright install chromium
              └─ systemctl restart botvmar
```

---

## 1. Setup initial du VPS (à faire une seule fois)

### 1.1. Pré-requis

- Ubuntu 22.04 / 24.04
- Un user avec sudo (ex. `ubuntu`)
- Un domaine ou IP publique
- Un port ouvert (8000 par défaut, configurable via `API_PORT` du `.env`)

### 1.2. Cloner le repo

```bash
sudo mkdir -p /opt/botvmar
sudo chown $USER:$USER /opt/botvmar
cd /opt/botvmar
git clone https://github.com/<your-org>/<your-repo>.git .
```

### 1.3. Configurer le `.env` du backend

```bash
cd /opt/botvmar/backend
cp .env.example .env
nano .env
```

Remplis :
- `DATABASE_URL` — Neon Postgres
- `API_TOKEN` — token long aléatoire (`openssl rand -hex 32`), à mettre aussi côté Vercel comme `BACKEND_API_TOKEN`
- `OPENROUTER_KEY` — depuis https://openrouter.ai/keys
- `SMTP_*` — pour les alertes email (optionnel)
- `TELEGRAM_*` — pour les alertes Telegram (optionnel)

### 1.4. Installation initiale

```bash
cd /opt/botvmar/backend
bash install.sh
```

Le script :
- Installe les paquets système (Python 3, Playwright deps, Xvfb)
- Crée le venv et installe les dépendances Python
- Installe Playwright Chromium avec ses libs système
- Crée les dossiers `data/`, `logs/`, `sessions/`
- Installe et active le service systemd `botvmar.service`

### 1.5. Login Yahoo manuel (one-shot)

Le bot a besoin d'une session Yahoo persistée. Sur un VPS sans display :

```bash
cd /opt/botvmar/backend
source .venv/bin/activate
xvfb-run python scripts/login.py
```

Ouvre le browser via Xvfb. Pour interagir, utilise un tunnel VNC ou X-forwarding :

```bash
# Depuis ta machine locale
ssh -X user@vps
# Puis sur le VPS
python scripts/login.py
```

(Alternative : login en local avec `python scripts/login.py`, puis `scp sessions/yahoo_session.json` vers le VPS.)

### 1.6. Démarrer le service

```bash
sudo systemctl start botvmar
sudo systemctl status botvmar
sudo journalctl -u botvmar -f
```

### 1.7. Reverse proxy (recommandé) — exposer l'API en HTTPS

Le frontend Vercel doit appeler `BACKEND_API_URL` en **HTTPS**. Mettez Caddy ou Nginx + Let's Encrypt devant `localhost:8000`.

Exemple Caddy (`/etc/caddy/Caddyfile`) :

```
api.tondomaine.com {
    reverse_proxy localhost:8000
}
```

```bash
sudo systemctl reload caddy
```

Sur Vercel, mets `BACKEND_API_URL=https://api.tondomaine.com`.

---

## 2. Setup auto-deploy via GitHub Actions

### 2.1. Préparer un user de déploiement (optionnel mais recommandé)

Crée une clé SSH dédiée au déploiement :

```bash
# Sur ta machine locale
ssh-keygen -t ed25519 -C "github-deploy-botvmar" -f ~/.ssh/botvmar_deploy

# Copie la PUBLIQUE sur le VPS
ssh-copy-id -i ~/.ssh/botvmar_deploy.pub user@vps
```

### 2.2. Sudo NOPASSWD pour `systemctl restart botvmar`

`deploy.sh` utilise `sudo systemctl restart botvmar`. Pour que la GH Action ne se bloque pas sur un prompt mot de passe, ajoute un fichier sudoers :

```bash
sudo visudo -f /etc/sudoers.d/botvmar-deploy
```

Contenu :

```
ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart botvmar, /bin/systemctl is-active botvmar, /usr/bin/journalctl -u botvmar
```

(Remplace `ubuntu` par le user SSH utilisé par la GH Action.)

### 2.3. Configurer les secrets GitHub

`Settings → Secrets and variables → Actions → New repository secret` :

| Secret | Valeur |
|---|---|
| `VPS_HOST` | IP ou hostname du VPS |
| `VPS_USER` | user SSH (ex. `ubuntu`) |
| `VPS_SSH_KEY` | contenu de `~/.ssh/botvmar_deploy` (clé **privée**) |
| `VPS_SSH_PORT` | `22` (ou ton port custom) |
| `VPS_PROJECT_PATH` | `/opt/botvmar` |

### 2.4. Premier test

Fait un changement dans `backend/`, push sur `main`. La GH Action se déclenche automatiquement (`Actions` tab du repo).

```bash
git add backend/
git commit -m "test deploy"
git push origin main
```

---

## 3. Setup Vercel pour le frontend

### 3.1. Connecter le repo

`vercel.com → Add Project → Import Git Repository`. Choisis le repo, **Root Directory = `frontend`**.

### 3.2. Variables d'environnement (Settings → Environment Variables)

| Variable | Valeur | Environments |
|---|---|---|
| `DATABASE_URL` | Neon Postgres URL | Production, Preview, Development |
| `BETTER_AUTH_SECRET` | `openssl rand -hex 32` | Production, Preview, Development |
| `BETTER_AUTH_URL` | `https://ton-app.vercel.app` (Production) / `http://localhost:3000` (Dev) | adapté par env |
| `NEXT_PUBLIC_BETTER_AUTH_URL` | idem | adapté par env |
| `BACKEND_API_URL` | `https://api.tondomaine.com` | Production, Preview |
| `BACKEND_API_TOKEN` | identique à `API_TOKEN` du `backend/.env` | Production, Preview |
| `RESEND_API_KEY` | depuis resend.com | Production (optionnel) |

### 3.3. Build settings

Vercel auto-détecte Next.js. Aucune config nécessaire si la structure est standard.

---

## 4. Opérations courantes

### Voir les logs du backend

```bash
sudo journalctl -u botvmar -f
sudo journalctl -u botvmar --since "1 hour ago"
```

### Redémarrer le backend

```bash
sudo systemctl restart botvmar
```

### Désactiver / réactiver l'auto-restart

```bash
sudo systemctl stop botvmar       # arrête
sudo systemctl disable botvmar    # ne redémarre pas au boot
sudo systemctl enable botvmar     # réactive au boot
```

### Re-login Yahoo (session expirée)

Tu reçois une alerte email/Telegram "Yahoo session expired". Pour relogin :

```bash
sudo systemctl stop botvmar
cd /opt/botvmar/backend
source .venv/bin/activate
xvfb-run python scripts/login.py
sudo systemctl start botvmar
```

### Trigger manuel d'un cycle depuis le terminal

```bash
curl -X POST -H "Authorization: Bearer $API_TOKEN" \
  https://api.tondomaine.com/trigger-cycle
```

(Ou simplement le bouton "Run cycle now" du dashboard Vercel.)

### Health check

```bash
curl https://api.tondomaine.com/health
# {"status":"ok"}
```

---

## 5. Troubleshooting

| Symptôme | Cause probable | Fix |
|---|---|---|
| GH Action timeout | Sudo demande mot de passe | Configurer NOPASSWD (§2.2) |
| `Permission denied (publickey)` | Clé pas ajoutée | `ssh-copy-id` (§2.1) |
| `Service failed to start` après deploy | Erreur Python | `journalctl -u botvmar -n 100` |
| `Backend offline` dans le dashboard | Reverse proxy ou firewall | Vérifier Caddy + UFW |
| `Yahoo session expired` en boucle | Session pas créée ou expirée | Re-login (§4) |

---

## 6. Sécurité

- Le `.env` du backend n'est **jamais** dans git (cf. `.gitignore`)
- Le `.env` Vercel est géré côté Vercel (jamais dans git)
- `API_TOKEN` et `BETTER_AUTH_SECRET` doivent être **différents** et longs (32+ chars hex)
- `disableSignUp: true` côté Better Auth empêche tout signup public
- Pour ajouter un admin : `cd frontend && pnpm create-user <email> <password>`

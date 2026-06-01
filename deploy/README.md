# Deploy naar tgn.opticore-insights.nl

Doel-URL:

```text
https://tgn.opticore-insights.nl/dashboard
```

## 1. GitHub secrets

Zet deze secrets in GitHub bij `Settings` -> `Secrets and variables` -> `Actions`:

```text
TGN_SSH_HOST=136.144.183.127
TGN_SSH_PORT=22
TGN_SSH_USER=<server user>
TGN_SSH_KEY=<private ssh key voor deploy>
```

De `.env` blijft op de server staan in:

```text
/home/opticore/projects/extern/top_groep_nederland/.env
```

Zet daar de waarden uit `.env.example` in, inclusief database en API keys.

## 2. Eenmalige server setup

Op de VPS:

```bash
bash deploy/setup_server.sh
```

Plaats daarna `/home/opticore/projects/extern/top_groep_nederland/.env`.

## 3. SSL

Na DNS en nginx:

```bash
sudo certbot --nginx -d tgn.opticore-insights.nl
```

## 4. Deploy

Elke push naar `main` start de GitHub Actions deploy. Handmatig kan via `Actions` -> `Deploy TGN dashboard` -> `Run workflow`.

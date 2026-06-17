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

## 4. Twee-factor-authenticatie

Het dashboard kan gratis worden beveiligd met een authenticator-app zoals Google Authenticator. De app gebruikt TOTP-codes en heeft geen externe betaalde dienst nodig.

Genereer een gebruikersnaam, wachtwoord-hash en authenticator-secret:

```bash
python deploy/generate_auth_secrets.py
```

Plaats de uitgeprinte waarden in de server `.env`:

```text
TGN_AUTH_ENABLED=true
TGN_AUTH_USERNAME=<gebruikersnaam>
TGN_AUTH_PASSWORD_HASH=<gegenereerde hash>
TGN_TOTP_SECRET=<gegenereerde TOTP secret>
TGN_SESSION_SECRET=<gegenereerde sessie secret>
```

Voeg de uitgeprinte `otpauth://...` URL toe aan Google Authenticator. Dat kan handmatig, of door de URL eenmalig om te zetten naar een QR-code op een vertrouwde beheercomputer.

Laat `TGN_AUTH_ENABLED` leeg of `false` in lokale/staging omgevingen waar je nog zonder login wilt testen.

## 5. Deploy

Elke push naar `main` start de GitHub Actions deploy. Handmatig kan via `Actions` -> `Deploy TGN dashboard` -> `Run workflow`.

Voor dit project deployen we altijd via deze vaste werkwijze vanuit de werkmap:

```bash
cd C:\Users\thoma\.codex\worktrees\bf3a\top_groep_nederland
git add <files>
git commit -m "<message>"
git push origin HEAD:main
```

Gebruik geen alternatieve deploy-route tenzij Thomas dat expliciet vraagt.


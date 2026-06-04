import base64
import secrets
import sys
from getpass import getpass
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.dashboard.auth import hash_password


def main() -> None:
    username = input("Gebruikersnaam: ").strip()
    password = getpass("Wachtwoord: ")
    if not username or not password:
        raise SystemExit("Gebruikersnaam en wachtwoord zijn verplicht.")

    totp_secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    session_secret = secrets.token_urlsafe(48)
    issuer = "Top Groep Nederland"
    otpauth_url = (
        "otpauth://totp/"
        f"{quote(issuer)}:{quote(username)}"
        f"?secret={totp_secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )

    print()
    print("Plaats dit in de server .env:")
    print("TGN_AUTH_ENABLED=true")
    print(f"TGN_AUTH_USERNAME={username}")
    print(f"TGN_AUTH_PASSWORD_HASH={hash_password(password)}")
    print(f"TGN_TOTP_SECRET={totp_secret}")
    print(f"TGN_SESSION_SECRET={session_secret}")
    print()
    print("Voeg deze URL handmatig toe in Google Authenticator of maak er een QR-code van:")
    print(otpauth_url)


if __name__ == "__main__":
    main()

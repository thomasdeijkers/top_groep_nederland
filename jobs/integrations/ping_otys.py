import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from jobs.integrations.otys_client import OtysClient
from shared.config.otys import validate_otys_settings


def main():
    missing = validate_otys_settings()
    if missing:
        print("OTYS_CONFIG_MISSING")
        print("\n".join(missing))
        return

    client = OtysClient()

    try:
        response = client.authenticate()
    except Exception as exc:
        print("OTYS_AUTH_ERROR")
        print(type(exc).__name__)
        print(str(exc))
        return

    print("OTYS_AUTH_RESULT")
    print("path=/api/auth")
    print(f"status_code={response.status_code}")
    print(f"content_type={response.headers.get('content-type', '')}")

    if response.ok:
        payload = response.json()
        access_token = payload.get("accessToken") or payload.get("token")
        token_type = payload.get("tokenType")
        expires_in = payload.get("expiresIn")
        expires_at = payload.get("expires_at") or payload.get("expiresAt")
        print(f"access_token_received={bool(access_token)}")
        print(f"token_type={token_type or ''}")
        print(f"expires_in_set={expires_in is not None}")
        print(f"expires_at_set={bool(expires_at)}")
    else:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if payload:
            print(f"response_keys={','.join(payload.keys())}")
            for key in ("title", "detail", "status", "type", "message"):
                if key in payload:
                    print(f"{key}={payload[key]}")


if __name__ == "__main__":
    main()

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.config.otys import get_otys_settings, validate_otys_settings


def main():
    missing = validate_otys_settings()
    settings = get_otys_settings()

    if missing:
        print("OTYS_CONFIG_MISSING")
        print("\n".join(missing))
        return

    print("OTYS_CONFIG_OK")
    print(f"base_url_set={bool(settings.base_url)}")
    print(f"api_key_set={bool(settings.api_key)}")
    print(f"username_set={bool(settings.username)}")
    print(f"password_set={bool(settings.password)}")
    print(f"user_interface_url_set={bool(settings.user_interface_url)}")


if __name__ == "__main__":
    main()

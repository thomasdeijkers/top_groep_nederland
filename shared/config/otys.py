import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class OtysSettings:
    base_url: str
    api_key: str
    username: str
    password: str
    user_interface_url: str | None = None


def get_otys_settings() -> OtysSettings:
    return OtysSettings(
        base_url=os.getenv("OTYS_BASE_URL", "").strip().rstrip("/"),
        api_key=os.getenv("OTYS_API_KEY", "").strip(),
        username=os.getenv("OTYS_USERNAME", "").strip(),
        password=os.getenv("OTYS_PASSWORD", "").strip(),
        user_interface_url=os.getenv("OTYS_USER_INTERFACE_URL", "").strip() or None,
    )


def validate_otys_settings() -> list[str]:
    settings = get_otys_settings()
    missing = []

    if not settings.base_url:
        missing.append("OTYS_BASE_URL")
    if not settings.api_key:
        missing.append("OTYS_API_KEY")
    if not settings.username:
        missing.append("OTYS_USERNAME")
    if not settings.password:
        missing.append("OTYS_PASSWORD")

    return missing

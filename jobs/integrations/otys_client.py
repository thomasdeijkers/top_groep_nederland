import requests

from shared.config.otys import OtysSettings, get_otys_settings


class OtysClient:
    def __init__(self, settings: OtysSettings | None = None):
        self.settings = settings or get_otys_settings()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def get(self, path: str, params: dict | None = None) -> requests.Response:
        url = f"{self.settings.base_url}/{path.lstrip('/')}"
        return self.session.get(url, params=params, timeout=15)

    def post(self, path: str, payload: dict | None = None) -> requests.Response:
        url = f"{self.settings.base_url}/{path.lstrip('/')}"
        return self.session.post(url, json=payload or {}, timeout=15)

    def authenticate(self) -> requests.Response:
        return self.post("api/auth", {"key": self.settings.api_key})

    def set_access_token(self, access_token: str, token_type: str = "Bearer") -> None:
        self.session.headers["Authorization"] = f"{token_type} {access_token}"

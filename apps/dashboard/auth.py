import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request


router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

SESSION_COOKIE = "tgn_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
PROTECTED_PREFIXES = ("/dashboard", "/api")
PUBLIC_PREFIXES = ("/dashboard/static", "/login", "/logout")


def auth_enabled() -> bool:
    return os.getenv("TGN_AUTH_ENABLED", "").strip().lower() in {"1", "true", "yes", "ja", "on"}


def _required_config() -> dict[str, str] | None:
    config = {
        "username": os.getenv("TGN_AUTH_USERNAME", "").strip(),
        "password_hash": os.getenv("TGN_AUTH_PASSWORD_HASH", "").strip(),
        "totp_secret": os.getenv("TGN_TOTP_SECRET", "").replace(" ", "").strip(),
        "session_secret": os.getenv("TGN_SESSION_SECRET", "").strip(),
    }
    if not all(config.values()) or len(config["session_secret"]) < 32:
        return None
    return config


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, salt: str | None = None, iterations: int = 260_000) -> str:
    salt = salt or secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${_b64_encode(digest)}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
        iteration_count = int(iterations)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    calculated = hash_password(password, salt=salt, iterations=iteration_count).rsplit("$", 1)[1]
    return hmac.compare_digest(calculated, expected)


def _totp_code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8), casefold=True)
    message = counter.to_bytes(8, "big")
    digest = hmac.new(key, message, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return f"{number % 1_000_000:06d}"


def _verify_totp(secret: str, code: str) -> bool:
    normalized = "".join(character for character in code if character.isdigit())
    if len(normalized) != 6:
        return False
    counter = int(time.time() // 30)
    try:
        return any(hmac.compare_digest(_totp_code(secret, counter + drift), normalized) for drift in (-1, 0, 1))
    except ValueError:
        return False


def _sign_session(username: str, session_secret: str) -> str:
    payload = _b64_encode(json.dumps({"sub": username, "exp": int(time.time()) + SESSION_TTL_SECONDS}).encode("utf-8"))
    signature = hmac.new(session_secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{_b64_encode(signature)}"


def _valid_session(cookie_value: str | None, session_secret: str) -> bool:
    if not cookie_value or "." not in cookie_value:
        return False
    payload, signature = cookie_value.rsplit(".", 1)
    expected = _b64_encode(hmac.new(session_secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        data = json.loads(_b64_decode(payload))
    except (ValueError, json.JSONDecodeError):
        return False
    return int(data.get("exp", 0)) >= int(time.time())


def _next_url(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    return f"{path}?{query}" if query else path


def _login_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(f"/login?next={quote(_next_url(request), safe='')}", status_code=303)


def _safe_next(value: str) -> str:
    return value if value.startswith("/") and not value.startswith("//") else "/dashboard"


def _is_protected_path(path: str) -> bool:
    return path == "/" or path == "/test-db" or any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)


async def auth_middleware(request: Request, call_next):
    if not auth_enabled() or any(request.url.path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
        return await call_next(request)
    if not _is_protected_path(request.url.path):
        return await call_next(request)

    config = _required_config()
    if config is None:
        return PlainTextResponse("2FA is ingeschakeld, maar de serverconfiguratie is nog niet compleet.", status_code=503)
    if _valid_session(request.cookies.get(SESSION_COOKIE), config["session_secret"]):
        return await call_next(request)
    if request.url.path.startswith("/api"):
        return PlainTextResponse("Inloggen vereist.", status_code=401)
    return _login_redirect(request)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/dashboard", error: str = ""):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"next": _safe_next(next), "error": error, "auth_enabled": auth_enabled()},
    )


@router.post("/login")
def login(
    username: str = Form(""),
    password: str = Form(""),
    code: str = Form(""),
    next: str = Form("/dashboard"),
):
    if not auth_enabled():
        return RedirectResponse(_safe_next(next), status_code=303)
    config = _required_config()
    if config is None:
        return PlainTextResponse("2FA is ingeschakeld, maar de serverconfiguratie is nog niet compleet.", status_code=503)

    valid_credentials = hmac.compare_digest(username.strip(), config["username"]) and _verify_password(password, config["password_hash"])
    if not valid_credentials or not _verify_totp(config["totp_secret"], code):
        return RedirectResponse(f"/login?next={quote(_safe_next(next), safe='')}&error=1", status_code=303)

    response = RedirectResponse(_safe_next(next), status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _sign_session(config["username"], config["session_secret"]),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response

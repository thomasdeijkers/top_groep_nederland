import requests
import time

from shared.config.otys import OtysSettings, get_otys_settings


RATE_LIMIT_MIN_REMAINING = 5
RATE_LIMIT_MAX_RETRIES = 5


class OtysClient:
    def __init__(self, settings: OtysSettings | None = None):
        self.settings = settings or get_otys_settings()
        self.session = requests.Session()
        self.last_rate_limit = {}
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

    def ows_call(self, method: str, params: list | None = None, request_id: int = 1) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": request_id,
        }

        for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
            started = time.monotonic()
            response = self.session.post(self.settings.ows_url, json=payload, timeout=30)
            duration_ms = int((time.monotonic() - started) * 1000)
            self._update_rate_limit_state(response)

            if response.status_code != 429:
                break

            self._record_usage_event(method, request_id, response.status_code, duration_ms, "rate limited")
            if attempt >= RATE_LIMIT_MAX_RETRIES:
                response.raise_for_status()

            wait_seconds = self._rate_limit_wait_seconds(response)
            print(f"OTYS_RATE_LIMIT_WAIT seconds={wait_seconds}", flush=True)
            time.sleep(wait_seconds)

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            self._record_usage_event(method, request_id, response.status_code, duration_ms, str(exc))
            raise
        result = response.json()
        if "error" in result:
            self._record_usage_event(method, request_id, response.status_code, duration_ms, str(result["error"]))
            raise OtysOwsError(result["error"])
        self._record_usage_event(method, request_id, response.status_code, duration_ms)
        self._pause_when_quota_is_low()
        return result

    def _update_rate_limit_state(self, response: requests.Response) -> None:
        self.last_rate_limit = {
            "blocked": response.headers.get("X-Orl-Limit-Blocked"),
            "remaining_timeframe": response.headers.get("X-Orl-Remaining-Timeframe"),
            "requests_remaining": response.headers.get("X-Orl-Requests-Remaining"),
        }

    def _rate_limit_wait_seconds(self, response: requests.Response) -> int:
        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return max(int(retry_after), 1)

        timeframe = self.last_rate_limit.get("remaining_timeframe")
        if timeframe and str(timeframe).isdigit():
            return max(int(timeframe) + 1, 1)

        return 10

    def _pause_when_quota_is_low(self) -> None:
        remaining = self.last_rate_limit.get("requests_remaining")
        timeframe = self.last_rate_limit.get("remaining_timeframe")
        if not (remaining and timeframe and str(remaining).isdigit() and str(timeframe).isdigit()):
            return

        if int(remaining) <= RATE_LIMIT_MIN_REMAINING:
            wait_seconds = max(int(timeframe) + 1, 1)
            print(
                f"OTYS_RATE_LIMIT_PAUSE requests_remaining={remaining} seconds={wait_seconds}",
                flush=True,
            )
            time.sleep(wait_seconds)

    def _record_usage_event(
        self,
        method: str,
        request_id: int | None,
        status_code: int | None,
        duration_ms: int | None,
        error: str | None = None,
    ) -> None:
        try:
            from apps.dashboard.otys_usage import record_otys_api_usage

            record_otys_api_usage(
                method=method,
                request_id=request_id,
                status_code=status_code,
                duration_ms=duration_ms,
                rate_limit=self.last_rate_limit,
                error=error,
            )
        except Exception:
            return

    def login_by_uid(self) -> str:
        result = self.ows_call("loginByUid", [self.settings.api_key])
        session_id = result.get("result")
        if not session_id:
            raise OtysOwsError({"message": "OWS login returned no session id"})
        return session_id

    def get_list_ex(
        self,
        session_id: str,
        service: str,
        limit: int = 25,
        offset: int = 0,
        what: dict | None = None,
        request_id: int = 100,
    ) -> dict:
        return self.ows_call(
            f"Otys.Services.{service}.getListEx",
            [
                session_id,
                {
                    "excludeLimitCheck": True,
                    "getTotalCount": True,
                    "limit": limit,
                    "offset": offset,
                    "what": what or {"uid": 1},
                },
            ],
            request_id=request_id,
        )

    def get_detail(
        self,
        session_id: str,
        service: str,
        record_id: str,
        what: dict | None = None,
        request_id: int = 200,
    ) -> dict:
        return self.ows_call(
            f"Otys.Services.{service}.getDetail",
            [
                session_id,
                record_id,
                what or {"uid": 1},
                None,
            ],
            request_id=request_id,
        )

    def get_candidate_detail(self, session_id: str, candidate_id: str, what: dict | None = None) -> dict:
        return self.get_detail(session_id, "CandidateService", candidate_id, what=what, request_id=21)

    def get_relations(self, session_id: str, limit: int = 25, offset: int = 0, what: dict | None = None) -> dict:
        return self.get_list_ex(
            session_id,
            "RelationService",
            limit=limit,
            offset=offset,
            what=what or {
                "relation": 1,
                "status": 1,
                "uid": 1,
            },
            request_id=10,
        )

    def get_candidates(self, session_id: str, limit: int = 25, offset: int = 0, what: dict | None = None) -> dict:
        return self.get_list_ex(
            session_id,
            "CandidateService",
            limit=limit,
            offset=offset,
            what=what or {
                "uid": 1,
                "Person": {
                    "firstName": 1,
                    "lastName": 1,
                },
            },
            request_id=20,
        )

    def get_vacancies(self, session_id: str, limit: int = 25, offset: int = 0, what: dict | None = None) -> dict:
        return self.get_list_ex(
            session_id,
            "VacancyService",
            limit=limit,
            offset=offset,
            what=what or {
                "uid": 1,
                "title": 1,
            },
            request_id=30,
        )

    def get_relation_contacts(self, session_id: str, limit: int = 25, offset: int = 0, what: dict | None = None) -> dict:
        return self.get_list_ex(
            session_id,
            "RelationContactService",
            limit=limit,
            offset=offset,
            what=what or {
                "uid": 1,
                "Person": {
                    "firstName": 1,
                    "lastName": 1,
                },
            },
            request_id=40,
        )

    def get_relation_detail(self, session_id: str, relation_id: str) -> dict:
        return self.ows_call(
            "Otys.Services.RelationService.getDetail",
            [
                session_id,
                relation_id,
                {
                    "relation": 1,
                    "uid": 1,
                },
                None,
            ],
            request_id=11,
        )


class OtysOwsError(Exception):
    pass

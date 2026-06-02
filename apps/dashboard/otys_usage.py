from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


_TABLES_READY = False


def record_otys_api_usage(
    method: str,
    request_id: int | None,
    status_code: int | None,
    duration_ms: int | None,
    rate_limit: dict | None = None,
    error: str | None = None,
) -> None:
    try:
        _ensure_tables_once()
        rate_limit = rate_limit or {}
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO otys_api_usage_events (
                        service, method, request_id, status_code, duration_ms,
                        rate_limit_blocked, rate_limit_remaining_timeframe,
                        rate_limit_requests_remaining, error
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        _service_from_method(method),
                        method,
                        request_id,
                        status_code,
                        duration_ms,
                        rate_limit.get("blocked"),
                        _int_or_none(rate_limit.get("remaining_timeframe")),
                        _int_or_none(rate_limit.get("requests_remaining")),
                        error,
                    ),
                )
            conn.commit()
    except Exception:
        return


def get_otys_usage_summary() -> dict:
    try:
        _ensure_tables_once()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM otys_api_usage_events
                    WHERE created_at >= NOW() - INTERVAL '1 minute';
                    """
                )
                minute_calls = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM otys_api_usage_events
                    WHERE created_at >= NOW() - INTERVAL '1 hour';
                    """
                )
                hour_calls = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM otys_api_usage_events
                    WHERE created_at >= NOW() - INTERVAL '24 hours';
                    """
                )
                day_calls = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM otys_api_usage_events
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                      AND (status_code = 429 OR rate_limit_blocked = '1');
                    """
                )
                day_blocked = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT rate_limit_requests_remaining,
                           rate_limit_remaining_timeframe,
                           created_at,
                           status_code,
                           error
                    FROM otys_api_usage_events
                    ORDER BY created_at DESC
                    LIMIT 1;
                    """
                )
                latest = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT MIN(rate_limit_requests_remaining)
                    FROM otys_api_usage_events
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                      AND rate_limit_requests_remaining IS NOT NULL;
                    """
                )
                min_remaining = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT error
                    FROM otys_api_usage_events
                    WHERE error IS NOT NULL AND error <> ''
                    ORDER BY created_at DESC
                    LIMIT 1;
                    """
                )
                last_error_row = cursor.fetchone()
        latest_remaining = latest[0] if latest else None
        latest_timeframe = latest[1] if latest else None
        latest_created = latest[2] if latest else None
        latest_status = latest[3] if latest else None
        latest_error = latest[4] if latest else None
        return {
            "minute_calls": minute_calls,
            "hour_calls": hour_calls,
            "day_calls": day_calls,
            "day_blocked": day_blocked,
            "latest_remaining": latest_remaining,
            "latest_timeframe": latest_timeframe,
            "latest_created": latest_created,
            "latest_status": latest_status,
            "latest_error": latest_error,
            "last_error": last_error_row[0] if last_error_row else "",
            "min_remaining_hour": min_remaining,
        }
    except Exception:
        return {
            "minute_calls": 0,
            "hour_calls": 0,
            "day_calls": 0,
            "day_blocked": 0,
            "latest_remaining": None,
            "latest_timeframe": None,
            "latest_created": None,
            "latest_status": None,
            "latest_error": "",
            "last_error": "",
            "min_remaining_hour": None,
        }


def _service_from_method(method: str) -> str:
    parts = (method or "").split(".")
    if len(parts) >= 3 and parts[0] == "Otys" and parts[1] == "Services":
        return parts[2]
    return "auth" if method == "loginByUid" else "OWS"


def _ensure_tables_once() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return
    ensure_dashboard_tables()
    _TABLES_READY = True


def _int_or_none(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

import os
import time
from decimal import Decimal

from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


MODEL_PRICING_USD_PER_1M = {
    "gpt-4.1-mini": {"input": Decimal("0.40"), "cached_input": Decimal("0.10"), "output": Decimal("1.60")},
    "gpt-5": {"input": Decimal("1.25"), "cached_input": Decimal("0.125"), "output": Decimal("10.00")},
    "gpt-5-mini": {"input": Decimal("0.25"), "cached_input": Decimal("0.025"), "output": Decimal("2.00")},
    "gpt-5-nano": {"input": Decimal("0.05"), "cached_input": Decimal("0.005"), "output": Decimal("0.40")},
}
OPENAI_USAGE_COST_MULTIPLIER = Decimal("4")
_USAGE_CACHE_TTL_SECONDS = 60
_USAGE_CACHE: tuple[float, dict] | None = None


def estimate_openai_cost(model: str, usage: dict) -> Decimal:
    pricing = _pricing(model)
    input_tokens = Decimal(str(max(_int(usage.get("input_tokens")) - _int(usage.get("cached_input_tokens")), 0)))
    cached_tokens = Decimal(str(_int(usage.get("cached_input_tokens"))))
    output_tokens = Decimal(str(_int(usage.get("output_tokens"))))
    cost = (
        input_tokens * pricing["input"]
        + cached_tokens * pricing["cached_input"]
        + output_tokens * pricing["output"]
    ) / Decimal("1000000")
    return cost.quantize(Decimal("0.000001"))


def _pricing(model: str) -> dict:
    if os.getenv("OPENAI_INPUT_USD_PER_1M") or os.getenv("OPENAI_OUTPUT_USD_PER_1M"):
        return {
            "input": _decimal_env("OPENAI_INPUT_USD_PER_1M", "0.25"),
            "cached_input": _decimal_env("OPENAI_CACHED_INPUT_USD_PER_1M", "0.025"),
            "output": _decimal_env("OPENAI_OUTPUT_USD_PER_1M", "2.00"),
        }
    return MODEL_PRICING_USD_PER_1M.get(model, MODEL_PRICING_USD_PER_1M["gpt-4.1-mini"])


def record_openai_usage(source: str, source_id: int | None, model: str, usage: dict) -> None:
    global _USAGE_CACHE
    ensure_dashboard_tables()
    cost = estimate_openai_cost(model, usage)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO openai_usage_events (
                    source, source_id, model, input_tokens, cached_input_tokens,
                    output_tokens, total_tokens, estimated_cost_usd
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    source,
                    source_id,
                    model,
                    _int(usage.get("input_tokens")),
                    _int(usage.get("cached_input_tokens")),
                    _int(usage.get("output_tokens")),
                    _int(usage.get("total_tokens")),
                    cost,
                ),
            )
        conn.commit()
    _USAGE_CACHE = None


def get_openai_usage_summary() -> dict:
    global _USAGE_CACHE
    now = time.monotonic()
    if _USAGE_CACHE and now - _USAGE_CACHE[0] < _USAGE_CACHE_TTL_SECONDS:
        return dict(_USAGE_CACHE[1])

    try:
        ensure_dashboard_tables()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*),
                           COALESCE(SUM(input_tokens), 0),
                           COALESCE(SUM(output_tokens), 0),
                           COALESCE(SUM(total_tokens), 0),
                           COALESCE(SUM(estimated_cost_usd), 0)
                    FROM openai_usage_events;
                    """
                )
                total = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT COUNT(*),
                           COALESCE(SUM(total_tokens), 0),
                           COALESCE(SUM(estimated_cost_usd), 0)
                    FROM openai_usage_events
                    WHERE created_at >= date_trunc('month', NOW());
                    """
                )
                month = cursor.fetchone()
        summary = {
            "requests": total[0],
            "input_tokens": total[1],
            "output_tokens": total[2],
            "total_tokens": total[3],
            "total_cost_usd": _display_cost(total[4]),
            "month_requests": month[0],
            "month_tokens": month[1],
            "month_cost_usd": _display_cost(month[2]),
        }
        _USAGE_CACHE = (now, summary)
        return dict(summary)
    except Exception:
        return {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": Decimal("0"),
            "month_requests": 0,
            "month_tokens": 0,
            "month_cost_usd": Decimal("0"),
        }


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _decimal_env(name: str, fallback: str) -> Decimal:
    try:
        return Decimal(os.getenv(name, fallback))
    except Exception:
        return Decimal(fallback)


def _display_cost(value) -> Decimal:
    return Decimal(str(value or 0)) * OPENAI_USAGE_COST_MULTIPLIER

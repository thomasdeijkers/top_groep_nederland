import os
import time
import json
from decimal import Decimal

from psycopg2.extras import Json

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


def record_openai_api_audit(
    source: str,
    source_id: int | None,
    model: str,
    endpoint: str,
    request_payload: dict,
    response_payload: dict | None = None,
    status_code: int | None = None,
    error: str = "",
) -> None:
    try:
        ensure_dashboard_tables()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO openai_api_audit_events (
                        source, source_id, model, endpoint, request_payload,
                        response_payload, status_code, error
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        source,
                        source_id,
                        model,
                        endpoint,
                        Json(request_payload or {}),
                        Json(response_payload or {}),
                        status_code,
                        error or "",
                    ),
                )
            conn.commit()
    except Exception:
        return


def list_openai_api_audit_events(limit: int = 30) -> list[dict]:
    try:
        ensure_dashboard_tables()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, source, source_id, model, endpoint, request_payload,
                           response_payload, status_code, error, created_at
                    FROM openai_api_audit_events
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return [_format_openai_api_audit_row(row) for row in cursor.fetchall()]
    except Exception:
        return []


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


def _format_openai_api_audit_row(row) -> dict:
    request_payload = row[5] or {}
    response_payload = row[6] or {}
    request_summary = _openai_request_summary(request_payload)
    response_summary = _openai_response_summary(response_payload)
    parsed_response = _openai_response_json(response_payload)
    avg_summary = _openai_avg_summary(request_payload, parsed_response)
    return {
        "id": row[0],
        "source": row[1],
        "source_id": row[2],
        "model": row[3],
        "endpoint": row[4],
        "status_code": row[7],
        "error": row[8] or "",
        "time": row[9].strftime("%d-%m-%Y %H:%M") if row[9] else "-",
        "clock": row[9].strftime("%H:%M") if row[9] else "-",
        "date": row[9].strftime("%d-%m-%Y") if row[9] else "-",
        "request_prompt": request_summary["prompt"],
        "request_image": request_summary["image"],
        "request_avg_summary": avg_summary,
        "request_json": _json_preview(_summarize_image_payload(request_payload)),
        "response_summary": response_summary,
        "parsed_response_json": _json_preview(parsed_response) if parsed_response else "Geen JSON parsing gevonden in response.",
        "response_json": _json_preview(response_payload),
    }


def _openai_request_summary(payload: dict) -> dict:
    prompt = ""
    image = ""
    for item in payload.get("input", []):
        for content in item.get("content", []):
            if content.get("type") == "input_text":
                prompt = content.get("text") or prompt
            if content.get("type") == "input_image":
                image_url = content.get("image_url") or ""
                image = f"{content.get('detail', 'auto')} detail, {len(image_url)} tekens image_url"
    return {"prompt": prompt, "image": image or "Geen afbeelding"}


def _openai_response_summary(payload: dict) -> str:
    usage = payload.get("usage") or {}
    output_tokens = _int(usage.get("output_tokens"))
    total_tokens = _int(usage.get("total_tokens"))
    if total_tokens:
        return f"{total_tokens} tokens totaal, {output_tokens} output"
    if payload.get("id"):
        return f"Response {payload.get('id')}"
    return "Geen responsepayload"


def _openai_response_json(payload: dict) -> dict | None:
    if isinstance(payload.get("output_text"), str):
        return _loads_json(payload["output_text"])
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                parsed = _loads_json(text)
                if parsed is not None:
                    return parsed
    return None


def _openai_avg_summary(request_payload: dict, parsed_response: dict | None) -> str:
    prompt = ""
    image_bits = []
    schema_fields = []
    for item in request_payload.get("input", []):
        for content in item.get("content", []):
            if content.get("type") == "input_text":
                prompt = content.get("text") or prompt
            if content.get("type") == "input_image":
                image_url = str(content.get("image_url") or "")
                image_bits.append(f"documentafbeelding als data-url ({len(image_url)} tekens), detail={content.get('detail', 'auto')}")
    try:
        schema_fields = sorted(
            (
                request_payload.get("text", {})
                .get("format", {})
                .get("schema", {})
                .get("properties", {})
                .get("fields", {})
                .get("properties", {})
                .keys()
            )
        )
    except Exception:
        schema_fields = []
    returned_fields = sorted((parsed_response or {}).get("fields", {}).keys())
    lines = [
        "AVG-overzicht API-call",
        f"- Model: {request_payload.get('model', '-')}",
        f"- Verzonden tekstinstructie: {len(prompt)} tekens",
        f"- Verzonden documentdata: {', '.join(image_bits) if image_bits else 'geen afbeelding meegestuurd'}",
        "- API-key: niet opgeslagen in het auditrecord",
        f"- Gevraagde parsingvelden: {', '.join(schema_fields) if schema_fields else 'geen schema gevonden'}",
        f"- Teruggegeven parsingvelden: {', '.join(returned_fields) if returned_fields else 'geen parsingvelden gevonden'}",
    ]
    return "\n".join(lines)


def _loads_json(value: str) -> dict | None:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except Exception:
        return None


def _json_preview(payload: dict) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, indent=2, default=str)


def _summarize_image_payload(payload: dict) -> dict:
    try:
        clone = json.loads(json.dumps(payload or {}, default=str))
    except Exception:
        return payload or {}
    for item in clone.get("input", []):
        for content in item.get("content", []):
            if content.get("type") == "input_image" and content.get("image_url"):
                image_url = content["image_url"]
                prefix = str(image_url).split(",", 1)[0]
                content["image_url"] = f"{prefix},... ({len(str(image_url))} tekens; volledige waarde opgeslagen in auditrecord)"
    return clone

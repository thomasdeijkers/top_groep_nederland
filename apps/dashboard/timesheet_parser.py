import base64
import json
import mimetypes
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()


FIELD_KEYS = (
    "week_number",
    "date",
    "principal_name",
    "project_number",
    "employee_name",
    "employee_phone",
    "signer_name",
    "signer_phone",
    "work_name",
    "work_number",
    "location",
    "single_trip_km",
    "monday_km",
    "tuesday_km",
    "wednesday_km",
    "thursday_km",
    "friday_km",
    "saturday_km",
    "sunday_km",
    "total_km",
    "monday_hours",
    "tuesday_hours",
    "wednesday_hours",
    "thursday_hours",
    "friday_hours",
    "saturday_hours",
    "sunday_hours",
    "total_hours",
    "monday_code",
    "tuesday_code",
    "wednesday_code",
    "thursday_code",
    "friday_code",
    "saturday_code",
    "sunday_code",
    "calculated_total_hours",
    "total_hours_check",
    "calculated_total_km",
    "total_km_check",
    "absence_code",
    "remarks",
    "signature",
    "expenses",
    "parking_costs",
    "invoice_with_receipt",
    "client_signature",
)


def parse_timesheet(content: bytes, filename: str, allow_openai: bool = False) -> dict:
    standard_result = parse_timesheet_stub(filename)
    if allow_openai and _openai_enabled() and standard_result["overall_confidence"] < _openai_threshold():
        parsed = _parse_with_openai(content, filename)
        if parsed:
            return parsed
    return standard_result


def parse_timesheet_stub(filename: str) -> dict:
    source_name = Path(filename).name
    fields = {key: {"value": "", "confidence": 15} for key in FIELD_KEYS}
    fields["signature"] = {"value": "niet gecontroleerd", "confidence": 15}
    _check_total_hours(fields)
    _check_total_km(fields)

    return {
        "message_text": f"Handmatig geupload urenbriefje: {source_name}",
        "parse_source": "stub",
        "parsed_fields": fields,
        "overall_confidence": _average_confidence(fields),
        "hours": None,
        "break_minutes": None,
        "work_date": None,
        "principal_name": "",
        "project_name": "",
        "employee_name": "",
        "employee_address": "",
        "employee_postal_code": "",
        "employee_city": "",
    }


def _openai_enabled() -> bool:
    enabled = os.getenv("OPENAI_OCR_FALLBACK_ENABLED", "true").strip().lower()
    return bool(os.getenv("OPENAI_API_KEY")) and enabled not in ("0", "false", "nee", "no")


def _openai_threshold() -> Decimal:
    try:
        return Decimal(os.getenv("OPENAI_OCR_CONFIDENCE_THRESHOLD", "70"))
    except Exception:
        return Decimal("70")


def _parse_with_openai(content: bytes, filename: str) -> dict | None:
    image_url = _data_url(content, filename)
    if not image_url:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Lees dit Nederlandse urenbriefje/weekstaat uit. "
                            "Het document kan 90, 180 of 270 graden gedraaid zijn; lees het alsof je het recht draait. "
                            "Neem alleen zichtbaar ingevulde waarden over, niet de voorgedrukte labels. "
                            "Gebruik lege strings voor velden die zichtbaar leeg zijn of niet ingevuld zijn. "
                            "Lege velden blijven leeg en tellen niet mee in de totale score. "
                            "Alleen een onleesbaar of twijfelachtig veld krijgt een lage confidence. "
                            "Confidence is 0-100 per veld. Interpreteer dagen als ma, di, wo, do, vr, za, zo. "
                            "Lees ook kilometers per dag uit de rij 'Aantal kilometers enkele reis' als monday_km t/m sunday_km en total_km. "
                            "Voor signature: kijk visueel in de kolom 'Handtekening' rechts van de weekstaatregels; als daar een krabbel/handtekening staat, vul exact 'aanwezig' in met hoge confidence. "
                            "Voor client_signature: kijk visueel bij 'Handtekening opdrachtgever / stempel' onderaan; als daar een krabbel/stempel staat, vul exact 'aanwezig' in met hoge confidence. "
                            "Behandel handtekeningen als visuele markeringen, niet als OCR-tekst. Laat alleen leeg als het vak echt leeg is. "
                            "Neem ook naam ondertekenaar, telefoon ondertekenaar, werknummer, opmerkingen, verzuimcode, dagcodes, parkeerkosten, factureren met tegenbon ja/nee en handtekening/stempel opdrachtgever over als die zichtbaar zijn. "
                            "Vul calculated_total_hours met de optelsom van ma t/m zo. "
                            "Vul total_hours_check met 'klopt' als de optelsom gelijk is aan het zichtbaar ingevulde totaal. Bij verschil: vermeld beide waarden, bijvoorbeeld 'bijlage 40, som 40,5'. "
                            "Vul calculated_total_km met de optelsom van monday_km t/m sunday_km. "
                            "Vul total_km_check met 'klopt' als de optelsom gelijk is aan total_km. Bij verschil: vermeld beide waarden, bijvoorbeeld 'bijlage 185, som 180'. "
                            "Bij twijfel liever een lagere confidence dan een gok."
                        ),
                    },
                    {"type": "input_image", "image_url": image_url, "detail": "high"},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "timesheet_parse",
                "schema": _json_schema(),
                "strict": True,
            }
        },
    }

    try:
        endpoint = "https://api.openai.com/v1/responses"
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        response_payload = response.json()
        data = _extract_response_json(response_payload)
        if not data:
            return None
        parsed = _normalize_openai_result(data, filename)
        parsed["openai_usage"] = _normalize_usage(response_payload.get("usage") or {})
        parsed["openai_api_audit"] = {
            "model": model,
            "endpoint": endpoint,
            "request_payload": payload,
            "response_payload": response_payload,
            "status_code": response.status_code,
        }
        return parsed
    except Exception:
        return None


def _json_schema() -> dict:
    field_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "value": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 100},
        },
        "required": ["value", "confidence"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "fields": {
                "type": "object",
                "additionalProperties": False,
                "properties": {key: field_schema for key in FIELD_KEYS},
                "required": list(FIELD_KEYS),
            }
        },
        "required": ["fields"],
    }


def _extract_response_json(payload: dict) -> dict | None:
    if isinstance(payload.get("output_text"), str):
        return json.loads(payload["output_text"])
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return json.loads(text)
    return None


def _normalize_openai_result(data: dict, filename: str) -> dict:
    fields = {}
    for key in FIELD_KEYS:
        raw = (data.get("fields") or {}).get(key) or {}
        value = str(raw.get("value") or "").strip()
        if key in {"signature", "client_signature"} and value.lower() in {
            "ja",
            "yes",
            "true",
            "1",
            "getekend",
            "handtekening",
            "stempel",
            "signed",
            "present",
            "aanwezig",
            "ingevuld",
            "krabbel",
        }:
            value = "aanwezig"
        fields[key] = {
            "value": value,
            "confidence": _field_confidence(value, raw.get("confidence")),
        }
    _cap_handwritten_number_confidence(fields)
    _check_total_hours(fields)
    _check_total_km(fields)

    return {
        "message_text": f"OpenAI parsing urenbriefje: {Path(filename).name}",
        "parse_source": "openai",
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini",
        "parsed_fields": fields,
        "overall_confidence": _average_confidence(fields),
        "hours": _decimal_or_none(fields["total_hours"]["value"]),
        "break_minutes": None,
        "work_date": _date_or_none(fields["date"]["value"]),
        "principal_name": fields["principal_name"]["value"],
        "project_name": fields["work_name"]["value"],
        "employee_name": fields["employee_name"]["value"],
        "employee_address": "",
        "employee_postal_code": "",
        "employee_city": fields["location"]["value"],
    }


def _normalize_usage(usage: dict) -> dict:
    input_details = usage.get("input_tokens_details") or {}
    cached_tokens = input_details.get("cached_tokens") or input_details.get("cached_input_tokens") or 0
    return {
        "input_tokens": _safe_int(usage.get("input_tokens")),
        "cached_input_tokens": _safe_int(cached_tokens),
        "output_tokens": _safe_int(usage.get("output_tokens")),
        "total_tokens": _safe_int(usage.get("total_tokens")),
    }


def _cap_handwritten_number_confidence(fields: dict) -> None:
    critical_keys = (
        "monday_hours",
        "tuesday_hours",
        "wednesday_hours",
        "thursday_hours",
        "friday_hours",
        "saturday_hours",
        "sunday_hours",
        "total_hours",
        "monday_km",
        "tuesday_km",
        "wednesday_km",
        "thursday_km",
        "friday_km",
        "saturday_km",
        "sunday_km",
        "total_km",
    )
    for key in critical_keys:
        field = fields.get(key) or {}
        if str(field.get("value") or "").strip():
            field["confidence"] = min(int(field.get("confidence", 0) or 0), 60)
            fields[key] = field


def _data_url(content: bytes, filename: str) -> str | None:
    mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
    if mime_type == "application/pdf":
        return None
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _confidence(value) -> int:
    try:
        return max(0, min(98, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def _field_confidence(value: str, confidence) -> int:
    score = _confidence(confidence)
    if not str(value or "").strip():
        return 0
    return score


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _decimal_or_none(value: str):
    try:
        cleaned = str(value).replace(",", ".").strip()
        return Decimal(cleaned) if cleaned else None
    except Exception:
        return None


def _format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f").rstrip("0").rstrip(".") if "." in format(normalized, "f") else format(normalized, "f")


def _check_total_hours(fields: dict) -> None:
    day_keys = (
        "monday_hours",
        "tuesday_hours",
        "wednesday_hours",
        "thursday_hours",
        "friday_hours",
        "saturday_hours",
        "sunday_hours",
    )
    day_values = [_decimal_or_none(fields.get(key, {}).get("value", "")) for key in day_keys]
    known_days = [value for value in day_values if value is not None]
    if not known_days:
        fields["calculated_total_hours"] = {"value": "", "confidence": 0}
        fields["total_hours_check"] = {"value": "", "confidence": 0}
        return

    calculated = sum(known_days, Decimal("0"))
    day_confidence = min(
        [int((fields.get(key) or {}).get("confidence", 0) or 0) for key in day_keys if _decimal_or_none((fields.get(key) or {}).get("value")) is not None]
        or [0]
    )
    fields["calculated_total_hours"] = {"value": _format_decimal(calculated), "confidence": min(98, day_confidence)}
    stated_total = _decimal_or_none(fields.get("total_hours", {}).get("value", ""))
    if stated_total is None:
        fields["total_hours_check"] = {"value": "totaal ontbreekt", "confidence": min(60, day_confidence)}
        return

    difference = calculated - stated_total
    if difference == 0:
        total_confidence = int(fields.get("total_hours", {}).get("confidence", 0) or 0)
        fields["total_hours_check"] = {"value": "klopt", "confidence": min(98, day_confidence, total_confidence)}
        return

    fields["total_hours_check"] = {"value": f"bijlage {_format_decimal(stated_total)}, som {_format_decimal(calculated)}", "confidence": 60}
    fields["total_hours"]["confidence"] = min(int(fields["total_hours"].get("confidence", 0)), 60)


def _check_total_km(fields: dict) -> None:
    day_keys = (
        "monday_km",
        "tuesday_km",
        "wednesday_km",
        "thursday_km",
        "friday_km",
        "saturday_km",
        "sunday_km",
    )
    day_values = [_decimal_or_none(fields.get(key, {}).get("value", "")) for key in day_keys]
    known_days = [value for value in day_values if value is not None]
    if not known_days:
        fields["calculated_total_km"] = {"value": "", "confidence": 0}
        fields["total_km_check"] = {"value": "", "confidence": 0}
        return

    calculated = sum(known_days, Decimal("0"))
    day_confidence = min(
        [int((fields.get(key) or {}).get("confidence", 0) or 0) for key in day_keys if _decimal_or_none((fields.get(key) or {}).get("value")) is not None]
        or [0]
    )
    fields["calculated_total_km"] = {"value": _format_decimal(calculated), "confidence": min(98, day_confidence)}
    stated_total = _decimal_or_none(fields.get("total_km", {}).get("value", ""))
    if stated_total is None:
        fields["total_km"] = {"value": _format_decimal(calculated), "confidence": min(98, day_confidence)}
        fields["total_km_check"] = {"value": "klopt", "confidence": min(98, day_confidence)}
        return

    difference = calculated - stated_total
    if difference == 0:
        total_confidence = int(fields.get("total_km", {}).get("confidence", 0) or 0)
        fields["total_km_check"] = {"value": "klopt", "confidence": min(98, day_confidence, total_confidence)}
        return

    fields["total_km_check"] = {"value": f"bijlage {_format_decimal(stated_total)}, som {_format_decimal(calculated)}", "confidence": 60}
    fields["total_km"]["confidence"] = min(int(fields["total_km"].get("confidence", 0)), 60)


def _date_or_none(value: str):
    text = (value or "").strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _average_confidence(fields: dict) -> Decimal:
    values = [
        field["confidence"]
        for field in fields.values()
        if str(field.get("value", "")).strip()
    ]
    if not values:
        return Decimal("0")
    return Decimal(str(round(sum(values) / len(values), 2)))

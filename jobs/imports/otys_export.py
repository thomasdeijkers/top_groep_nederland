import csv
import io
import re
from dataclasses import dataclass

from psycopg2.extras import Json

from shared.db.connection import get_connection


HEADER_ALIASES = {
    "otys_id": ("otys_id", "otys id", "id", "relatie id", "customer id", "company id"),
    "name": ("name", "naam", "bedrijfsnaam", "bedrijf", "company", "organisatie"),
    "email": ("email", "e-mail", "mail", "emailadres"),
    "phone": ("phone", "telefoon", "tel", "mobile", "mobiel"),
    "website": ("website", "site", "web"),
    "city": ("city", "plaats", "stad", "woonplaats"),
}


@dataclass
class ImportPreview:
    total_rows: int
    valid_rows: int
    skipped_rows: int
    sample: list[dict]
    errors: list[str]


def parse_otys_csv(content: bytes, organization_type: str) -> tuple[list[dict], ImportPreview]:
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text), delimiter=_detect_delimiter(text))
    rows = []
    errors = []

    for index, source_row in enumerate(reader, start=2):
        row = _normalize_row(source_row, organization_type)
        if not row["name"]:
            errors.append(f"Rij {index}: naam ontbreekt")
            continue
        rows.append(row)

    preview = ImportPreview(
        total_rows=max((reader.line_num or 1) - 1, 0),
        valid_rows=len(rows),
        skipped_rows=len(errors),
        sample=rows[:5],
        errors=errors[:10],
    )
    return rows, preview


def import_otys_organizations(rows: list[dict]) -> dict:
    ensure_otys_tables()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO otys_organizations (
                        otys_id,
                        organization_type,
                        name,
                        email,
                        phone,
                        website,
                        city,
                        raw_data,
                        synced_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (otys_id) DO UPDATE SET
                        organization_type = EXCLUDED.organization_type,
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        website = EXCLUDED.website,
                        city = EXCLUDED.city,
                        raw_data = EXCLUDED.raw_data,
                        synced_at = NOW(),
                        updated_at = NOW();
                    """,
                    (
                        row["otys_id"],
                        row["organization_type"],
                        row["name"],
                        row["email"],
                        row["phone"],
                        row["website"],
                        row["city"],
                        Json(row["raw_data"]),
                    ),
                )
        conn.commit()

    return {"imported": len(rows)}


def ensure_otys_tables():
    with open("migrations/001_otys_organizations.sql", encoding="utf-8") as migration:
        sql = migration.read()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()


def _normalize_row(source_row: dict, organization_type: str) -> dict:
    normalized = {}
    source_lookup = {_clean_header(key): value for key, value in source_row.items()}

    for target, aliases in HEADER_ALIASES.items():
        normalized[target] = _first_value(source_lookup, aliases)

    if not normalized["otys_id"] and normalized["name"]:
        normalized["otys_id"] = f"export:{organization_type}:{_slug(normalized['name'])}"

    return {
        "otys_id": normalized["otys_id"],
        "organization_type": organization_type,
        "name": normalized["name"],
        "email": normalized["email"],
        "phone": normalized["phone"],
        "website": normalized["website"],
        "city": normalized["city"],
        "raw_data": {key: value for key, value in source_row.items() if value not in (None, "")},
    }


def _decode_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _detect_delimiter(text: str) -> str:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if first_line.count(";") > first_line.count(","):
        return ";"
    return ","


def _first_value(source_lookup: dict, aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        value = source_lookup.get(_clean_header(alias))
        if value:
            return value.strip()
    return ""


def _clean_header(header: str | None) -> str:
    return (header or "").strip().lower()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"

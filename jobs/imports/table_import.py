import csv
import io
import re
from dataclasses import dataclass

from psycopg2.extras import Json

from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


COMMON_ALIASES = {
    "external_id": ("external_id", "otys_id", "otys id", "id", "nummer", "poe"),
    "name": ("name", "naam", "kandidaat", "bedrijfsnaam", "bedrijf", "opdrachtgever"),
    "email": ("email", "e-mail", "mail", "emailadres"),
    "phone": ("phone", "telefoon", "mobiel", "mobile", "mobiele telefoon"),
    "city": ("city", "plaats", "stad", "woonplaats"),
    "status": ("status", "fase", "workflow"),
    "source": ("source", "bron", "herkomst"),
    "website": ("website", "site", "web"),
    "motivation": ("motivation", "motivatie", "korte beschrijving", "omschrijving"),
    "title": ("title", "titel", "vacature", "functie", "functie titel"),
    "reference_number": ("referencenumber", "referentienummer", "referentie", "vacaturenummer"),
    "owner": ("owner", "eigenaar", "beheerder"),
    "relation_name": ("relation", "relatie", "opdrachtgever", "klant"),
    "location": ("location", "locatie", "plaats", "standplaats"),
    "publication_status": ("publication status", "publicatie", "gepubliceerd", "publicatiestatus"),
    "applicant_count": ("applicants", "aantal", "aantal sollicitanten", "sollicitanten"),
}


@dataclass
class ImportResult:
    total_rows: int
    valid_rows: int
    skipped_rows: int
    sample: list[dict]
    errors: list[str]


def parse_csv(content: bytes, target: str) -> tuple[list[dict], ImportResult]:
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text), delimiter=_detect_delimiter(text))
    rows = []
    errors = []

    for index, source_row in enumerate(reader, start=2):
        row = _normalize_row(source_row)
        required_name = row["title"] if target == "vacancy" else row["name"]
        if not required_name:
            errors.append(f"Rij {index}: naam ontbreekt")
            continue
        if not row["external_id"]:
            row["external_id"] = f"import:{target}:{_slug(required_name)}"
        rows.append(row)

    return rows, ImportResult(
        total_rows=max((reader.line_num or 1) - 1, 0),
        valid_rows=len(rows),
        skipped_rows=len(errors),
        sample=rows[:5],
        errors=errors[:10],
    )


def import_candidates(rows: list[dict]) -> dict:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO relations (
                        relation_type, external_id, name, email, phone, city, status, source,
                        motivation, raw_data, imported_at, updated_at
                    )
                    VALUES ('candidate', %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (relation_type, external_id)
                    WHERE external_id IS NOT NULL
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        city = EXCLUDED.city,
                        status = EXCLUDED.status,
                        source = EXCLUDED.source,
                        motivation = EXCLUDED.motivation,
                        raw_data = EXCLUDED.raw_data,
                        imported_at = NOW(),
                        updated_at = NOW();
                    """,
                    (
                        row["external_id"], row["name"], row["email"], row["phone"],
                        row["city"], row["status"], row["source"], row["motivation"],
                        Json(row["raw_data"]),
                    ),
                )
        conn.commit()
    return {"imported": len(rows)}


def import_principals(rows: list[dict]) -> dict:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO relations (
                        relation_type, external_id, name, email, phone, website, city, status,
                        source, raw_data, imported_at, updated_at
                    )
                    VALUES ('principal', %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (relation_type, external_id)
                    WHERE external_id IS NOT NULL
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        website = EXCLUDED.website,
                        city = EXCLUDED.city,
                        status = EXCLUDED.status,
                        source = EXCLUDED.source,
                        raw_data = EXCLUDED.raw_data,
                        imported_at = NOW(),
                        updated_at = NOW();
                    """,
                    (
                        row["external_id"], row["name"], row["email"], row["phone"],
                        row["website"], row["city"], row["status"], row["source"],
                        Json(row["raw_data"]),
                    ),
                )
        conn.commit()
    return {"imported": len(rows)}


def import_vacancies(rows: list[dict]) -> dict:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO vacancies (
                        external_id, title, reference_number, status, owner,
                        relation_name, location, publication_status,
                        applicant_count, raw_data, imported_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (external_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        reference_number = EXCLUDED.reference_number,
                        status = EXCLUDED.status,
                        owner = EXCLUDED.owner,
                        relation_name = EXCLUDED.relation_name,
                        location = EXCLUDED.location,
                        publication_status = EXCLUDED.publication_status,
                        applicant_count = EXCLUDED.applicant_count,
                        raw_data = EXCLUDED.raw_data,
                        imported_at = NOW(),
                        updated_at = NOW();
                    """,
                    (
                        row["external_id"], row["title"], row["reference_number"],
                        row["status"], row["owner"], row["relation_name"],
                        row["location"], row["publication_status"] or "concept",
                        _to_int(row["applicant_count"]), Json(row["raw_data"]),
                    ),
                )
        conn.commit()
    return {"imported": len(rows)}


def _normalize_row(source_row: dict) -> dict:
    lookup = {_clean_header(key): value for key, value in source_row.items()}
    row = {key: _first_value(lookup, aliases) for key, aliases in COMMON_ALIASES.items()}
    row["raw_data"] = {key: value for key, value in source_row.items() if value not in (None, "")}
    return row


def _decode_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _detect_delimiter(text: str) -> str:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    return ";" if first_line.count(";") > first_line.count(",") else ","


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
    return slug or "record"


def _to_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

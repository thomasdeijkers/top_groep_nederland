import re
from uuid import uuid4

from psycopg2.extras import Json

from jobs.imports.otys_export import ensure_otys_tables
from shared.db.connection import get_connection


def list_organizations(limit: int = 25) -> list[dict]:
    try:
        ensure_otys_tables()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT organization_type, name, email, city
                    FROM otys_organizations
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return [
                    {
                        "type": _format_type(row[0]),
                        "name": row[1],
                        "contact": row[2] or "-",
                        "city": row[3] or "-",
                        "status": "Database",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def create_organization(
    organization_type: str,
    name: str,
    email: str = "",
    phone: str = "",
    website: str = "",
    city: str = "",
) -> dict:
    ensure_otys_tables()

    clean_type = organization_type if organization_type in ("klant", "opdrachtgever") else "klant"
    clean_name = name.strip()
    otys_id = f"manual:{clean_type}:{_slug(clean_name)}:{uuid4().hex[:8]}"

    with get_connection() as conn:
        with conn.cursor() as cursor:
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
                RETURNING id, otys_id;
                """,
                (
                    otys_id,
                    clean_type,
                    clean_name,
                    email.strip() or None,
                    phone.strip() or None,
                    website.strip() or None,
                    city.strip() or None,
                    Json({"source": "manual_dashboard"}),
                ),
            )
            record_id, created_otys_id = cursor.fetchone()
        conn.commit()

    return {"id": record_id, "otys_id": created_otys_id}


def _format_type(organization_type: str) -> str:
    if organization_type == "opdrachtgever":
        return "Opdrachtgever"
    return "Klant"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "organisatie"

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from psycopg2.extras import RealDictCursor

from apps.dashboard.addressing import split_street_house_number
from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection

RELATION_PHOTO_DIR = Path("runtime/uploads/relations")


def get_relation(relation_id: int) -> dict | None:
    try:
        ensure_dashboard_tables()
    except Exception as exc:
        print(f"RELATION_READ_SCHEMA_WARNING {type(exc).__name__}: {exc}")
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM relations WHERE id = %s;", (relation_id,))
            record = cursor.fetchone()
            if not record:
                return None
            relation = dict(record)
            street, house_number, addition = split_street_house_number(
                relation.get("street") or relation.get("address"),
                relation.get("house_number"),
                relation.get("house_number_addition"),
            )
            relation["street"] = street
            relation["house_number"] = house_number
            relation["house_number_addition"] = addition
            return relation


def get_candidate(candidate_id: int) -> dict | None:
    return _get_relation("candidate", candidate_id)


def get_principal(principal_id: int) -> dict | None:
    return _get_relation("principal", principal_id)


def get_vacancy(vacancy_id: int) -> dict | None:
    return _get_record("vacancies", vacancy_id)


def create_relation(data: dict, photo: dict | None = None) -> int:
    relation_type = _relation_type(data)
    payload = _relation_payload(data, relation_type)
    if photo:
        payload.update(photo)

    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO relations (
                    relation_type, name, first_name, last_name, contact_name,
                    email, phone, website, address, street, house_number,
                    house_number_addition, postal_code, city, country,
                    status, source, owner, availability, hourly_rate, kvk_number,
                    vat_number, notes, photo_filename, photo_path, archived_at,
                    payroll_license_plate, payroll_choice_budget, payroll_phase,
                    payroll_pension, payroll_cao_hours, payroll_days_right,
                    payroll_scale, payroll_function, payroll_hourly_wage,
                    payroll_settings_updated_at, updated_at
                )
                VALUES (
                    %(relation_type)s, %(name)s, %(first_name)s, %(last_name)s,
                    %(contact_name)s, %(email)s, %(phone)s, %(website)s,
                    %(address)s, %(street)s, %(house_number)s,
                    %(house_number_addition)s, %(postal_code)s, %(city)s, %(country)s,
                    %(status)s, %(source)s, %(owner)s, %(availability)s,
                    %(hourly_rate)s, %(kvk_number)s, %(vat_number)s, %(notes)s,
                    %(photo_filename)s, %(photo_path)s, %(archived_at)s,
                    %(payroll_license_plate)s, %(payroll_choice_budget)s,
                    %(payroll_phase)s, %(payroll_pension)s, %(payroll_cao_hours)s,
                    %(payroll_days_right)s, %(payroll_scale)s, %(payroll_function)s,
                    %(payroll_hourly_wage)s,
                    CASE WHEN %(has_payroll_settings)s THEN NOW() ELSE NULL END,
                    NOW()
                )
                RETURNING id;
                """,
                payload,
            )
            record_id = cursor.fetchone()[0]
        conn.commit()
    return record_id


def update_relation(relation_id: int, data: dict, photo: dict | None = None) -> None:
    existing = get_relation(relation_id)
    if not existing:
        return

    relation_type = _relation_type(data)
    payload = _relation_payload(data, relation_type)
    payload["id"] = relation_id
    payload["photo_filename"] = existing.get("photo_filename")
    payload["photo_path"] = existing.get("photo_path")
    if photo:
        payload.update(photo)

    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE relations
                SET relation_type = %(relation_type)s,
                    name = %(name)s,
                    first_name = %(first_name)s,
                    last_name = %(last_name)s,
                    contact_name = %(contact_name)s,
                    email = %(email)s,
                    phone = %(phone)s,
                    website = %(website)s,
                    address = %(address)s,
                    street = %(street)s,
                    house_number = %(house_number)s,
                    house_number_addition = %(house_number_addition)s,
                    postal_code = %(postal_code)s,
                    city = %(city)s,
                    country = %(country)s,
                    status = %(status)s,
                    source = %(source)s,
                    owner = %(owner)s,
                    availability = %(availability)s,
                    hourly_rate = %(hourly_rate)s,
                    kvk_number = %(kvk_number)s,
                    vat_number = %(vat_number)s,
                    notes = %(notes)s,
                    photo_filename = %(photo_filename)s,
                    photo_path = %(photo_path)s,
                    archived_at = %(archived_at)s,
                    payroll_license_plate = %(payroll_license_plate)s,
                    payroll_choice_budget = %(payroll_choice_budget)s,
                    payroll_phase = %(payroll_phase)s,
                    payroll_pension = %(payroll_pension)s,
                    payroll_cao_hours = %(payroll_cao_hours)s,
                    payroll_days_right = %(payroll_days_right)s,
                    payroll_scale = %(payroll_scale)s,
                    payroll_function = %(payroll_function)s,
                    payroll_hourly_wage = %(payroll_hourly_wage)s,
                    payroll_settings_updated_at = CASE
                        WHEN %(has_payroll_settings)s THEN NOW()
                        ELSE payroll_settings_updated_at
                    END,
                    updated_at = NOW()
                WHERE id = %(id)s;
                """,
                payload,
            )
        conn.commit()


def delete_relation(relation_id: int) -> None:
    _delete_record("relations", relation_id)


def archive_relation(relation_id: int) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE relations
                SET archived_at = NOW(),
                    status = 'Archief',
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (relation_id,),
            )
        conn.commit()


def create_candidate(data: dict) -> int:
    ensure_dashboard_tables()
    name = _full_name(data)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO relations (
                    relation_type, name, first_name, last_name, email, phone, city, status,
                    source, address, postal_code, country, owner, availability,
                    hourly_rate, notes, updated_at
                )
                VALUES ('candidate', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id;
                """,
                (
                    name,
                    data.get("first_name"),
                    data.get("last_name"),
                    data.get("email"),
                    data.get("phone"),
                    data.get("city"),
                    data.get("status") or "Nieuw",
                    data.get("source"),
                    data.get("address"),
                    data.get("postal_code"),
                    data.get("country"),
                    data.get("owner"),
                    data.get("availability"),
                    data.get("hourly_rate"),
                    data.get("notes"),
                ),
            )
            record_id = cursor.fetchone()[0]
        conn.commit()
    return record_id


def update_candidate(candidate_id: int, data: dict) -> None:
    ensure_dashboard_tables()
    name = _full_name(data)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE relations
                SET name = %s,
                    first_name = %s,
                    last_name = %s,
                    email = %s,
                    phone = %s,
                    city = %s,
                    status = %s,
                    source = %s,
                    address = %s,
                    postal_code = %s,
                    country = %s,
                    owner = %s,
                    availability = %s,
                    hourly_rate = %s,
                    notes = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND relation_type = 'candidate';
                """,
                (
                    name,
                    data.get("first_name"),
                    data.get("last_name"),
                    data.get("email"),
                    data.get("phone"),
                    data.get("city"),
                    data.get("status"),
                    data.get("source"),
                    data.get("address"),
                    data.get("postal_code"),
                    data.get("country"),
                    data.get("owner"),
                    data.get("availability"),
                    data.get("hourly_rate"),
                    data.get("notes"),
                    candidate_id,
                ),
            )
        conn.commit()


def create_principal(data: dict) -> int:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO relations (
                    relation_type, name, contact_name, email, phone, website, city, status,
                    source, address, postal_code, country, kvk_number,
                    vat_number, notes, updated_at
                )
                VALUES ('principal', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id;
                """,
                (
                    data.get("name"),
                    data.get("contact_name"),
                    data.get("email"),
                    data.get("phone"),
                    data.get("website"),
                    data.get("city"),
                    data.get("status") or "Nieuw",
                    data.get("source"),
                    data.get("address"),
                    data.get("postal_code"),
                    data.get("country"),
                    data.get("kvk_number"),
                    data.get("vat_number"),
                    data.get("notes"),
                ),
            )
            record_id = cursor.fetchone()[0]
        conn.commit()
    return record_id


def update_principal(principal_id: int, data: dict) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE relations
                SET name = %s,
                    contact_name = %s,
                    email = %s,
                    phone = %s,
                    website = %s,
                    city = %s,
                    status = %s,
                    source = %s,
                    address = %s,
                    postal_code = %s,
                    country = %s,
                    kvk_number = %s,
                    vat_number = %s,
                    notes = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND relation_type = 'principal';
                """,
                (
                    data.get("name"),
                    data.get("contact_name"),
                    data.get("email"),
                    data.get("phone"),
                    data.get("website"),
                    data.get("city"),
                    data.get("status"),
                    data.get("source"),
                    data.get("address"),
                    data.get("postal_code"),
                    data.get("country"),
                    data.get("kvk_number"),
                    data.get("vat_number"),
                    data.get("notes"),
                    principal_id,
                ),
            )
        conn.commit()


def delete_candidate(candidate_id: int) -> None:
    _delete_relation("candidate", candidate_id)


def delete_principal(principal_id: int) -> None:
    _delete_relation("principal", principal_id)


def save_relation_photo(content: bytes, filename: str) -> dict | None:
    if not content or not filename:
        return None
    RELATION_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid4().hex}_{Path(filename).name}"
    file_path = RELATION_PHOTO_DIR / safe_name
    file_path.write_bytes(content)
    return {"photo_filename": filename, "photo_path": str(file_path)}


def create_vacancy(data: dict) -> int:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vacancies (
                    title, reference_number, status, owner, relation_name, location,
                    publication_status, website_enabled, indeed_enabled,
                    applicant_count, category, subcategory, contact_email,
                    contact_name, country, province, internal_notes, description,
                    requirements, benefits, region, function_group, employment_type,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id;
                """,
                _vacancy_values(data),
            )
            record_id = cursor.fetchone()[0]
        conn.commit()
    return record_id


def update_vacancy(vacancy_id: int, data: dict) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE vacancies
                SET title = %s,
                    reference_number = %s,
                    status = %s,
                    owner = %s,
                    relation_name = %s,
                    location = %s,
                    publication_status = %s,
                    website_enabled = %s,
                    indeed_enabled = %s,
                    applicant_count = %s,
                    category = %s,
                    subcategory = %s,
                    contact_email = %s,
                    contact_name = %s,
                    country = %s,
                    province = %s,
                    internal_notes = %s,
                    description = %s,
                    requirements = %s,
                    benefits = %s,
                    region = %s,
                    function_group = %s,
                    employment_type = %s,
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (*_vacancy_values(data), vacancy_id),
            )
        conn.commit()


def delete_vacancy(vacancy_id: int) -> None:
    _delete_record("vacancies", vacancy_id)


def _get_record(table_name: str, record_id: int) -> dict | None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(f"SELECT * FROM {table_name} WHERE id = %s;", (record_id,))
            record = cursor.fetchone()
            return dict(record) if record else None


def _get_relation(relation_type: str, record_id: int) -> dict | None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM relations
                WHERE id = %s
                  AND relation_type = %s;
                """,
                (record_id, relation_type),
            )
            record = cursor.fetchone()
            return dict(record) if record else None


def _delete_record(table_name: str, record_id: int) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table_name} WHERE id = %s;", (record_id,))
        conn.commit()


def _delete_relation(relation_type: str, record_id: int) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM relations
                WHERE id = %s
                  AND relation_type = %s;
                """,
                (record_id, relation_type),
            )
        conn.commit()


def _full_name(data: dict) -> str:
    name = " ".join(part for part in (data.get("first_name"), data.get("last_name")) if part)
    return name or data.get("name") or "Naam onbekend"


def _relation_type(data: dict) -> str:
    return "principal" if data.get("relation_type") == "principal" else "candidate"


def _relation_payload(data: dict, relation_type: str) -> dict:
    name = data.get("name") or _full_name(data)
    if relation_type == "candidate":
        name = _full_name(data)
    street, house_number, addition = split_street_house_number(
        data.get("street") or data.get("address"),
        data.get("house_number"),
        data.get("house_number_addition"),
    )
    address_data = {**data, "street": street, "house_number": house_number, "house_number_addition": addition}
    return {
        "relation_type": relation_type,
        "name": name or "Naam onbekend",
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "contact_name": data.get("contact_name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "website": data.get("website"),
        "street": street,
        "house_number": house_number,
        "house_number_addition": addition,
        "address": _compose_address(address_data),
        "postal_code": data.get("postal_code"),
        "city": data.get("city"),
        "country": data.get("country"),
        "status": _relation_status(data),
        "source": data.get("source"),
        "owner": data.get("owner"),
        "availability": data.get("availability"),
        "hourly_rate": data.get("hourly_rate"),
        "payroll_license_plate": data.get("payroll_license_plate"),
        "payroll_choice_budget": data.get("payroll_choice_budget"),
        "payroll_phase": data.get("payroll_phase"),
        "payroll_pension": data.get("payroll_pension"),
        "payroll_cao_hours": data.get("payroll_cao_hours"),
        "payroll_days_right": data.get("payroll_days_right"),
        "payroll_scale": data.get("payroll_scale"),
        "payroll_function": data.get("payroll_function"),
        "payroll_hourly_wage": data.get("payroll_hourly_wage"),
        "has_payroll_settings": any(
            (data.get(key) or "").strip()
            for key in (
                "payroll_license_plate",
                "payroll_choice_budget",
                "payroll_phase",
                "payroll_pension",
                "payroll_cao_hours",
                "payroll_days_right",
                "payroll_scale",
                "payroll_function",
                "payroll_hourly_wage",
            )
        ),
        "kvk_number": data.get("kvk_number"),
        "vat_number": data.get("vat_number"),
        "notes": data.get("notes"),
        "photo_filename": data.get("photo_filename"),
        "photo_path": data.get("photo_path"),
        "archived_at": datetime.now() if _relation_status(data) == "Archief" else None,
    }


def _compose_address(data: dict) -> str:
    street = data.get("street") or data.get("address") or ""
    house_number = data.get("house_number") or ""
    addition = data.get("house_number_addition") or ""
    return " ".join(part for part in (street, house_number, addition) if part).strip()


def _relation_status(data: dict) -> str:
    status = (data.get("status") or "Actief").strip().lower()
    return "Archief" if status in ("archief", "gearchiveerd", "archived") else "Actief"


def _vacancy_values(data: dict) -> tuple:
    return (
        data.get("title"),
        data.get("reference_number"),
        data.get("status") or "Concept",
        data.get("owner"),
        data.get("relation_name"),
        data.get("location"),
        data.get("publication_status") or "concept",
        _to_bool(data.get("website_enabled")),
        _to_bool(data.get("indeed_enabled")),
        _to_int(data.get("applicant_count")),
        data.get("category"),
        data.get("subcategory"),
        data.get("contact_email"),
        data.get("contact_name"),
        data.get("country"),
        data.get("province"),
        data.get("internal_notes"),
        data.get("description"),
        data.get("requirements"),
        data.get("benefits"),
        data.get("region"),
        data.get("function_group"),
        data.get("employment_type"),
    )


def _to_bool(value) -> bool:
    return value in (True, "true", "1", "on", "yes", "ja")


def _to_int(value) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0

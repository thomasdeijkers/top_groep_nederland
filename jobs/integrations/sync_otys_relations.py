import argparse
import sys
from pathlib import Path

from psycopg2.extras import Json

sys.path.append(str(Path(__file__).resolve().parents[2]))

from apps.dashboard.data_store import ensure_dashboard_tables
from jobs.imports.otys_export import ensure_otys_tables
from jobs.integrations.otys_client import OtysClient
from shared.db.connection import get_connection


DEFAULT_LIMIT = 100
RELATION_FIELDS = {
    "uid": 1,
    "relation": 1,
    "status": 1,
    "email": 1,
    "phoneNumberMain": 1,
    "website": 1,
    "city": 1,
    "entryDateTime": 1,
}
CANDIDATE_FIELDS = {
    "uid": 1,
    "status": 1,
    "entryDateTime": 1,
    "Person": {
        "firstName": 1,
        "lastName": 1,
        "emailPrimary": 1,
    },
}
CANDIDATE_DETAIL_FIELD_GROUPS = [
    {
        "_label": "Addresses",
        "uid": 1,
        "Addresses": {
            "address": 1,
            "city": 1,
            "postcode": 1,
            "countryCode": 1,
        },
    },
    {
        "_label": "ExtraPhoneNumbers",
        "uid": 1,
        "ExtraPhoneNumbers": {
            "phoneNumber": 1,
        },
    },
]
VACANCY_FIELDS = {
    "uid": 1,
    "title": 1,
    "referenceNr": 1,
    "status": 1,
    "relation": 1,
    "location": 1,
    "entryDateTime": 1,
}
CONTACT_FIELDS = {
    "uid": 1,
    "relation": 1,
    "Person": {
        "firstName": 1,
        "lastName": 1,
        "emailPrimary": 1,
    },
}


def main():
    parser = argparse.ArgumentParser(description="Synchroniseer OTYS opdrachtgevers en kandidaten naar het dashboard.")
    parser.add_argument("--apply", action="store_true", help="Schrijf de opgehaalde relaties naar de database.")
    parser.add_argument("--replace", action="store_true", help="Vervang bestaande OTYS-records in onze database.")
    parser.add_argument("--clear-demo", action="store_true", help="Verwijder demo/testrecords voor de gekozen target.")
    parser.add_argument("--target", choices=("all", "principals", "candidates", "contacts", "vacancies"), default="all")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Aantal records per OTYS-request.")
    parser.add_argument("--max", type=int, default=0, help="Maximaal aantal records per type ophalen. 0 betekent alles.")
    args = parser.parse_args()

    if args.replace and not args.apply:
        print("OTYS_SYNC_ERROR")
        print("--replace kan alleen samen met --apply")
        return

    client = OtysClient()
    session_id = client.login_by_uid()
    principal_rows = []
    candidate_rows = []
    principal_total = 0
    candidate_total = 0
    vacancy_rows = []
    vacancy_total = 0
    contact_rows = []
    contact_total = 0

    if args.target in ("all", "principals"):
        rows, principal_total = fetch_all(
            lambda batch_limit, offset: client.get_relations(
                session_id,
                limit=batch_limit,
                offset=offset,
                what=RELATION_FIELDS,
            ),
            label="principals",
            limit=args.limit,
            max_rows=args.max,
        )
        principal_rows = [normalize_principal(row) for row in rows if row.get("uid") and row.get("relation")]

    if args.target in ("all", "candidates"):
        rows, candidate_total = fetch_all(
            lambda batch_limit, offset: client.get_candidates(
                session_id,
                limit=batch_limit,
                offset=offset,
                what=CANDIDATE_FIELDS,
            ),
            label="candidates",
            limit=args.limit,
            max_rows=args.max,
        )
        rows = enrich_candidate_details(client, session_id, rows)
        candidate_rows = [normalize_candidate(row) for row in rows if row.get("uid") and candidate_name(row)]

    if args.target in ("all", "vacancies"):
        rows, vacancy_total = fetch_all(
            lambda batch_limit, offset: client.get_vacancies(
                session_id,
                limit=batch_limit,
                offset=offset,
                what=VACANCY_FIELDS,
            ),
            label="vacancies",
            limit=args.limit,
            max_rows=args.max,
        )
        vacancy_rows = [normalize_vacancy(row) for row in rows if row.get("uid") and row.get("title")]

    if args.target in ("all", "contacts"):
        rows, contact_total = fetch_all(
            lambda batch_limit, offset: client.get_relation_contacts(
                session_id,
                limit=batch_limit,
                offset=offset,
                what=CONTACT_FIELDS,
            ),
            label="contacts",
            limit=args.limit,
            max_rows=args.max,
        )
        contact_rows = [normalize_contact(row) for row in rows if row.get("uid") and contact_display_name(row)]

    print("OTYS_SYNC_PREVIEW" if not args.apply else "OTYS_SYNC_APPLY")
    print(f"target={args.target}")
    print(f"principals_total_count={principal_total}")
    print(f"principals_valid_for_import={len(principal_rows)}")
    print(f"candidates_total_count={candidate_total}")
    print(f"candidates_valid_for_import={len(candidate_rows)}")
    print(f"vacancies_total_count={vacancy_total}")
    print(f"vacancies_valid_for_import={len(vacancy_rows)}")
    print(f"contacts_total_count={contact_total}")
    print(f"contacts_valid_for_import={len(contact_rows)}")

    if principal_rows:
        first = principal_rows[0]
        print(f"first_principal_otys_id={first['otys_id']}")
        print(f"first_principal_name={first['name']}")
    if candidate_rows:
        first = candidate_rows[0]
        print(f"first_candidate_otys_id={first['otys_id']}")
        print(f"first_candidate_name={first['name']}")
    if vacancy_rows:
        first = vacancy_rows[0]
        print(f"first_vacancy_otys_id={first['otys_id']}")
        print(f"first_vacancy_title={first['title']}")
    if contact_rows:
        first = contact_rows[0]
        print(f"first_contact_otys_id={first['otys_id']}")
        print(f"first_contact_name={first['name']}")

    if not args.apply:
        print("dry_run=True")
        print("Gebruik --apply om te schrijven, eventueel met --replace om oude OTYS-data te vervangen.")
        return

    result = upsert_records(
        principal_rows,
        candidate_rows,
        contact_rows,
        vacancy_rows,
        replace=args.replace,
        clear_demo=args.clear_demo,
        target=args.target,
    )
    print(f"replace={args.replace}")
    print(f"clear_demo={args.clear_demo}")
    print(f"principals_imported={result['principals_imported']}")
    print(f"candidates_imported={result['candidates_imported']}")
    print(f"contacts_imported={result['contacts_imported']}")
    print(f"vacancies_imported={result['vacancies_imported']}")


def fetch_all(fetch_page, label: str, limit: int, max_rows: int = 0) -> tuple[list[dict], int]:
    rows = []
    total_count = None
    offset = 0

    while True:
        batch_limit = _batch_limit(limit, max_rows, len(rows))
        if batch_limit <= 0:
            break

        response = fetch_page(batch_limit, offset)
        result = response.get("result", {})
        batch = extract_rows(result)
        if total_count is None:
            total_count = extract_total_count(result) or len(batch)

        rows.extend(batch)
        offset += batch_limit
        print(
            f"progress_fetch_{label}={len(rows)}/{total_count or '?'}",
            flush=True,
        )

        if not batch or len(rows) >= total_count:
            break
        if max_rows and len(rows) >= max_rows:
            break

    return rows[:max_rows] if max_rows else rows, total_count or len(rows)


def enrich_candidate_details(client: OtysClient, session_id: str, rows: list[dict]) -> list[dict]:
    enriched_rows = []
    total = len(rows)
    disabled_groups = set()
    for index, row in enumerate(rows, start=1):
        candidate_id = str(row.get("uid", "")).strip()
        if not candidate_id:
            enriched_rows.append(row)
            continue
        for detail_fields in CANDIDATE_DETAIL_FIELD_GROUPS:
            group_label = detail_fields.get("_label", "detail")
            if group_label in disabled_groups:
                continue
            request_fields = {key: value for key, value in detail_fields.items() if key != "_label"}
            try:
                response = client.get_candidate_detail(session_id, candidate_id, what=request_fields)
                detail = response.get("result") or {}
                if isinstance(detail, dict):
                    row = deep_merge_copy(row, detail)
            except Exception as exc:
                if "Abstract_field" in str(exc):
                    disabled_groups.add(group_label)
                    print(f"candidate_detail_group_disabled={group_label} error={exc}", flush=True)
                else:
                    print(f"candidate_detail_group_skipped={candidate_id} group={group_label} error={exc}", flush=True)
        enriched_rows.append(row)
        print_progress("candidate_details", total, index)
    return enriched_rows


def deep_merge_copy(base: dict, extra: dict) -> dict:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_copy(merged[key], value)
        elif value not in (None, "", {}, []):
            merged[key] = value
    return merged


def normalize_principal(row: dict) -> dict:
    return {
        "otys_id": str(row.get("uid", "")).strip(),
        "organization_type": "otys_relation",
        "name": clean_value(row.get("relation")),
        "email": clean_value(row.get("email")),
        "phone": clean_value(row.get("phoneNumberMain")),
        "website": clean_value(row.get("website") or row.get("url")),
        "city": clean_value(row.get("city")),
        "status": clean_value(row.get("status")),
        "entry_date_time": clean_value(row.get("entryDateTime")),
        "raw_data": row,
    }


def normalize_candidate(row: dict) -> dict:
    person = row.get("Person") if isinstance(row.get("Person"), dict) else {}
    address = first_collection_item(row.get("Addresses"))
    first_name = clean_value(person.get("firstName"))
    last_name = clean_value(person.get("lastName"))
    return {
        "otys_id": str(row.get("uid", "")).strip(),
        "name": " ".join(part for part in (first_name, last_name) if part).strip(),
        "first_name": first_name,
        "last_name": last_name,
        "email": clean_value(person.get("emailPrimary")),
        "phone": candidate_phone(row),
        "mobile_phone": candidate_phone(row),
        "address": clean_value(address.get("address")),
        "postal_code": clean_value(address.get("postcode")),
        "city": clean_value(address.get("city")),
        "country": clean_value(address.get("countryCode")),
        "status": clean_value(row.get("status")),
        "entry_date_time": clean_value(row.get("entryDateTime")),
        "raw_data": row,
    }


def candidate_phone(row: dict) -> str:
    direct_phone = clean_value(row.get("phoneMobile") or row.get("phoneNumber"))
    if direct_phone:
        return direct_phone

    candidates = []
    for collection_name in ("PhoneNumbers", "ExtraPhoneNumbers"):
        collection = row.get(collection_name)
        if isinstance(collection, dict):
            candidates.extend(collection.values())
        elif isinstance(collection, list):
            candidates.extend(collection)

    fallback = ""
    for item in candidates:
        if isinstance(item, dict):
            phone = clean_value(item.get("phoneNumber") or item.get("number") or item.get("value"))
            phone_type = clean_value(item.get("type")).lower()
            if phone and not fallback:
                fallback = phone
            if phone and phone_type in {"mobile", "primary", "mobiel", "privé", "prive"}:
                return phone
        else:
            phone = clean_value(item)
            if phone and not fallback:
                fallback = phone
    return fallback


def first_collection_item(collection) -> dict:
    if isinstance(collection, dict):
        for value in collection.values():
            if isinstance(value, dict):
                return value
    if isinstance(collection, list):
        for value in collection:
            if isinstance(value, dict):
                return value
    return {}


def normalize_vacancy(row: dict) -> dict:
    return {
        "otys_id": str(row.get("uid", "")).strip(),
        "title": clean_value(row.get("title")),
        "reference_number": clean_value(row.get("referenceNr")) or clean_value(row.get("uid")),
        "status": clean_value(row.get("status")) or "OTYS",
        "owner": clean_value(row.get("owner")),
        "relation_name": clean_value(row.get("relation")),
        "location": clean_value(row.get("location")),
        "publication_status": "otys",
        "applicant_count": 0,
        "entry_date_time": clean_value(row.get("entryDateTime")),
        "raw_data": row,
    }


def normalize_contact(row: dict) -> dict:
    person = row.get("Person") if isinstance(row.get("Person"), dict) else {}
    first_name = clean_value(person.get("firstName"))
    last_name = clean_value(person.get("lastName"))
    return {
        "otys_id": str(row.get("uid", "")).strip(),
        "organization_otys_id": clean_value(row.get("relationUid")),
        "relation_name": clean_value(row.get("relation")),
        "name": contact_display_name(row),
        "first_name": first_name,
        "last_name": last_name,
        "email": clean_value(person.get("emailPrimary")),
        "phone": clean_value(person.get("phoneNumberBusiness")),
        "mobile_phone": clean_value(person.get("phoneNumberMobile")),
        "status": clean_value(row.get("status")),
        "raw_data": row,
    }


def candidate_name(row: dict) -> str:
    person = row.get("Person") if isinstance(row.get("Person"), dict) else {}
    return " ".join(
        part
        for part in (
            clean_value(person.get("firstName")),
            clean_value(person.get("lastName")),
        )
        if part
    ).strip()


def contact_name(row: dict) -> str:
    person = row.get("Person") if isinstance(row.get("Person"), dict) else {}
    return " ".join(
        part
        for part in (
            clean_value(person.get("firstName")),
            clean_value(person.get("lastName")),
        )
        if part
    ).strip()


def contact_display_name(row: dict) -> str:
    person = row.get("Person") if isinstance(row.get("Person"), dict) else {}
    return (
        contact_name(row)
        or clean_value(person.get("emailPrimary"))
        or clean_value(row.get("relation"))
        or str(row.get("uid", "")).strip()
    )


def upsert_records(
    principal_rows: list[dict],
    candidate_rows: list[dict],
    contact_rows: list[dict],
    vacancy_rows: list[dict],
    replace: bool = False,
    clear_demo: bool = False,
    target: str = "all",
) -> dict:
    ensure_dashboard_tables()
    ensure_otys_tables()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            if replace:
                if target in ("all", "principals"):
                    cursor.execute("TRUNCATE TABLE otys_organizations RESTART IDENTITY;")
                    cursor.execute("DELETE FROM relations WHERE relation_type = 'principal' AND source = 'otys';")
                if target in ("all", "candidates"):
                    cursor.execute("DELETE FROM relations WHERE relation_type = 'candidate' AND source = 'otys';")
                if target in ("all", "contacts"):
                    cursor.execute("TRUNCATE TABLE otys_contacts RESTART IDENTITY;")
                if target in ("all", "vacancies"):
                    cursor.execute("DELETE FROM vacancies WHERE publication_status = 'otys';")

            if clear_demo:
                if target in ("all", "principals"):
                    cursor.execute("DELETE FROM relations WHERE relation_type = 'principal' AND source = 'demo';")
                if target in ("all", "candidates"):
                    cursor.execute("DELETE FROM relations WHERE relation_type = 'candidate' AND source = 'demo';")
                if target in ("all", "vacancies"):
                    cursor.execute(
                        """
                        DELETE FROM vacancies
                        WHERE COALESCE(raw_data->>'demo', '') = 'true'
                           OR COALESCE(publication_status, '') = 'demo';
                        """
                    )

            for index, row in enumerate(principal_rows, start=1):
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
                upsert_dashboard_principal(cursor, row)
                upsert_raw_record(cursor, "principal", row["otys_id"], row["name"], row["raw_data"])
                print_progress("principals", len(principal_rows), index)

            for index, row in enumerate(candidate_rows, start=1):
                upsert_otys_candidate(cursor, row)
                upsert_dashboard_candidate(cursor, row)
                upsert_raw_record(cursor, "candidate", row["otys_id"], row["name"], row["raw_data"])
                print_progress("candidates", len(candidate_rows), index)

            for index, row in enumerate(contact_rows, start=1):
                upsert_otys_contact(cursor, row)
                upsert_raw_record(cursor, "contact", row["otys_id"], row["name"], row["raw_data"])
                print_progress("contacts", len(contact_rows), index)

            for index, row in enumerate(vacancy_rows, start=1):
                upsert_otys_vacancy(cursor, row)
                upsert_vacancy(cursor, row)
                upsert_raw_record(cursor, "vacancy", row["otys_id"], row["title"], row["raw_data"])
                print_progress("vacancies", len(vacancy_rows), index)
        conn.commit()

    return {
        "principals_imported": len(principal_rows),
        "candidates_imported": len(candidate_rows),
        "contacts_imported": len(contact_rows),
        "vacancies_imported": len(vacancy_rows),
    }


def print_progress(label: str, total: int, index: int, every: int = 500) -> None:
    if index == 1 or index == total or index % every == 0:
        print(f"progress_write_{label}={index}/{total}", flush=True)


def upsert_dashboard_principal(cursor, row: dict) -> None:
    cursor.execute(
        """
        INSERT INTO relations (
            relation_type, external_id, name, email, phone, website, city, status,
            source, raw_data, imported_at, updated_at
        )
        VALUES ('principal', %s, %s, %s, %s, %s, %s, %s, 'otys', %s, NOW(), NOW())
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
            row["otys_id"],
            row["name"],
            row["email"],
            row["phone"],
            row["website"],
            row["city"],
            row["status"],
            Json(row["raw_data"]),
        ),
    )


def upsert_dashboard_candidate(cursor, row: dict) -> None:
    cursor.execute(
        """
        INSERT INTO relations (
            relation_type, external_id, name, first_name, last_name, email, phone,
            address, street, postal_code, city, country, status, source, raw_data, imported_at, updated_at
        )
        VALUES ('candidate', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'otys', %s, NOW(), NOW())
        ON CONFLICT (relation_type, external_id)
        WHERE external_id IS NOT NULL
        DO UPDATE SET
            name = EXCLUDED.name,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            email = EXCLUDED.email,
            phone = EXCLUDED.phone,
            address = EXCLUDED.address,
            street = EXCLUDED.street,
            postal_code = EXCLUDED.postal_code,
            city = EXCLUDED.city,
            country = EXCLUDED.country,
            status = EXCLUDED.status,
            source = EXCLUDED.source,
            raw_data = EXCLUDED.raw_data,
            imported_at = NOW(),
            updated_at = NOW();
        """,
        (
            row["otys_id"],
            row["name"],
            row["first_name"],
            row["last_name"],
            row["email"],
            row["phone"],
            row["address"],
            row["address"],
            row["postal_code"],
            row["city"],
            row["country"],
            row["status"],
            Json(row["raw_data"]),
        ),
    )


def upsert_otys_candidate(cursor, row: dict) -> None:
    cursor.execute(
        """
        INSERT INTO otys_candidates (
            otys_id,
            name,
            first_name,
            last_name,
            email,
            phone,
            mobile_phone,
            address,
            postal_code,
            city,
            country,
            status,
            entry_date_time,
            raw_data,
            synced_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (otys_id) DO UPDATE SET
            name = EXCLUDED.name,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            email = EXCLUDED.email,
            phone = EXCLUDED.phone,
            mobile_phone = EXCLUDED.mobile_phone,
            address = EXCLUDED.address,
            postal_code = EXCLUDED.postal_code,
            city = EXCLUDED.city,
            country = EXCLUDED.country,
            status = EXCLUDED.status,
            entry_date_time = EXCLUDED.entry_date_time,
            raw_data = EXCLUDED.raw_data,
            synced_at = NOW(),
            updated_at = NOW();
        """,
        (
            row["otys_id"],
            row["name"],
            row["first_name"],
            row["last_name"],
            row["email"],
            row["phone"],
            row.get("mobile_phone", ""),
            row["address"],
            row["postal_code"],
            row["city"],
            row["country"],
            row["status"],
            row["entry_date_time"],
            Json(row["raw_data"]),
        ),
    )


def upsert_otys_contact(cursor, row: dict) -> None:
    cursor.execute(
        """
        INSERT INTO otys_contacts (
            otys_id,
            organization_otys_id,
            relation_name,
            name,
            first_name,
            last_name,
            email,
            phone,
            mobile_phone,
            status,
            raw_data,
            synced_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (otys_id) DO UPDATE SET
            organization_otys_id = EXCLUDED.organization_otys_id,
            relation_name = EXCLUDED.relation_name,
            name = EXCLUDED.name,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            email = EXCLUDED.email,
            phone = EXCLUDED.phone,
            mobile_phone = EXCLUDED.mobile_phone,
            status = EXCLUDED.status,
            raw_data = EXCLUDED.raw_data,
            synced_at = NOW(),
            updated_at = NOW();
        """,
        (
            row["otys_id"],
            row["organization_otys_id"],
            row["relation_name"],
            row["name"],
            row["first_name"],
            row["last_name"],
            row["email"],
            row["phone"],
            row["mobile_phone"],
            row["status"],
            Json(row["raw_data"]),
        ),
    )


def upsert_vacancy(cursor, row: dict) -> None:
    cursor.execute(
        """
        INSERT INTO vacancies (
            external_id,
            title,
            reference_number,
            status,
            owner,
            relation_name,
            location,
            publication_status,
            applicant_count,
            raw_data,
            imported_at,
            updated_at
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
            row["otys_id"],
            row["title"],
            row["reference_number"],
            row["status"],
            row["owner"],
            row["relation_name"],
            row["location"],
            row["publication_status"],
            row["applicant_count"],
            Json(row["raw_data"]),
        ),
    )


def upsert_otys_vacancy(cursor, row: dict) -> None:
    cursor.execute(
        """
        INSERT INTO otys_vacancies (
            otys_id,
            title,
            reference_number,
            status,
            owner,
            relation_otys_id,
            relation_name,
            location,
            publication_status,
            applicant_count,
            entry_date_time,
            raw_data,
            synced_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (otys_id) DO UPDATE SET
            title = EXCLUDED.title,
            reference_number = EXCLUDED.reference_number,
            status = EXCLUDED.status,
            owner = EXCLUDED.owner,
            relation_otys_id = EXCLUDED.relation_otys_id,
            relation_name = EXCLUDED.relation_name,
            location = EXCLUDED.location,
            publication_status = EXCLUDED.publication_status,
            applicant_count = EXCLUDED.applicant_count,
            entry_date_time = EXCLUDED.entry_date_time,
            raw_data = EXCLUDED.raw_data,
            synced_at = NOW(),
            updated_at = NOW();
        """,
        (
            row["otys_id"],
            row["title"],
            row["reference_number"],
            row["status"],
            row["owner"],
            row.get("relation_otys_id", ""),
            row["relation_name"],
            row["location"],
            row["publication_status"],
            row["applicant_count"],
            row["entry_date_time"],
            Json(row["raw_data"]),
        ),
    )


def upsert_raw_record(cursor, record_type: str, otys_id: str, display_name: str, raw_data: dict) -> None:
    cursor.execute(
        """
        INSERT INTO otys_raw_records (
            record_type,
            otys_id,
            display_name,
            raw_data,
            synced_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (record_type, otys_id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            raw_data = EXCLUDED.raw_data,
            synced_at = NOW(),
            updated_at = NOW();
        """,
        (record_type, otys_id, display_name, Json(raw_data)),
    )


def extract_rows(result):
    if isinstance(result, list):
        return result
    if not isinstance(result, dict):
        return []

    for key in ("listOutput", "list", "rows", "items", "data", "output", "records", "result"):
        value = result.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = extract_rows(value)
            if nested:
                return nested

    return []


def extract_total_count(result):
    if not isinstance(result, dict):
        return None

    for key in ("totalCount", "total_count", "count"):
        if key in result:
            return result[key]

    return None


def clean_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("value", "name", "label", "status", "title", "relation"):
            if value.get(key) not in (None, ""):
                return clean_value(value.get(key))
        return ""
    if isinstance(value, list):
        return ", ".join(clean_value(item) for item in value if clean_value(item))
    return str(value).strip()


def _batch_limit(limit: int, max_rows: int, fetched: int) -> int:
    if max_rows <= 0:
        return limit
    return min(limit, max_rows - fetched)


if __name__ == "__main__":
    main()

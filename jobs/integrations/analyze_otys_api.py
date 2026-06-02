import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from jobs.integrations.otys_client import OtysClient, OtysOwsError
from jobs.integrations.sync_otys_relations import extract_rows, extract_total_count


SERVICE_FIELDS = {
    "principals": {
        "service": "RelationService",
        "fields": [
            {"uid": 1},
            {"relation": 1},
            {"status": 1},
            {"email": 1},
            {"phoneNumberMain": 1},
            {"website": 1},
            {"city": 1},
            {"address": 1},
            {"postalCode": 1},
            {"country": 1},
            {"entryDateTime": 1},
            {"updateDateTime": 1},
        ],
    },
    "candidates": {
        "service": "CandidateService",
        "fields": [
            {"uid": 1},
            {"status": 1},
            {"Person": {"firstName": 1}},
            {"Person": {"lastName": 1}},
            {"Person": {"emailPrimary": 1}},
            {"Person": {"phoneNumberMobile": 1}},
            {"Person": {"phoneNumberHome": 1}},
            {"Person": {"city": 1}},
            {"Person": {"postalCode": 1}},
            {"Person": {"street": 1}},
            {"Person": {"houseNumber": 1}},
            {"Person": {"birthDate": 1}},
            {"entryDateTime": 1},
            {"updateDateTime": 1},
        ],
    },
    "contacts": {
        "service": "RelationContactService",
        "fields": [
            {"uid": 1},
            {"relationUid": 1},
            {"relation": 1},
            {"status": 1},
            {"Person": {"firstName": 1}},
            {"Person": {"lastName": 1}},
            {"Person": {"emailPrimary": 1}},
            {"Person": {"phoneNumberMobile": 1}},
            {"Person": {"phoneNumberBusiness": 1}},
            {"Person": {"city": 1}},
        ],
    },
    "vacancies": {
        "service": "VacancyService",
        "fields": [
            {"uid": 1},
            {"title": 1},
            {"referenceNr": 1},
            {"status": 1},
            {"owner": 1},
            {"relation": 1},
            {"relationUid": 1},
            {"location": 1},
            {"entryDateTime": 1},
            {"updateDateTime": 1},
        ],
    },
}


def main():
    parser = argparse.ArgumentParser(description="Analyseer welke OTYS OWS velden veilig gelezen kunnen worden.")
    parser.add_argument("--target", choices=(*SERVICE_FIELDS.keys(), "all"), default="all")
    parser.add_argument("--sample", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    client = OtysClient()
    session_id = client.login_by_uid()
    targets = SERVICE_FIELDS.keys() if args.target == "all" else [args.target]
    report = {}

    for target in targets:
        config = SERVICE_FIELDS[target]
        service = config["service"]
        accepted = []
        rejected = []
        sample = {}
        total_count = 0

        for field in config["fields"]:
            try:
                response = client.get_list_ex(session_id, service, limit=args.sample, what=field)
                result = response.get("result", {})
                rows = extract_rows(result)
                total_count = extract_total_count(result) or total_count
                accepted.append(field)
                if rows:
                    deep_merge(sample, rows[0])
            except OtysOwsError as exc:
                rejected.append({"field": field, "error": str(exc)})

        report[target] = {
            "service": service,
            "total_count": total_count,
            "accepted": accepted,
            "rejected": rejected,
            "sample_keys": sorted(sample.keys()),
            "sample": sample,
        }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return

    for target, item in report.items():
        print(f"OTYS_ANALYSIS {target}")
        print(f"service={item['service']}")
        print(f"total_count={item['total_count']}")
        print(f"accepted={len(item['accepted'])}")
        for field in item["accepted"]:
            print(f"  + {json.dumps(field, ensure_ascii=False)}")
        print(f"rejected={len(item['rejected'])}")
        for rejected in item["rejected"]:
            print(f"  - {json.dumps(rejected['field'], ensure_ascii=False)} :: {rejected['error']}")
        print(f"sample_keys={', '.join(item['sample_keys'])}")


def deep_merge(target: dict, source: dict) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        elif key not in target or target[key] in (None, "", {}):
            target[key] = value


if __name__ == "__main__":
    main()

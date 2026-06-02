import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from jobs.integrations.otys_client import OtysClient, OtysOwsError
from jobs.integrations.sync_otys_relations import CANDIDATE_FIELDS, extract_rows


CANDIDATE_DETAIL_FIELDS = [
    {"uid": 1},
    {"status": 1},
    {"Person": {"firstName": 1}},
    {"Person": {"lastName": 1}},
    {"Person": {"emailPrimary": 1}},
    {"Person": {"phoneNumberMobile": 1}},
    {"Person": {"phoneNumberHome": 1}},
    {"Person": {"phoneNumberBusiness": 1}},
    {"Person": {"street": 1}},
    {"Person": {"houseNumber": 1}},
    {"Person": {"houseNumberAddition": 1}},
    {"Person": {"postalCode": 1}},
    {"Person": {"city": 1}},
    {"Person": {"country": 1}},
    {"Person": {"birthDate": 1}},
    {"entryDateTime": 1},
]


def main():
    parser = argparse.ArgumentParser(description="Analyseer OTYS getDetail velden.")
    parser.add_argument("--target", choices=("candidates",), default="candidates")
    parser.add_argument("--id", default="", help="OTYS uid. Leeg betekent: eerste kandidaat uit de list-call.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    client = OtysClient()
    session_id = client.login_by_uid()
    candidate_id = args.id or first_candidate_id(client, session_id)
    report = analyze_candidate(client, session_id, candidate_id)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return

    print("OTYS_DETAIL_ANALYSIS candidates")
    print(f"candidate_id={candidate_id}")
    print(f"accepted={len(report['accepted'])}")
    for field in report["accepted"]:
        print(f"  + {json.dumps(field, ensure_ascii=False)}")
    print(f"rejected={len(report['rejected'])}")
    for rejected in report["rejected"]:
        print(f"  - {json.dumps(rejected['field'], ensure_ascii=False)} :: {rejected['error']}")
    print(f"sample_keys={', '.join(report['sample_keys'])}")


def first_candidate_id(client: OtysClient, session_id: str) -> str:
    response = client.get_candidates(session_id, limit=1, what=CANDIDATE_FIELDS)
    rows = extract_rows(response.get("result", {}))
    if not rows:
        raise RuntimeError("No candidate returned by CandidateService.getListEx")
    return str(rows[0]["uid"])


def analyze_candidate(client: OtysClient, session_id: str, candidate_id: str) -> dict:
    accepted = []
    rejected = []
    sample = {}

    for field in CANDIDATE_DETAIL_FIELDS:
        try:
            response = client.get_candidate_detail(session_id, candidate_id, what=field)
            result = response.get("result") or {}
            accepted.append(field)
            if isinstance(result, dict):
                deep_merge(sample, result)
        except OtysOwsError as exc:
            rejected.append({"field": field, "error": str(exc)})

    return {
        "candidate_id": candidate_id,
        "accepted": accepted,
        "rejected": rejected,
        "sample_keys": sorted(sample.keys()),
        "sample": sample,
    }


def deep_merge(target: dict, source: dict) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        elif key not in target or target[key] in (None, "", {}):
            target[key] = value


if __name__ == "__main__":
    main()

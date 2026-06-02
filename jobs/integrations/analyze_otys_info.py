import argparse
import json
import re
import sys
from html import unescape
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.config.otys import get_otys_settings


DEFAULT_SERVICES = [
    "Otys.Services.CandidateService",
    "Otys.Services.PersonService",
    "Otys.Services.RelationContactService",
]

KEYWORDS = (
    "phone",
    "mobile",
    "tel",
    "address",
    "street",
    "postal",
    "postcode",
    "zip",
    "city",
    "plaats",
    "person",
    "email",
)


def main():
    parser = argparse.ArgumentParser(description="Zoek OTYS OWS veldnamen via de officiële info-definities.")
    parser.add_argument("--service", action="append", help="Bijv. Otys.Services.CandidateService. Mag vaker.")
    parser.add_argument("--json", action="store_true", help="Print volledige JSON als OTYS JSON teruggeeft.")
    args = parser.parse_args()

    settings = get_otys_settings()
    services = args.service or DEFAULT_SERVICES
    auth = (settings.username, settings.password) if settings.username and settings.password else None

    print("OTYS_INFO_ANALYSIS")
    print("source=https://ows.otys.nl/info/detail.php")
    print(f"services={len(services)}")
    print(f"auth={'username_password' if auth else 'none'}")

    for service in services:
        analyze_service(service, auth, args.json)


def analyze_service(service: str, auth, print_json: bool) -> None:
    response = requests.get(
        "https://ows.otys.nl/info/detail.php",
        params={"service": service},
        auth=auth,
        timeout=30,
    )
    print(f"OTYS_INFO_SERVICE {service}")
    print(f"status_code={response.status_code}")
    print(f"content_type={response.headers.get('Content-Type', '')}")

    if response.status_code >= 400:
        print(f"error={response.text[:300].strip()}")
        return

    payload = parse_json(response)
    if payload is not None:
        if print_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        matches = []
        collect_json_matches(payload, matches)
        print_matches(matches)
        return

    rows = extract_html_rows(response.text)
    matches = [row for row in rows if any(keyword in row.lower() for keyword in KEYWORDS)]
    print_matches(matches)


def parse_json(response):
    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type.lower() and not response.text.lstrip().startswith(("{", "[")):
        return None
    try:
        return response.json()
    except ValueError:
        return None


def collect_json_matches(value, matches: list[str], path: str = "") -> None:
    if isinstance(value, dict):
        joined = " ".join(str(part) for part in value.keys())
        if any(keyword in joined.lower() for keyword in KEYWORDS):
            matches.append(f"{path or 'root'} :: {json.dumps(value, ensure_ascii=False, default=str)[:500]}")
        for key, item in value.items():
            collect_json_matches(item, matches, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value[:200]):
            collect_json_matches(item, matches, f"{path}[{index}]")


def extract_html_rows(html: str) -> list[str]:
    table_rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL)
    if not table_rows:
        text = html_to_text(html)
        return [line.strip() for line in text.splitlines() if line.strip()]
    return [html_to_text(row) for row in table_rows]


def html_to_text(html: str) -> str:
    text = re.sub(r"<(br|/td|/th)[^>]*>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", " | ", text)
    return text.strip(" |")


def print_matches(matches: list[str]) -> None:
    print(f"matches={len(matches)}")
    for match in matches[:120]:
        print(f"  - {match}")
    if len(matches) > 120:
        print(f"  ... {len(matches) - 120} meer")


if __name__ == "__main__":
    main()

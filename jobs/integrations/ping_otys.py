import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from jobs.integrations.otys_client import OtysClient
from shared.config.otys import validate_otys_settings


def main():
    missing = validate_otys_settings()
    if missing:
        print("OTYS_CONFIG_MISSING")
        print("\n".join(missing))
        return

    client = OtysClient()

    try:
        session_id = client.login_by_uid()
        relations_response = client.get_relations(session_id, limit=25)
    except Exception as exc:
        print("OTYS_AUTH_ERROR")
        print(type(exc).__name__)
        print(str(exc))
        return

    print("OTYS_AUTH_RESULT")
    print("path=https://ows.otys.nl/jservice.php")
    print(f"session_id_received={bool(session_id)}")
    print("method=Otys.Services.RelationService.getListEx")

    result = relations_response.get("result")
    rows = _extract_rows(result)
    total_count = _extract_total_count(result)

    print(f"relations_received={len(rows)}")
    if total_count is not None:
        print(f"total_count={total_count}")
    if rows:
        first = rows[0]
        print(f"first_relation_uid={first.get('uid', '')}")
        print(f"first_relation_name={first.get('relation', '')}")
        print(f"first_relation_status={first.get('status', '')}")
    else:
        print(f"result_shape={_describe_result_shape(result)}")


def _extract_rows(result):
    if isinstance(result, list):
        return result
    if not isinstance(result, dict):
        return []

    for key in ("listOutput", "list", "rows", "items", "data", "output", "records", "result"):
        value = result.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_rows(value)
            if nested:
                return nested

    return []


def _extract_total_count(result):
    if not isinstance(result, dict):
        return None

    for key in ("totalCount", "total_count", "count"):
        if key in result:
            return result[key]

    return None


def _describe_result_shape(result):
    if isinstance(result, list):
        return f"list:{len(result)}"
    if not isinstance(result, dict):
        return type(result).__name__

    parts = []
    for key, value in result.items():
        if isinstance(value, list):
            parts.append(f"{key}=list:{len(value)}")
        elif isinstance(value, dict):
            nested_keys = ",".join(list(value.keys())[:8])
            parts.append(f"{key}=dict:{nested_keys}")
        else:
            parts.append(f"{key}={type(value).__name__}")

    return "; ".join(parts[:12])


if __name__ == "__main__":
    main()

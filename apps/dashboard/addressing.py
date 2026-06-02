import re


_STREET_HOUSE_NUMBER_RE = re.compile(
    r"^\s*(?P<street>.*?[^\d\s])\s+(?P<number>\d+(?:\s*[-/]\s*\d+)?)(?:\s*(?P<addition>[A-Za-z][\w-]*))?\s*$"
)


def split_street_house_number(street: str = "", house_number: str = "", addition: str = "") -> tuple[str, str, str]:
    street = str(street or "").strip()
    house_number = str(house_number or "").strip()
    addition = str(addition or "").strip()
    if house_number or not street:
        return street, house_number, addition

    match = _STREET_HOUSE_NUMBER_RE.match(street)
    if not match:
        return street, house_number, addition

    parsed_street = match.group("street").strip()
    parsed_number = re.sub(r"\s+", "", match.group("number") or "")
    parsed_addition = match.group("addition") or addition
    return parsed_street, parsed_number, parsed_addition.strip()

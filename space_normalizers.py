from datetime import datetime

from space_models import StudySpaceRecord


def _pick(item: dict, *keys: str):
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _parse_float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _format_operating_hours(item: dict) -> str | None:
    close_day = _pick(item, "closeDay", "CLOSE_DAY") or "정보 없음"

    def time_range(open_key: str, close_key: str, label: str) -> str:
        open_time = _pick(item, open_key)
        close_time = _pick(item, close_key)
        if not open_time or not close_time or (open_time == "00:00" and close_time == "00:00"):
            return f"{label} 운영안함"
        return f"{label} {open_time}~{close_time}"

    return " / ".join([
        f"휴관일: {close_day}",
        time_range("weekdayOperOpenHhmm", "weekdayOperColseHhmm", "평일"),
        time_range("satOperOperOpenHhmm", "satOperCloseHhmm", "토요일"),
        time_range("holidayOperOpenHhmm", "holidayCloseOpenHhmm", "공휴일"),
    ])


def normalize_public_library_to_study_space(item: dict) -> StudySpaceRecord | None:
    name = _pick(item, "lbrryNm", "LBRRY_NM")
    address = _pick(item, "rdnmadr", "RDNMADR")
    latitude = _parse_float(_pick(item, "latitude", "LATITUDE"))
    longitude = _parse_float(_pick(item, "longitude", "LONGITUDE"))

    if not name or not address or latitude is None or longitude is None:
        return None

    return StudySpaceRecord(
        name=name,
        type="LIBRARY",
        address=address,
        latitude=StudySpaceRecord.quantize_coordinate(latitude),
        longitude=StudySpaceRecord.quantize_coordinate(longitude),
        operating_hours=_format_operating_hours(item),
        phone=_pick(item, "phoneNumber", "PHONE_NUMBER"),
        has_wifi=False,
        has_power_outlet=False,
        is_active=True,
        last_updated_at=_parse_date(_pick(item, "referenceDate", "REFERENCE_DATE")),
    )

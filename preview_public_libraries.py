import argparse
import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from collectors.public_library import PublicLibraryCollector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path("preview_outputs/public_libraries_preview.json")


def pick(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def parse_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def format_operating_hours(item: dict[str, Any]) -> str:
    close_day = pick(item, "closeDay", "CLOSE_DAY") or "정보 없음"

    def time_range(open_key: str, close_key: str, label: str) -> str:
        open_time = pick(item, open_key)
        close_time = pick(item, close_key)
        if not open_time or not close_time or (open_time == "00:00" and close_time == "00:00"):
            return f"{label} 운영안함"
        return f"{label} {open_time}~{close_time}"

    parts = [f"휴관일: {close_day}"]
    parts.append(time_range("weekdayOperOpenHhmm", "weekdayOperColseHhmm", "평일"))
    parts.append(time_range("satOperOperOpenHhmm", "satOperCloseHhmm", "토요일"))
    parts.append(time_range("holidayOperOpenHhmm", "holidayCloseOpenHhmm", "공휴일"))
    return " / ".join(parts)


def normalize_library_item(item: dict[str, Any]) -> dict[str, Any]:
    name = pick(item, "lbrryNm", "LBRRY_NM")
    address = pick(item, "rdnmadr", "RDNMADR")
    latitude = parse_float(pick(item, "latitude", "LATITUDE"))
    longitude = parse_float(pick(item, "longitude", "LONGITUDE"))

    validation_issues = []
    if not name:
        validation_issues.append("missing_name")
    if not address:
        validation_issues.append("missing_address")
    if latitude is None:
        validation_issues.append("missing_latitude")
    if longitude is None:
        validation_issues.append("missing_longitude")

    return {
        "name": name,
        "type": "LIBRARY",
        "libraryType": pick(item, "lbrrySe", "LBRRY_SE"),
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "phone": pick(item, "phoneNumber", "PHONE_NUMBER"),
        "operatingHours": format_operating_hours(item),
        "homepageUrl": pick(item, "homepageUrl", "HOMEPAGE_URL"),
        "seatCount": parse_int(pick(item, "seatCo", "SEAT_CO")),
        "operatorInstitution": pick(item, "operInstitutionNm", "OPER_INSTITUTION_NM"),
        "province": pick(item, "ctprvnNm", "CTPRVN_NM"),
        "city": pick(item, "signguNm", "SIGNGU_NM"),
        "closeDay": pick(item, "closeDay", "CLOSE_DAY"),
        "referenceDate": pick(item, "referenceDate", "REFERENCE_DATE"),
        "sourceInstitutionCode": pick(item, "insttCode", "instt_code"),
        "sourceInstitutionName": pick(item, "insttNm", "instt_nm"),
        "isUsableForStudySpace": len(validation_issues) == 0,
        "validationIssues": validation_issues,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="전국도서관표준데이터 미리보기 수집")
    parser.add_argument("--page-start", type=int, default=1, help="시작 페이지 번호")
    parser.add_argument("--pages", type=int, default=1, help="수집할 페이지 수")
    parser.add_argument("--num-rows", type=int, default=100, help="페이지당 건수 (최대 1000)")
    parser.add_argument("--ctprvn", default="", help="시도명 필터")
    parser.add_argument("--sigungu", default="", help="시군구명 필터")
    parser.add_argument("--library-type", default="", help="도서관유형 필터")
    parser.add_argument("--library-name", default="", help="도서관명 필터")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="미리보기 JSON 저장 경로")
    return parser.parse_args()


def build_filters(args: argparse.Namespace) -> dict[str, str]:
    return {
        "CTPRVN_NM": args.ctprvn,
        "SIGNGU_NM": args.sigungu,
        "LBRRY_SE": args.library_type,
        "LBRRY_NM": args.library_name,
    }


def summarize_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_items = [normalize_library_item(item) for item in items]
    library_types = Counter(pick(item, "lbrrySe", "LBRRY_SE") or "미상" for item in items)
    provinces = Counter(pick(item, "ctprvnNm", "CTPRVN_NM") or "미상" for item in items)
    validation_issue_counts = Counter(
        issue
        for item in normalized_items
        for issue in item["validationIssues"]
    )

    return {
        "itemsFetched": len(items),
        "missingCoordinates": sum(
            1
            for item in normalized_items
            if item["latitude"] is None or item["longitude"] is None
        ),
        "missingRoadAddress": sum(1 for item in normalized_items if not item["address"]),
        "missingPhoneNumber": sum(1 for item in normalized_items if not item["phone"]),
        "missingHomepageUrl": sum(1 for item in normalized_items if not item["homepageUrl"]),
        "missingOperatingHours": sum(
            1 for item in normalized_items if "정보 없음" in item["operatingHours"]
        ),
        "usableForStudySpaces": sum(1 for item in normalized_items if item["isUsableForStudySpace"]),
        "validationIssueCounts": dict(validation_issue_counts),
        "libraryTypes": dict(library_types.most_common()),
        "provinces": dict(provinces.most_common()),
    }


def main() -> None:
    load_dotenv()
    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        raise SystemExit("DATA_GO_KR_API_KEY 환경 변수가 필요합니다.")

    args = parse_args()
    filters = build_filters(args)
    collector = PublicLibraryCollector(api_key=api_key)

    all_items: list[dict[str, Any]] = []
    total_count = 0
    pages_fetched = 0

    for offset in range(args.pages):
        page_no = args.page_start + offset
        page = collector.fetch_page(
            page_no=page_no,
            num_of_rows=args.num_rows,
            filters=filters,
            debug=(offset == 0),
        )

        pages_fetched += 1
        total_count = page["totalCount"] or total_count
        all_items.extend(page["items"])

        if not page["items"]:
            logger.info("빈 페이지를 받아 수집을 종료합니다. page=%s", page_no)
            break

        expected_count = page["pageNo"] * page["numOfRows"]
        if total_count and expected_count >= total_count:
            break

        collector.delay()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_items = [normalize_library_item(item) for item in all_items]

    payload = {
        "source": "전국도서관표준데이터",
        "fetchedAt": datetime.now(timezone.utc).astimezone().isoformat(),
        "request": {
            "pageStart": args.page_start,
            "pages": args.pages,
            "numOfRows": args.num_rows,
            "filters": {key: value for key, value in filters.items() if value},
        },
        "summary": {
            "pagesFetched": pages_fetched,
            "totalCountFromApi": total_count,
            **summarize_items(all_items),
        },
        "selectedFields": [
            "name",
            "type",
            "libraryType",
            "address",
            "latitude",
            "longitude",
            "phone",
            "operatingHours",
            "homepageUrl",
            "seatCount",
            "operatorInstitution",
            "province",
            "city",
            "closeDay",
            "referenceDate",
        ],
        "studySpaceCandidates": normalized_items,
        "items": all_items,
    }

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("미리보기 JSON 저장 완료: %s", output_path)


if __name__ == "__main__":
    main()

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
    library_types = Counter(item.get("LBRRY_SE") or "미상" for item in items)
    provinces = Counter(item.get("CTPRVN_NM") or "미상" for item in items)

    return {
        "itemsFetched": len(items),
        "missingCoordinates": sum(
            1 for item in items if not item.get("LATITUDE") or not item.get("LONGITUDE")
        ),
        "missingRoadAddress": sum(1 for item in items if not item.get("RDNMADR")),
        "missingPhoneNumber": sum(1 for item in items if not item.get("PHONE_NUMBER")),
        "missingHomepageUrl": sum(1 for item in items if not item.get("HOMEPAGE_URL")),
        "missingOperatingHours": sum(
            1
            for item in items
            if not item.get("WEEKDAY_OPER_OPEN_HHMM") or not item.get("WEEKDAY_OPER_COLSE_HHMM")
        ),
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
        "items": all_items,
    }

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("미리보기 JSON 저장 완료: %s", output_path)


if __name__ == "__main__":
    main()

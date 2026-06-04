import argparse
import logging
import os
import re
import uuid

import pymysql
from dotenv import load_dotenv

from collectors.youth_center import YouthCenterCollector
from space_geocoders import KakaoLocalGeocoder
from space_models import StudySpaceRecord
from space_normalizers import normalize_youth_center_to_study_space

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

YOUTH_CENTER_TYPE = "YOUTH_CENTER"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="청년센터 공간 정보를 study_spaces에 적재")
    parser.add_argument("--page-start", type=int, default=1, help="시작 페이지 번호")
    parser.add_argument("--pages", type=int, default=0, help="수집할 페이지 수. 0이면 전체 적재")
    parser.add_argument("--page-size", type=int, default=100, help="페이지당 건수")
    parser.add_argument("--page-type", type=int, default=None, help="화면유형")
    parser.add_argument("--ctpv-cd", default="", help="시도코드")
    parser.add_argument("--sgg-cd", default="", help="시군구코드")
    parser.add_argument("--plc-sn", default="", help="센터일련번호")
    parser.add_argument("--plc-type", default="", help="센터유형")
    parser.add_argument("--api-key", default="", help="청년센터 API 키 (없으면 env 사용)")
    parser.add_argument("--kakao-api-key", default="", help="카카오 로컬 REST API 키 (없으면 env 사용)")
    return parser.parse_args()


def resolve_api_key(args: argparse.Namespace) -> str:
    return args.api_key or os.getenv("YOUTHCENTER_API_KEY", "") or os.getenv("YOUTH_CENTER_API_KEY", "")


def build_filters(args: argparse.Namespace) -> dict[str, str]:
    return {
        "ctpvCd": args.ctpv_cd,
        "sggCd": args.sgg_cd,
        "plcSn": args.plc_sn,
        "plcType": args.plc_type,
    }


def build_center_address(item: dict) -> str:
    parts = [
        (item.get("cntrAddr") or "").strip(),
        (item.get("cntrDaddr") or "").strip(),
    ]
    return " ".join(part for part in parts if part)


def connect_mysql():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "kuriq"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def ensure_study_space_type_enum(cursor, required_type: str) -> None:
    cursor.execute("SHOW COLUMNS FROM study_spaces LIKE 'type'")
    column = cursor.fetchone()
    if not column:
        raise RuntimeError("study_spaces.type 컬럼을 찾을 수 없습니다.")

    type_definition = column["Type"]
    enum_values = re.findall(r"'([^']+)'", type_definition)
    if required_type in enum_values:
        return

    if "CAFE" in enum_values:
        cafe_index = enum_values.index("CAFE")
        enum_values.insert(cafe_index, required_type)
    else:
        enum_values.append(required_type)

    enum_sql = ", ".join(f"'{value}'" for value in enum_values)
    alter_sql = f"ALTER TABLE study_spaces MODIFY COLUMN type ENUM({enum_sql}) NOT NULL"
    logger.info("study_spaces.type enum 확장: %s 추가", required_type)
    cursor.execute(alter_sql)


def upsert_study_space(cursor, record: StudySpaceRecord) -> str:
    select_sql = """
        SELECT id
        FROM study_spaces
        WHERE name = %s AND address = %s AND type = %s
        LIMIT 1
    """
    cursor.execute(select_sql, record.unique_key())
    existing = cursor.fetchone()

    if existing:
        update_sql = """
            UPDATE study_spaces
            SET latitude = %s,
                longitude = %s,
                operating_hours = %s,
                phone = %s,
                has_wifi = %s,
                has_power_outlet = %s,
                is_active = %s,
                last_updated_at = %s
            WHERE id = %s
        """
        cursor.execute(
            update_sql,
            (
                str(record.latitude),
                str(record.longitude),
                record.operating_hours,
                record.phone,
                record.has_wifi,
                record.has_power_outlet,
                record.is_active,
                record.last_updated_at,
                existing["id"],
            ),
        )
        return "updated"

    insert_sql = """
        INSERT INTO study_spaces (
            id,
            name,
            type,
            address,
            latitude,
            longitude,
            operating_hours,
            phone,
            has_wifi,
            has_power_outlet,
            is_active,
            last_updated_at,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """
    cursor.execute(
        insert_sql,
        (
            str(uuid.uuid4()),
            record.name,
            record.type,
            record.address,
            str(record.latitude),
            str(record.longitude),
            record.operating_hours,
            record.phone,
            record.has_wifi,
            record.has_power_outlet,
            record.is_active,
            record.last_updated_at,
        ),
    )
    return "inserted"


def main() -> None:
    load_dotenv()
    args = parse_args()

    api_key = resolve_api_key(args)
    if not api_key:
        raise SystemExit("YOUTHCENTER_API_KEY 또는 YOUTH_CENTER_API_KEY 환경 변수가 필요합니다.")
    if args.page_start < 1:
        raise SystemExit("--page-start 는 1 이상이어야 합니다.")
    if args.pages < 0:
        raise SystemExit("--pages 는 0 이상이어야 합니다. 0은 전체 적재입니다.")

    filters = build_filters(args)
    collector = YouthCenterCollector(api_key=api_key)
    geocoder = KakaoLocalGeocoder(api_key=args.kakao_api_key or None)
    if not geocoder.api_key:
        raise SystemExit("KAKAO_LOCAL_REST_API_KEY 또는 --kakao-api-key 가 필요합니다.")

    inserted = 0
    updated = 0
    skipped = 0
    geocode_failed = 0
    pages_fetched = 0

    logger.info(
        "청년센터 적재 시작: page_start=%s, pages=%s, page_size=%s, filters=%s",
        args.page_start,
        "ALL" if args.pages == 0 else args.pages,
        args.page_size,
        {key: value for key, value in filters.items() if value},
    )

    connection = connect_mysql()
    try:
        with connection.cursor() as cursor:
            ensure_study_space_type_enum(cursor, YOUTH_CENTER_TYPE)

            page_num = args.page_start
            processed_center_ids: set[str] = set()
            while True:
                if args.pages > 0 and pages_fetched >= args.pages:
                    break

                page = collector.fetch_page(
                    page_num=page_num,
                    page_size=args.page_size,
                    page_type=args.page_type,
                    filters=filters,
                    debug=(pages_fetched == 0),
                )
                pages_fetched += 1

                for item in page["items"]:
                    center_id = (item.get("cntrSn") or "").strip()
                    if center_id and center_id in processed_center_ids:
                        continue

                    geocoded = geocoder.geocode(
                        build_center_address(item) or item.get("cntrAddr", ""),
                        keyword=item.get("cntrNm", ""),
                    )
                    if geocoded is None:
                        geocode_failed += 1
                        skipped += 1
                        logger.warning("[청년센터] 좌표 변환 실패로 스킵: %s", item.get("cntrNm"))
                        continue

                    lat, lng = geocoded
                    normalized = normalize_youth_center_to_study_space(item, latitude=lat, longitude=lng)
                    if normalized is None:
                        skipped += 1
                        continue

                    action = upsert_study_space(cursor, normalized)
                    if center_id:
                        processed_center_ids.add(center_id)
                    if action == "inserted":
                        inserted += 1
                    else:
                        updated += 1

                if not page["items"]:
                    break

                total_count = page["totalCount"]
                expected_count = page["pageNum"] * page["pageSize"]
                if total_count and expected_count >= total_count:
                    break

                page_num += 1
                collector.delay()

        connection.commit()
        logger.info(
            "청년센터 적재 완료: pages_fetched=%s inserted=%s updated=%s skipped=%s geocode_failed=%s",
            pages_fetched,
            inserted,
            updated,
            skipped,
            geocode_failed,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()

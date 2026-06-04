import argparse
import logging
import os
import uuid

import pymysql
from dotenv import load_dotenv

from collectors.public_library import PublicLibraryCollector
from space_models import StudySpaceRecord
from space_normalizers import normalize_public_library_to_study_space

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="전국도서관표준데이터를 study_spaces에 적재")
    parser.add_argument("--page-start", type=int, default=1)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--num-rows", type=int, default=100)
    parser.add_argument("--ctprvn", default="")
    parser.add_argument("--sigungu", default="")
    parser.add_argument("--library-type", default="")
    parser.add_argument("--library-name", default="")
    return parser.parse_args()


def build_filters(args: argparse.Namespace) -> dict[str, str]:
    return {
        "CTPRVN_NM": args.ctprvn,
        "SIGNGU_NM": args.sigungu,
        "LBRRY_SE": args.library_type,
        "LBRRY_NM": args.library_name,
    }


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
    api_key = os.getenv("DATA_GO_KR_API_KEY", "")
    if not api_key:
        raise SystemExit("DATA_GO_KR_API_KEY 환경 변수가 필요합니다.")

    args = parse_args()
    filters = build_filters(args)
    collector = PublicLibraryCollector(api_key=api_key)

    connection = connect_mysql()
    inserted = 0
    updated = 0
    skipped = 0

    try:
        with connection.cursor() as cursor:
            for offset in range(args.pages):
                page_no = args.page_start + offset
                page = collector.fetch_page(page_no=page_no, num_of_rows=args.num_rows, filters=filters, debug=(offset == 0))

                for item in page["items"]:
                    normalized = normalize_public_library_to_study_space(item)
                    if normalized is None:
                        skipped += 1
                        continue

                    action = upsert_study_space(cursor, normalized)
                    if action == "inserted":
                        inserted += 1
                    else:
                        updated += 1

                if not page["items"]:
                    break

                total_count = page["totalCount"]
                expected_count = page["pageNo"] * page["numOfRows"]
                if total_count and expected_count >= total_count:
                    break

                collector.delay()

        connection.commit()
        logger.info("study_spaces 적재 완료: inserted=%s updated=%s skipped=%s", inserted, updated, skipped)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()

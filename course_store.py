import logging
import os
import re
import uuid
from decimal import Decimal
from typing import Iterable

import pymysql

from models.course import Course

logger = logging.getLogger(__name__)


def _connect_mysql():
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


def _difficulty(course: Course) -> str:
    level = (course.level or "").strip()
    if level:
        return level

    title = course.title.lower()
    if any(token in title for token in ("심화", "고급", "advanced", "expert")):
        return "심화"
    if any(token in title for token in ("중급", "intermediate", "활용")):
        return "중급"
    return "입문"


def _duration_weeks(course: Course) -> int:
    text = course.duration or ""
    match = re.search(r"(\d+)\s*주", text)
    if match:
        return int(match.group(1))
    return 4


def _estimated_hours(course: Course) -> Decimal:
    weeks = _duration_weeks(course)
    return Decimal(str(max(weeks, 1) * 2.5)).quantize(Decimal("0.1"))


class CourseStore:
    """MySQL courses 테이블을 정본으로 유지하는 저장소."""

    def __init__(self):
        self.connection = _connect_mysql()

    def close(self) -> None:
        self.connection.close()

    def upsert_many(self, courses: list[Course]) -> list[Course]:
        if not courses:
            return []

        synced: list[Course] = []
        with self.connection.cursor() as cursor:
            for course in courses:
                course.backend_id = self._upsert_one(cursor, course)
                synced.append(course)
        self.connection.commit()
        logger.info("MySQL courses upsert — %s개 완료", len(synced))
        return synced

    def deactivate_missing(self, seen_keys: Iterable[tuple[str, str]]) -> int:
        keys = set(seen_keys)
        if not keys:
            return 0

        deactivated = 0
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT id, platform, platform_course_id FROM courses WHERE is_active = true")
            rows = cursor.fetchall()
            for row in rows:
                key = (row["platform"], row["platform_course_id"])
                if key in keys:
                    continue
                cursor.execute(
                    "UPDATE courses SET is_active = false, updated_at = NOW() WHERE id = %s",
                    (row["id"],),
                )
                deactivated += cursor.rowcount
        self.connection.commit()
        logger.info("MySQL courses 비활성화 — %s개", deactivated)
        return deactivated

    def _upsert_one(self, cursor, course: Course) -> str:
        platform = course.backend_platform()
        platform_course_id = course.id

        cursor.execute(
            """
            SELECT id
            FROM courses
            WHERE platform = %s AND platform_course_id = %s
            LIMIT 1
            """,
            (platform, platform_course_id),
        )
        existing = cursor.fetchone()
        if existing:
            course_id = existing["id"]
            cursor.execute(
                """
                UPDATE courses
                SET title = %s,
                    institution = %s,
                    category = %s,
                    difficulty = %s,
                    duration_weeks = %s,
                    estimated_hours = %s,
                    has_certificate = %s,
                    url = %s,
                    description = %s,
                    is_active = true,
                    last_crawled_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                self._course_values(course) + (course_id,),
            )
            return course_id

        course_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO courses (
                id,
                platform,
                platform_course_id,
                title,
                institution,
                category,
                difficulty,
                duration_weeks,
                estimated_hours,
                has_certificate,
                url,
                description,
                is_active,
                last_crawled_at,
                created_at,
                updated_at,
                click_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, NOW(), NOW(), NOW(), 0)
            """,
            (course_id, platform, platform_course_id) + self._course_values(course),
        )
        return course_id

    def _course_values(self, course: Course) -> tuple:
        return (
            course.title[:500],
            (course.institution or "")[:255],
            (course.std_category or "기타")[:100],
            _difficulty(course)[:10],
            _duration_weeks(course),
            _estimated_hours(course),
            bool(False),
            course.url or "#",
            course.description or None,
        )

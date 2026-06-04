import logging
import xml.etree.ElementTree as ET
from typing import Generator
import requests
from collectors.base import BaseCollector
from models.course import Course

logger = logging.getLogger(__name__)

KOCW_API_URL = "http://www.kocw.net/home/api/handler.do"

# KOCW 주제분류 코드
CATEGORY_CODES = {
    "1": "인문",
    "2": "사회",
    "3": "공학",
    "4": "자연과학",
    "5": "교육학",
    "6": "의약학",
    "7": "예술체육",
}

PAGE_SIZE = 100


class KocwCollector(BaseCollector):
    PLATFORM = "KOCW"

    def collect_all(self) -> Generator[Course, None, None]:
        """전체 카테고리 순회하며 수집"""
        for cat_id, cat_name in CATEGORY_CODES.items():
            logger.info(f"[KOCW] 카테고리 수집 시작: {cat_name} (id={cat_id})")
            yield from self._collect_category(cat_id, cat_name)

    def _collect_category(self, cat_id: str, cat_name: str) -> Generator[Course, None, None]:
        """카테고리 단위 페이지네이션 수집"""
        start = 1
        collected = 0

        while True:
            end = start + PAGE_SIZE - 1
            params = {
                "key": self.api_key,
                "verb": "list_item",
                "category_type": "t",
                "category_id": cat_id,
                "from": "20000101",
                "start_num": start,
                "end_num": end,
            }

            root = self._fetch_xml(params)
            if root is None:
                break

            # 전체 건수 파싱
            total_count_el = root.find(".//total_count")
            total_count = int(total_count_el.text) if total_count_el is not None else 0

            if total_count == 0:
                break

            items = root.findall(".//list_item")
            if not items:
                break

            for item in items:
                # 삭제된 강의 제외
                if self._text(item, "status") == "deleted":
                    continue

                course = self._parse(item, cat_name)
                if course:
                    collected += 1
                    yield course

            logger.info(f"[KOCW] {cat_name} — {collected}/{total_count}개 수집 중")

            if end >= total_count:
                break

            start = end + 1
            self.delay()

        logger.info(f"[KOCW] {cat_name} 완료 — {collected}개")

    def _fetch_xml(self, params: dict) -> ET.Element | None:
        """XML 응답 전용 요청"""
        for attempt in range(3):
            try:
                response = self.session.get(KOCW_API_URL, params=params, timeout=10)
                response.raise_for_status()
                response.encoding = "utf-8"
                return ET.fromstring(response.text)
            except ET.ParseError as e:
                logger.error(f"[KOCW] XML 파싱 오류: {e}")
                break
            except requests.RequestException as e:
                logger.warning(f"[KOCW] 요청 실패 (시도 {attempt + 1}/3): {e}")
        return None

    @staticmethod
    def _text(element: ET.Element, tag: str) -> str:
        """XML 요소에서 텍스트 안전하게 추출"""
        el = element.find(tag)
        return el.text.strip() if el is not None and el.text else ""

    def _parse(self, item: ET.Element, cat_name: str) -> Course | None:
        try:
            course_id = self._text(item, "course_id")
            title = self._text(item, "course_title")

            if not course_id or not title:
                return None

            lecture_count = self._text(item, "lecture_count")
            duration = f"{lecture_count}강" if lecture_count else ""

            return Course(
                id=course_id,
                title=title,
                institution=self._text(item, "provider"),
                platform=self.PLATFORM,
                category=self._text(item, "taxon") or cat_name,
                description=self._text(item, "course_description"),
                duration=duration,
                url=self._text(item, "course_url"),
                is_free=True,
                level="",
            )
        except Exception as e:
            logger.warning(f"[KOCW] 파싱 실패: {e}")
            return None
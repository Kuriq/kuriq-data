import logging
import xml.etree.ElementTree as ET
import requests
from typing import Generator
from collectors.base import BaseCollector
from models.course import Course

logger = logging.getLogger(__name__)

LIFELONG_API_URL = "https://apis.data.go.kr/7010000/everlearning/getLectureList"
EVERLEARNING_BASE_URL = "https://everlearning.sen.go.kr"


class LifelongCollector(BaseCollector):
    PLATFORM = "에버러닝"
    PAGE_SIZE = 100

    def collect_all(self) -> Generator[Course, None, None]:
        page = 1
        total_count = None
        collected = 0

        while True:
            logger.info(f"[에버러닝] page {page} 수집 중... (누적: {collected}개)")

            root = self._fetch_xml({
                "serviceKey": self.api_key,
                "pageNo": page,
                "numOfRows": self.PAGE_SIZE,
            }, debug=(page == 1))

            if root is None:
                break

            if total_count is None:
                el = root.find(".//totalCnt")
                total_count = int(el.text) if el is not None and el.text else 0
                logger.info(f"[에버러닝] 전체 강좌 수: {total_count}개")

            if total_count == 0:
                break

            items = root.findall(".//item")
            if not items:
                break

            for item in items:
                course = self._parse(item)
                if course:
                    collected += 1
                    yield course

            if collected >= total_count:
                break

            page += 1
            self.delay()

        logger.info(f"[에버러닝] 수집 완료 — 총 {collected}개")

    def _fetch_xml(self, params: dict, debug: bool = False) -> ET.Element | None:
        for attempt in range(3):
            try:
                response = self.session.get(LIFELONG_API_URL, params=params, timeout=10)
                response.raise_for_status()
                response.encoding = "utf-8"
                if debug:
                    logger.debug(f"[에버러닝] RAW XML:\n{response.text[:2000]}")
                return ET.fromstring(response.text)
            except ET.ParseError as e:
                logger.error(f"[에버러닝] XML 파싱 오류: {e}\n{response.text[:500]}")
                break
            except requests.RequestException as e:
                logger.warning(f"[에버러닝] 요청 실패 (시도 {attempt + 1}/3): {e}")
        return None

    @staticmethod
    def _text(element: ET.Element, tag: str) -> str:
        el = element.find(tag)
        return el.text.strip() if el is not None and el.text else ""

    def _parse(self, item: ET.Element) -> Course | None:
        try:
            end_date = self._text(item, "lectureEndYmd")
            if end_date and end_date < "20250101":
                return None

            lecture_id = self._text(item, "lectureId")
            title = self._text(item, "lectureNm")
            organ = self._text(item, "organNm")
            teacher = self._text(item, "teacherNm")
            category = self._text(item, "categoryNm") or "기타"
            region = self._text(item, "sigunguNm")
            place = self._text(item, "place")
            start_ymd = self._text(item, "lectureStartYmd")
            end_ymd = self._text(item, "lectureEndYmd")
            target = self._text(item, "targetNm")

            parts = []
            if organ:
                parts.append(f"{organ} 제공")
            if teacher:
                parts.append(f"강사: {teacher}")
            if region:
                parts.append(f"지역: {region}")
            if place:
                parts.append(f"장소: {place}")
            if target:
                parts.append(f"대상: {target}")
            if start_ymd and end_ymd:
                parts.append(f"강의기간: {start_ymd} ~ {end_ymd}")
            description = " | ".join(parts)

            day_cnt = self._text(item, "lectureDayCnt")
            duration = f"{day_cnt}일" if day_cnt else ""

            lecture_cost = self._text(item, "lectureCost") or "0"
            is_free = lecture_cost.replace(",", "").strip() in ("0", "무료", "")

            return Course(
                id=lecture_id,
                title=title,
                institution=organ,
                platform=self.PLATFORM,
                category=category,
                description=description,
                duration=duration,
                url=f"{EVERLEARNING_BASE_URL}/lecture/detail/{lecture_id}" if lecture_id else EVERLEARNING_BASE_URL,
                is_free=is_free,
            )
        except Exception as e:
            logger.warning(f"[에버러닝] 파싱 실패: {e}")
            return None
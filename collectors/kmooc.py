import logging
from typing import Generator
from collectors.base import BaseCollector
from models.course import Course

logger = logging.getLogger(__name__)

KMOOC_API_URL = "https://apis.data.go.kr/B552881/kmooc_v2_0/courseList_v2_0"


class KmoocCollector(BaseCollector):
    PLATFORM = "K-MOOC"
    PAGE_SIZE = 100

    def collect_all(self) -> Generator[Course, None, None]:
        page = 1
        total_count = None
        collected = 0

        while True:
            logger.info(f"[K-MOOC] page {page} 수집 중... (누적: {collected}개)")

            data = self.fetch(KMOOC_API_URL, params={
                "ServiceKey": self.api_key,
                "Page": page,
                "Size": self.PAGE_SIZE,
            }, debug=(page == 1))

            if not data:
                break

            if data.get("resultCode", "00") != "00":
                logger.error(f"[K-MOOC] API 오류 — {data.get('resultCode')}: {data.get('resultMsg')}")
                break

            if total_count is None:
                total_count = int(data.get("header", {}).get("totalCount", 0))
                logger.info(f"[K-MOOC] 전체 강좌 수: {total_count}개")

            items = data.get("items", [])
            if isinstance(items, dict):
                items = [items]
            if not items:
                break

            if page == 1:
                sample = items[0] if items else {}
                logger.debug(f"[K-MOOC] 첫 번째 아이템 키: {list(sample.keys())}")

            for item in items:
                course = self._parse(item)
                if course:
                    collected += 1
                    yield course

            if collected >= total_count:
                break

            page += 1
            self.delay()

        logger.info(f"[K-MOOC] 수집 완료 — 총 {collected}개")

    def _parse(self, item: dict) -> Course | None:
        try:
            org = item.get("org_name", "").strip()
            professor = item.get("professor", "").strip()
            study_start = item.get("study_start", "")
            study_end = item.get("study_end", "")
            name = item.get("name", "").strip()

            parts = []
            if org:
                parts.append(f"{org} 제공")
            if professor:
                parts.append(f"담당 교수: {professor}")
            if study_start and study_end:
                parts.append(f"학습 기간: {study_start} ~ {study_end}")
            description = " | ".join(parts)

            duration = f"{study_start} ~ {study_end}" if study_start and study_end else ""

            # K-MOOC API 는 카테고리 필드를 제공하지 않음 → 강의명으로 카테고리 추론
            # category_mapper 에서 처리하므로 빈 문자열로 설정
            return Course(
                id=item.get("id", ""),
                title=name,
                institution=org,
                platform=self.PLATFORM,
                category=name,  # 강의명을 카테고리로 설정 (전처리에서 키워드 추출용)
                description=description,
                duration=duration,
                url=item.get("url", ""),
                is_free=True,
            )
        except Exception as e:
            logger.warning(f"[K-MOOC] 파싱 실패: {e}")
            return None
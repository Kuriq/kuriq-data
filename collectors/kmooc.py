import logging
from typing import Generator
from collectors.base import BaseCollector
from models.course import Course

logger = logging.getLogger(__name__)

KMOOC_API_URL = "http://api.data.go.kr/openapi/tn_pubr_public_knline_lrn_api"


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
                "serviceKey": self.api_key,
                "pageNo": page,
                "numOfRows": self.PAGE_SIZE,
                "type": "json",
            })

            if not data:
                break

            body = data.get("response", {}).get("body", {})

            if total_count is None:
                total_count = int(body.get("totalCount", 0))
                logger.info(f"[K-MOOC] 전체 강좌 수: {total_count}개")

            items = body.get("items", {})
            if not items:
                break

            item_list = items.get("item", [])
            if isinstance(item_list, dict):
                item_list = [item_list]

            if not item_list:
                break

            for item in item_list:
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
            return Course(
                id=item.get("lctrId", ""),
                title=item.get("lctrNm", "").strip(),
                institution=item.get("orgnztNm", "").strip(),
                platform=self.PLATFORM,
                category=item.get("lctrFldNm", "기타"),
                description=item.get("lctrSumryCn", "").strip(),
                duration=item.get("lctrPd", ""),
                url=item.get("lctrUrl", ""),
                is_free=True,
            )
        except Exception as e:
            logger.warning(f"[K-MOOC] 파싱 실패: {e}")
            return None
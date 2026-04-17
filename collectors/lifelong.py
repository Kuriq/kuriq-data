import logging
from typing import Generator
from collectors.base import BaseCollector
from models.course import Course

logger = logging.getLogger(__name__)

LIFELONG_API_URL = "http://api.data.go.kr/openapi/tn_pubr_public_lftm_lrn_lctre_api"


class LifelongCollector(BaseCollector):
    PLATFORM = "온국민평생배움터"
    PAGE_SIZE = 100

    def collect_all(self) -> Generator[Course, None, None]:
        page = 1
        total_count = None
        collected = 0

        while True:
            logger.info(f"[평생학습] page {page} 수집 중... (누적: {collected}개)")

            data = self.fetch(LIFELONG_API_URL, params={
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
                logger.info(f"[평생학습] 전체 강좌 수: {total_count}개")

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

        logger.info(f"[평생학습] 수집 완료 — 총 {collected}개")

    def _parse(self, item: dict) -> Course | None:
        try:
            end_date = item.get("eduEndde", "")
            if end_date and end_date < "20250101":
                return None

            return Course(
                id=item.get("lctreSn", ""),
                title=item.get("lctreNm", "").strip(),
                institution=item.get("insttNm", "").strip(),
                platform=self.PLATFORM,
                category=item.get("lctreKindNm", "기타"),
                description=item.get("lctreIntrcn", "").strip(),
                duration=f"{item.get('eduTime', '')}시간",
                url=item.get("hmpgAddr", ""),
                is_free=item.get("prcpAmt", "0") == "0",
            )
        except Exception as e:
            logger.warning(f"[평생학습] 파싱 실패: {e}")
            return None
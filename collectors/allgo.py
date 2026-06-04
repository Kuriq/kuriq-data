import logging
from typing import Generator
from bs4 import BeautifulSoup
from collectors.base import BaseCollector
from models.course import Course

logger = logging.getLogger(__name__)

ALLGO_BASE_URL = "https://www.all.go.kr"
ALLGO_LIST_API_URL = f"{ALLGO_BASE_URL}/apol/getListSerClassMoreAjax.do"


class AllgoCollector(BaseCollector):
    PLATFORM = "온국민평생배움터"
    PAGE_SIZE = 100

    def collect_all(self) -> Generator[Course, None, None]:
        page = 1
        collected = 0
        empty_count = 0

        logger.info(f"[{self.PLATFORM}] 크롤링 시작")

        while True:
            logger.info(f"[{self.PLATFORM}] page {page} 수집 중... (누적: {collected}개)")

            html = self._fetch_list(page, debug=(page == 1))
            if not html:
                break

            cards = self._parse_cards(html)
            if not cards:
                empty_count += 1
                if empty_count >= 3:
                    logger.info(f"[{self.PLATFORM}] 빈 페이지 3회 연속 — 수집 종료")
                    break
                page += 1
                continue

            empty_count = 0
            for card in cards:
                course = self._parse(card)
                if course:
                    collected += 1
                    yield course

            page += 1
            self.delay()

        logger.info(f"[{self.PLATFORM}] 수집 완료 — 총 {collected}개")

    def _fetch_list(self, page: int, debug: bool = False) -> str:
        """온국민평생배움터 목록 API (POST)"""
        return self.fetch_post(
            ALLGO_LIST_API_URL,
            data={
                "searchClassTypeCd": "01",
                "searchKeyword": "",
                "searchCndtnYear": "",
                "searchLrngClsf": "",
                "searchLrngPrpsClsf": "",
                "searchClassSeCdArr[]": ["01", "02"],
                "searchCndtnSe": "A",
                "pageIndex": page,
                "pageUnit": self.PAGE_SIZE,
            },
            headers={"Referer": f"{ALLGO_BASE_URL}/apol/viewListSerClass.do"},
            debug=debug,
        )

    def _parse_cards(self, html: str) -> list[dict]:
        """HTML에서 강좌 카드 목록 추출"""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("li.card")
        result = []

        for card in cards:
            try:
                a_tag = card.select_one("a")
                if not a_tag:
                    continue

                href = a_tag.get("href", "")
                class_sn = href.split("classSn=")[-1] if "classSn=" in href else ""
                if not class_sn:
                    continue

                title_el = card.select_one("strong.card__title")
                title = title_el.text.strip() if title_el else ""

                category_el = card.select_one("p.card__sort__title")
                category = category_el.text.strip() if category_el else "기타"

                institution_el = card.select_one("li.card__agency")
                institution = institution_el.text.strip() if institution_el else ""

                result.append({
                    "id": class_sn,
                    "title": title,
                    "category": category,
                    "institution": institution,
                    "url": f"{ALLGO_BASE_URL}/cntnts/viewContentsDetailInfo.do?classSn={class_sn}",
                })
            except Exception as e:
                logger.warning(f"[{self.PLATFORM}] 카드 파싱 실패: {e}")

        return result

    def _parse(self, card: dict) -> Course | None:
        """카드 딕셔너리를 Course 모델로 변환"""
        try:
            return Course(
                id=card["id"],
                title=card["title"],
                institution=card["institution"],
                platform=self.PLATFORM,
                category=card["category"],
                description="",
                duration="",
                url=card["url"],
                is_free=True,
            )
        except Exception as e:
            logger.warning(f"[{self.PLATFORM}] Course 파싱 실패: {e}")
            return None

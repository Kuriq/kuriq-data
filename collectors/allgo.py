# crawl_allgokr.py
# 온국민평생배움터 강좌 크롤링 (description 없이 목록만)
# 실행: python crawl_allgokr.py

import requests
import json
import time
import logging
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] — %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.all.go.kr"
LIST_API_URL = f"{BASE_URL}/apol/getListSerClassMoreAjax.do"

PAGE_SIZE = 100
DELAY = 0.3
OUTPUT_FILE = "allgokr_courses.json"


def init_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": BASE_URL,
    })
    try:
        session.get(BASE_URL, timeout=10)
        logger.info("세션 초기화 완료")
    except Exception as e:
        logger.warning(f"세션 초기화 실패: {e}")
    return session


def fetch_list(session: requests.Session, page: int) -> str | None:
    try:
        response = session.post(
            LIST_API_URL,
            data={
                "searchClassTypeCd": "01",
                "searchKeyword": "",
                "searchCndtnYear": "",
                "searchLrngClsf": "",
                "searchLrngPrpsClsf": "",
                "searchClassSeCdArr[]": ["01", "02"],
                "searchCndtnSe": "A",
                "pageIndex": page,
                "pageUnit": PAGE_SIZE,
            },
            headers={"Referer": f"{BASE_URL}/apol/viewListSerClass.do"},
            timeout=15,
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text
    except Exception as e:
        logger.error(f"목록 요청 실패 (page {page}): {e}")
        return None


def parse_cards(html: str) -> list[dict]:
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
                "description": "",
                "url": f"{BASE_URL}/cntnts/viewContentsDetailInfo.do?classSn={class_sn}",
                "platform": "온국민평생배움터",
                "is_free": True,
            })
        except Exception as e:
            logger.warning(f"카드 파싱 실패: {e}")

    return result


def main():
    session = init_session()
    all_courses = []
    page = 1
    empty_count = 0

    logger.info("=== 온국민평생배움터 크롤링 시작 ===")

    while True:
        logger.info(f"page {page} 수집 중 (누적: {len(all_courses)}개)")

        html = fetch_list(session, page)
        if not html:
            break

        cards = parse_cards(html)

        if not cards:
            empty_count += 1
            if empty_count >= 3:
                logger.info("빈 페이지 3회 연속 — 수집 종료")
                break
            page += 1
            continue

        empty_count = 0
        all_courses.extend(cards)

        # 100개마다 중간 저장
        if len(all_courses) % 1000 == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(all_courses, f, ensure_ascii=False, indent=2)
            logger.info(f"중간 저장 완료 — {len(all_courses)}개")

        page += 1
        time.sleep(DELAY)

    # 최종 저장
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_courses, f, ensure_ascii=False, indent=2)

    logger.info(f"=== 크롤링 완료 — 총 {len(all_courses)}개 → {OUTPUT_FILE} 저장 ===")


if __name__ == "__main__":
    main()
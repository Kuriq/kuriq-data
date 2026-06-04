import logging
import os
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)


class KakaoLocalGeocoder:
    ADDRESS_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/address.json"
    KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("KAKAO_LOCAL_REST_API_KEY") or os.getenv("KAKAO_REST_API_KEY")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "KuriqDataPipeline/1.0"})
        self._cache: dict[str, tuple[float, float] | None] = {}

    def geocode(self, address: str, keyword: str | None = None) -> tuple[float, float] | None:
        normalized = (address or "").strip()
        if not normalized:
            return None

        if normalized in self._cache:
            return self._cache[normalized]

        if not self.api_key:
            raise RuntimeError("KAKAO_LOCAL_REST_API_KEY 또는 KAKAO_REST_API_KEY 환경 변수가 필요합니다.")

        candidates = self._build_address_candidates(normalized)

        for candidate in candidates:
            try:
                response = self.session.get(
                    self.ADDRESS_SEARCH_URL,
                    params={"query": candidate},
                    headers={"Authorization": f"KakaoAK {self.api_key}"},
                    timeout=(10, 30),
                )
                response.raise_for_status()
                payload = response.json()
                documents = payload.get("documents") or []
                if not documents:
                    continue

                first: dict[str, Any] = documents[0]
                lng = float(first["x"])
                lat = float(first["y"])
                self._cache[normalized] = (lat, lng)
                return lat, lng
            except Exception as e:
                logger.warning("[KakaoLocalGeocoder] 주소 변환 실패: %s (%s)", candidate, e)

        keyword_candidates = self._build_keyword_candidates(keyword, normalized)
        for candidate in keyword_candidates:
            try:
                response = self.session.get(
                    self.KEYWORD_SEARCH_URL,
                    params={"query": candidate, "size": 5},
                    headers={"Authorization": f"KakaoAK {self.api_key}"},
                    timeout=(10, 30),
                )
                response.raise_for_status()
                payload = response.json()
                documents = payload.get("documents") or []
                if not documents:
                    continue

                first: dict[str, Any] = documents[0]
                lng = float(first["x"])
                lat = float(first["y"])
                self._cache[normalized] = (lat, lng)
                return lat, lng
            except Exception as e:
                logger.warning("[KakaoLocalGeocoder] 키워드 변환 실패: %s (%s)", candidate, e)

        self._cache[normalized] = None
        return None

    @staticmethod
    def _clean_text(value: str) -> str:
        cleaned = (value or "").strip()
        cleaned = cleaned.replace("대전광약시", "대전광역시")
        cleaned = cleaned.replace("백룡료", "백룡로")
        cleaned = re.sub(r"(적금로)(\d+)", r"\1 \2", cleaned)
        cleaned = re.sub(r"\([^)]*\)", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip(" ,")

    @classmethod
    def _build_address_candidates(cls, address: str) -> list[str]:
        cleaned = cls._clean_text(address)
        variants = [cleaned]

        if " " in cleaned:
            variants.append(re.sub(r"\b\d+[~\-/]?\d*층\b", "", cleaned).strip(" ,"))
            variants.append(re.sub(r"\b[0-9]+층\b", "", cleaned).strip(" ,"))

        road_addr_match = re.search(r"^(.*?\S\s\d+(?:-\d+)?)\b", cleaned)
        if road_addr_match:
            variants.append(road_addr_match.group(1).strip(" ,"))

        if "(" in address:
            variants.append(cls._clean_text(address.split("(", 1)[0]))

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in variants:
            candidate = re.sub(r"\s+", " ", candidate).strip(" ,")
            if candidate and candidate not in seen:
                deduped.append(candidate)
                seen.add(candidate)
        return deduped

    @classmethod
    def _build_keyword_candidates(cls, keyword: str | None, address: str) -> list[str]:
        candidates = []
        if keyword:
            cleaned_keyword = cls._clean_text(keyword)
            candidates.append(cleaned_keyword)
            candidates.append(cleaned_keyword.replace("²¹", "21"))

        cleaned_address = cls._clean_text(address)
        tokens = cleaned_address.split()
        if len(tokens) >= 2 and keyword:
            candidates.append(f"{tokens[0]} {tokens[1]} {cls._clean_text(keyword)}")

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            candidate = candidate.strip()
            if candidate and candidate not in seen:
                deduped.append(candidate)
                seen.add(candidate)
        return deduped

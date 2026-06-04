import logging
from typing import Any

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

YOUTH_CENTER_API_URL = "https://www.youthcenter.go.kr/go/ythip/getSpace"


class YouthCenterCollector(BaseCollector):
    PLATFORM = "청년센터"

    def __init__(self, api_key: str = ""):
        super().__init__(api_key=api_key)
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.youthcenter.go.kr/",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def collect_all(self):
        raise NotImplementedError("검증 단계에서는 fetch_page() 기반으로만 사용합니다.")

    def build_params(
        self,
        page_num: int = 1,
        page_size: int = 100,
        page_type: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "apiKeyNm": self.api_key,
            "pageNum": max(1, page_num),
            "pageSize": max(1, page_size),
            "rtnType": "json",
        }
        if page_type is not None:
            params["pageType"] = page_type

        for key, value in (filters or {}).items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            params[key] = value

        return params

    def fetch_page(
        self,
        page_num: int = 1,
        page_size: int = 100,
        page_type: int | None = None,
        filters: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        params = self.build_params(
            page_num=page_num,
            page_size=page_size,
            page_type=page_type,
            filters=filters,
        )
        payload = self.fetch(YOUTH_CENTER_API_URL, params=params, retries=5, debug=debug)
        if not payload:
            raise RuntimeError("응답이 비어 있습니다.")

        result_code = int(payload.get("resultCode", 0) or 0)
        result_message = payload.get("resultMessage", "")
        if result_code != 200:
            raise RuntimeError(f"API 오류: {result_code} {result_message}")

        result = payload.get("result") or {}
        paging = result.get("pagging") or {}
        items = result.get("youthPolicyList") or []

        if not isinstance(items, list):
            items = []

        total_count = self._safe_int(paging.get("totCount"))
        normalized_page_num = self._safe_int(paging.get("pageNum"), page_num)
        normalized_page_size = self._safe_int(paging.get("pageSize"), page_size)

        logger.info(
            "[%s] page=%s fetched=%s total=%s code=%s",
            self.PLATFORM,
            normalized_page_num,
            len(items),
            total_count,
            result_code,
        )

        return {
            "resultCode": result_code,
            "resultMessage": result_message,
            "pageNum": normalized_page_num,
            "pageSize": normalized_page_size,
            "totalCount": total_count,
            "items": [item for item in items if isinstance(item, dict)],
        }

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

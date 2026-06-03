import logging
from typing import Any

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

PUBLIC_LIBRARY_API_URL = "https://api.data.go.kr/openapi/tn_pubr_public_lbrry_api"
MAX_NUM_OF_ROWS = 1000


class PublicLibraryCollector(BaseCollector):
    PLATFORM = "전국도서관표준데이터"

    def collect_all(self):
        raise NotImplementedError("검증 단계에서는 fetch_page() 기반으로만 사용합니다.")

    def build_params(
        self,
        page_no: int = 1,
        num_of_rows: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "serviceKey": self.api_key,
            "pageNo": page_no,
            "numOfRows": max(1, min(num_of_rows, MAX_NUM_OF_ROWS)),
            "type": "json",
        }

        for key, value in (filters or {}).items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            params[key] = value

        return params

    def fetch_page(
        self,
        page_no: int = 1,
        num_of_rows: int = 100,
        filters: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        params = self.build_params(page_no=page_no, num_of_rows=num_of_rows, filters=filters)
        payload = self.fetch(PUBLIC_LIBRARY_API_URL, params=params, debug=debug)
        if not payload:
            raise RuntimeError("응답이 비어 있습니다.")

        response = payload.get("response", {})
        header = response.get("header", {})
        body = response.get("body", {})

        result_code = str(header.get("resultCode", "")).zfill(2)
        result_msg = header.get("resultMsg", "")

        if result_code not in {"00", "03"}:
            raise RuntimeError(f"API 오류: {result_code} {result_msg}")

        items = self._extract_items(body.get("items"))
        total_count = self._safe_int(body.get("totalCount"))

        logger.info(
            "[%s] page=%s fetched=%s total=%s code=%s",
            self.PLATFORM,
            page_no,
            len(items),
            total_count,
            result_code,
        )

        return {
            "resultCode": result_code,
            "resultMsg": result_msg,
            "pageNo": self._safe_int(body.get("pageNo"), page_no),
            "numOfRows": self._safe_int(body.get("numOfRows"), num_of_rows),
            "totalCount": total_count,
            "items": items,
        }

    @staticmethod
    def _extract_items(raw_items: Any) -> list[dict[str, Any]]:
        if raw_items is None:
            return []

        if isinstance(raw_items, list):
            return [item for item in raw_items if isinstance(item, dict)]

        if isinstance(raw_items, dict):
            nested = raw_items.get("item")
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
            if isinstance(nested, dict):
                return [nested]
            return [raw_items]

        return []

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

from abc import ABC, abstractmethod
from typing import Generator
from models.course import Course
import logging
import os
import time
import requests

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """모든 수집기의 공통 추상 클래스"""

    PLATFORM: str = ""  
    REQUEST_DELAY: float = 0.3  # API 호출 간격 
    CONNECT_TIMEOUT: float = 10.0
    READ_TIMEOUT: float = 60.0

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "KuriqDataPipeline/1.0"})
        self.connect_timeout = float(os.getenv("COLLECTOR_CONNECT_TIMEOUT", self.CONNECT_TIMEOUT))
        self.read_timeout = float(os.getenv("COLLECTOR_READ_TIMEOUT", self.READ_TIMEOUT))

    @abstractmethod
    def collect_all(self) -> Generator[Course, None, None]:
        """전체 강좌 수집 — Generator로 yield"""
        pass

    def fetch(self, url: str, params: dict = None, retries: int = 3, debug: bool = False) -> dict:
        """공통 HTTP GET 요청 — 재시도 로직 포함"""
        for attempt in range(retries):
            response = None
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=(self.connect_timeout, self.read_timeout),
                )
                response.raise_for_status()

                if debug:
                    import json
                    logger.debug(f"[{self.PLATFORM}] HTTP {response.status_code} — URL: {response.url}")
                    try:
                        logger.debug(f"[{self.PLATFORM}] RAW JSON:\n{json.dumps(response.json(), ensure_ascii=False, indent=2)}")
                    except Exception:
                        logger.debug(f"[{self.PLATFORM}] RAW TEXT:\n{response.text[:2000]}")

                return response.json()
            except requests.exceptions.Timeout:
                logger.warning(
                    f"[{self.PLATFORM}] 타임아웃 (시도 {attempt + 1}/{retries}): {url} "
                    f"(connect={self.connect_timeout}s, read={self.read_timeout}s)"
                )
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                body_preview = e.response.text[:500]
                if status_code >= 500 or status_code == 429:
                    logger.warning(
                        f"[{self.PLATFORM}] 재시도 가능한 HTTP 오류 {status_code} "
                        f"(시도 {attempt + 1}/{retries}): {url}"
                    )
                    logger.warning(f"[{self.PLATFORM}] 응답 본문: {body_preview}")
                else:
                    logger.error(f"[{self.PLATFORM}] HTTP 오류 {status_code}: {url}")
                    logger.error(f"[{self.PLATFORM}] 응답 본문: {body_preview}")
                    break
            except ValueError:
                if response is not None:
                    logger.warning(
                        f"[{self.PLATFORM}] JSON 파싱 실패 (시도 {attempt + 1}/{retries}): {url}"
                    )
                    logger.warning(f"[{self.PLATFORM}] 응답 본문: {response.text[:500]}")
                else:
                    logger.warning(f"[{self.PLATFORM}] JSON 파싱 실패 (시도 {attempt + 1}/{retries}): {url}")
            except Exception as e:
                logger.error(f"[{self.PLATFORM}] 요청 실패: {e}")
                if response is not None:
                    logger.error(f"[{self.PLATFORM}] RAW TEXT:\n{response.text[:1000]}")
                break
            time.sleep(min(2 ** attempt, 5))
        return {}

    def fetch_post(self, url: str, data: dict = None, headers: dict = None, retries: int = 3, debug: bool = False) -> str:
        """공통 HTTP POST 요청 — HTML 응답 반환 (재시도 로직 포함)"""
        for attempt in range(retries):
            try:
                response = self.session.post(url, data=data, headers=headers, timeout=15)
                response.raise_for_status()
                response.encoding = "utf-8"

                if debug:
                    logger.debug(f"[{self.PLATFORM}] HTTP {response.status_code} — URL: {url}")
                    logger.debug(f"[{self.PLATFORM}] RAW HTML:\n{response.text[:2000]}")

                return response.text
            except requests.exceptions.Timeout:
                logger.warning(f"[{self.PLATFORM}] 타임아웃 (시도 {attempt + 1}/{retries}): {url}")
            except requests.exceptions.HTTPError as e:
                logger.error(f"[{self.PLATFORM}] HTTP 오류 {e.response.status_code}: {url}")
                logger.error(f"[{self.PLATFORM}] 응답 본문: {e.response.text[:500]}")
                break
            except Exception as e:
                logger.error(f"[{self.PLATFORM}] POST 요청 실패: {e}")
                break
            time.sleep(1)
        return ""

    def delay(self):
        """API 호출 간격 준수"""
        time.sleep(self.REQUEST_DELAY)

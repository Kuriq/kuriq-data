from abc import ABC, abstractmethod
from typing import Generator
from models.course import Course
import logging
import time
import requests

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """모든 수집기의 공통 추상 클래스"""

    PLATFORM: str = ""  
    REQUEST_DELAY: float = 0.3  # API 호출 간격 

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "KuriqDataPipeline/1.0"})

    @abstractmethod
    def collect_all(self) -> Generator[Course, None, None]:
        """전체 강좌 수집 — Generator로 yield"""
        pass

    def fetch(self, url: str, params: dict = None, retries: int = 3) -> dict:
        """공통 HTTP GET 요청 — 재시도 로직 포함"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                logger.warning(f"[{self.PLATFORM}] 타임아웃 (시도 {attempt + 1}/{retries}): {url}")
            except requests.exceptions.HTTPError as e:
                logger.error(f"[{self.PLATFORM}] HTTP 오류 {e.response.status_code}: {url}")
                break
            except Exception as e:
                logger.error(f"[{self.PLATFORM}] 요청 실패: {e}")
                break
            time.sleep(1)
        return {}

    def delay(self):
        """API 호출 간격 준수"""
        time.sleep(self.REQUEST_DELAY)
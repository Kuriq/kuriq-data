import os
import logging
from typing import Generator
from dotenv import load_dotenv

from models.course import Course
from collectors.kmooc import KmoocCollector
from collectors.kocw import KocwCollector
from collectors.lifelong import LifelongCollector
from preprocessors.cleaner import clean_course
from preprocessors.category_mapper import normalize_category
from preprocessors.validator import is_valid
from embedders.embedder import Embedder

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_FLUSH_SIZE = 500


def preprocess(course: Course) -> Course | None:
    """수집기 → 전처리 파이프라인"""
    course = clean_course(course)
    course.std_category = normalize_category(course.category)
    if not is_valid(course):
        return None
    return course


def run_collector(
    collector_gen: Generator[Course, None, None],
    embedder: Embedder,
    name: str,
) -> int:
    buffer = []
    total = 0

    for raw in collector_gen:
        processed = preprocess(raw)
        if processed is None:
            continue
        buffer.append(processed)

        if len(buffer) >= BATCH_FLUSH_SIZE:
            embedder.upsert(buffer)
            total += len(buffer)
            logger.info(f"[{name}] 누적 적재: {total}개")
            buffer.clear()

    if buffer:
        embedder.upsert(buffer)
        total += len(buffer)

    logger.info(f"[{name}] 완료 — 총 {total}개 적재")
    return total


def main():
    api_key = os.getenv("DATA_GO_KR_API_KEY")
    if not api_key:
        raise ValueError(".env에 DATA_GO_KR_API_KEY가 없습니다.")

    embedder = Embedder()

    logger.info("=== 큐릭 데이터 파이프라인 시작 ===")
    logger.info(f"파이프라인 시작 전 ChromaDB: {embedder.count()}개")

    collectors = [
        (KmoocCollector(api_key=api_key).collect_all(), "K-MOOC"),
        (KocwCollector(api_key=os.getenv("KOCW_API_KEY", "")).collect_all(), "KOCW"),
        (LifelongCollector(api_key=api_key).collect_all(), "전국평생학습"),
    ]

    grand_total = 0
    for gen, name in collectors:
        grand_total += run_collector(gen, embedder, name)

    logger.info(f"=== 파이프라인 완료 — 총 {grand_total}개 적재 ===")
    logger.info(f"파이프라인 완료 후 ChromaDB: {embedder.count()}개")


if __name__ == "__main__":
    main()
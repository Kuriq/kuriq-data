import argparse
import os
import logging
from typing import Callable, Generator, Literal
from dotenv import load_dotenv

from models.course import Course
from collectors.kmooc import KmoocCollector
from collectors.kocw import KocwCollector
from collectors.lifelong import LifelongCollector
from collectors.allgo import AllgoCollector
from preprocessors.cleaner import clean_course
from preprocessors.category_mapper import normalize_category
from preprocessors.validator import is_valid
from embedders.embedder import Embedder
from course_store import CourseStore

load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_FLUSH_SIZE = 500
PipelinePlatform = Literal["K-MOOC", "KOCW", "LLL_PORTAL", "SEOUL_LLL", "ALLGO", "ALL"]
ProgressCallback = Callable[[dict], None]


def preprocess(course: Course) -> Course | None:
    """수집기 -> 전처리 파이프라인"""
    course = clean_course(course)
    course.std_category = normalize_category(course.category)
    if not is_valid(course):
        return None
    return course


def run_collector(
    collector_gen: Generator[Course, None, None],
    embedder: Embedder,
    name: str,
    course_store: CourseStore | None = None,
    seen_keys: set[tuple[str, str]] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[int, dict]:
    buffer = []
    total = 0
    category_count = {}

    for raw in collector_gen:
        processed = preprocess(raw)
        if processed is None:
            continue
        buffer.append(processed)
        
        # 카테고리 카운트
        cat = processed.std_category or "기타"
        category_count[cat] = category_count.get(cat, 0) + 1

        if len(buffer) >= BATCH_FLUSH_SIZE:
            courses_to_embed = course_store.upsert_many(buffer) if course_store else buffer
            if seen_keys is not None:
                seen_keys.update((course.backend_platform(), course.id) for course in courses_to_embed)
            embedder.upsert(courses_to_embed)
            total += len(buffer)
            if progress_callback:
                progress_callback({"crawled": total, "newCourses": total})
            logger.info(f"[{name}] 누적 적재: {total}개")
            buffer.clear()

    if buffer:
        courses_to_embed = course_store.upsert_many(buffer) if course_store else buffer
        if seen_keys is not None:
            seen_keys.update((course.backend_platform(), course.id) for course in courses_to_embed)
        embedder.upsert(courses_to_embed)
        total += len(buffer)
        if progress_callback:
            progress_callback({"crawled": total, "newCourses": total})

    logger.info(f"[{name}] 완료 — 총 {total}개 적재")
    return total, category_count


def build_collectors(platform: PipelinePlatform, api_key: str):
    if platform == "K-MOOC":
        return [(KmoocCollector(api_key=api_key).collect_all(), "K-MOOC")]
    if platform == "KOCW":
        return [(KocwCollector(api_key=os.getenv("KOCW_API_KEY", "")).collect_all(), "KOCW")]
    if platform in ("LLL_PORTAL", "SEOUL_LLL"):
        return [(LifelongCollector(api_key=api_key).collect_all(), platform)]
    if platform == "ALLGO":
        return [(AllgoCollector().collect_all(), "온국민평생배움터")]
    return [
        (KmoocCollector(api_key=api_key).collect_all(), "K-MOOC"),
        (KocwCollector(api_key=os.getenv("KOCW_API_KEY", "")).collect_all(), "KOCW"),
        (LifelongCollector(api_key=api_key).collect_all(), "전국평생학습"),
        (AllgoCollector().collect_all(), "온국민평생배움터"),
    ]


def run_pipeline(
    platform: PipelinePlatform = "ALL",
    incremental: bool = True,
    progress_callback: ProgressCallback | None = None,
    reset: bool = False,
    sync_mysql: bool | None = None,
    deactivate_missing: bool = False,
) -> int:
    api_key = os.getenv("DATA_GO_KR_API_KEY")
    if not api_key:
        raise ValueError(".env 에 DATA_GO_KR_API_KEY 가 없습니다.")

    if sync_mysql is None:
        sync_mysql = os.getenv("MYSQL_SYNC_ENABLED", "false").lower() in ("1", "true", "yes", "y")

    course_store = CourseStore() if sync_mysql else None
    seen_keys: set[tuple[str, str]] | None = set() if course_store and deactivate_missing else None
    embedder = Embedder(reset=reset)

    logger.info("=== 큐릭 데이터 파이프라인 시작 ===")
    logger.info(
        "platform=%s, incremental=%s, reset=%s, sync_mysql=%s, deactivate_missing=%s",
        platform,
        incremental,
        reset,
        sync_mysql,
        deactivate_missing,
    )
    logger.info(f"파이프라인 시작 전 ChromaDB: {embedder.count()}개")

    collectors = build_collectors(platform, api_key)

    # 통계 수집
    platform_stats = {}
    total_category_count = {}
    grand_total = 0
    
    try:
        for gen, name in collectors:
            count, category_count = run_collector(
                gen,
                embedder,
                name,
                course_store=course_store,
                seen_keys=seen_keys,
                progress_callback=progress_callback,
            )
            platform_stats[name] = count
            grand_total += count
            
            # 카테고리 통합 카운트
            for cat, cnt in category_count.items():
                total_category_count[cat] = total_category_count.get(cat, 0) + cnt

        if course_store and deactivate_missing and seen_keys is not None and platform == "ALL":
            course_store.deactivate_missing(seen_keys)
        elif course_store and deactivate_missing and platform != "ALL":
            logger.warning("--deactivate-missing은 전체 수집(platform=ALL)에서만 실행됩니다. 현재 platform=%s", platform)
    finally:
        if course_store:
            course_store.close()

    # 통계 출력
    logger.info("\n" + "="*60)
    logger.info("📊 파이프라인 실행 통계")
    logger.info("="*60)
    
    logger.info("\n[플랫폼별 적재 개수]")
    for plat, cnt in sorted(platform_stats.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {plat}: {cnt:,}개")
    logger.info(f"  └ 총계: {grand_total:,}개")
    
    logger.info("\n[카테고리별 강좌 적재 개수]")
    for cat, cnt in sorted(total_category_count.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {cat}: {cnt:,}개")
    logger.info(f"  └ 총계: {sum(total_category_count.values()):,}개")
    
    logger.info("="*60)

    logger.info(f"=== 파이프라인 완료 — 총 {grand_total}개 적재 ===")
    logger.info(f"파이프라인 완료 후 ChromaDB: {embedder.count()}개")
    return grand_total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KuriQ 강좌 수집 → MySQL/Chroma 적재 파이프라인")
    parser.add_argument(
        "--platform",
        default="ALL",
        choices=["K-MOOC", "KOCW", "LLL_PORTAL", "SEOUL_LLL", "ALLGO", "ALL"],
        help="수집할 플랫폼",
    )
    parser.add_argument("--reset-chroma", action="store_true", help="ChromaDB 컬렉션 삭제 후 재생성")
    parser.add_argument("--sync-mysql", action="store_true", help="MySQL courses upsert 후 MySQL UUID로 Chroma 적재")
    parser.add_argument("--deactivate-missing", action="store_true", help="이번 수집에 없는 기존 MySQL 강좌를 비활성화")
    parser.add_argument("--full", action="store_true", help="--sync-mysql --reset-chroma --deactivate-missing 단축 옵션")
    return parser.parse_args()


def main():
    args = parse_args()
    run_pipeline(
        platform=args.platform,
        incremental=not args.full,
        reset=args.reset_chroma or args.full,
        sync_mysql=args.sync_mysql or args.full,
        deactivate_missing=args.deactivate_missing or args.full,
    )


if __name__ == "__main__":
    main()

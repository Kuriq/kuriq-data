#!/usr/bin/env python3
"""
JSON 강좌 데이터를 ChromaDB 에 저장 (임베딩 없이 메타데이터만)
"""
import json
import chromadb
from pathlib import Path

CHROMA_PATH = "/Users/shail1027/Desktop/Project/kuriq-data/chroma_db"

# 카테고리 매핑
CATEGORY_MAP = {
    "인문/교양": "인문",
    "환경/생태": "자연과학",
    "경제/경영": "사회",
    "직무역량": "교육",
    "문화/예술": "예술",
    "보건/의료": "의약학",
    "법률/행정": "사회",
    "기술/공학": "공학",
    "IT/SW": "IT/SW",
    "데이터 분석": "데이터 분석",
}

def load_courses(json_path: str) -> list[dict]:
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_metadata(course: dict, idx: int) -> dict:
    category = course.get("category", "기타")
    normalized_category = CATEGORY_MAP.get(category, category)
    
    # 더미 임베딩 (384 차원, sentence-transformers 와 호환)
    # 실제 검색에서는 keyword 기반 필터만 사용
    return {
        "courseId": course.get("id", f"course_{idx}"),
        "title": course.get("title", ""),
        "platform": course.get("platform", "UNKNOWN"),
        "institution": course.get("institution", ""),
        "category": normalized_category,
        "level": "입문",
        "url": course.get("url", ""),
        "description": course.get("description", ""),
    }

def save_to_chroma(courses: list[dict]):
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection("kuriq_courses")
    
    # 기존 데이터 삭제
    existing = collection.get(include=[])
    if existing["ids"]:
        print(f"기존 {len(existing['ids'])}개 데이터 삭제 중...")
        collection.delete(ids=existing["ids"])
    
    print(f"{len(courses)}개 강좌 저장 중...")
    
    # 배치로 저장
    BATCH_SIZE = 500
    for offset in range(0, len(courses), BATCH_SIZE):
        batch = courses[offset:offset + BATCH_SIZE]
        
        ids = [c.get("id", f"course_{i}") for i, c in enumerate(batch)]
        metadatas = [build_metadata(c, offset + i) for i, c in enumerate(batch)]
        # 더미 텍스트 (검색용)
        documents = [f"{c.get('title', '')} {c.get('description', '')} {c.get('category', '')}" for c in batch]
        # 더미 임베딩 (1536 차원 - OpenAI text-embedding-3-small 과 호환)
        embeddings = [[0.0] * 1536 for _ in batch]
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )
        
        print(f"  [{min(offset + BATCH_SIZE, len(courses))}/{len(courses)}] 배치 완료")
    
    print(f"\n완료! 총 {collection.count()}개 강좌 저장됨")

if __name__ == "__main__":
    json_path = Path(__file__).parent / "allgokr_courses.json"
    courses = load_courses(str(json_path))
    print(f"총 {len(courses)}개 강좌 로드됨")
    save_to_chroma(courses)

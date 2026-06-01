#!/usr/bin/env python3
"""
실제 강좌 데이터를 ChromaDB 에 임베딩하는 스크립트
"""
import json
import os
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI
import chromadb
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 50

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

# 난이도 매핑 (단순화)
def map_difficulty(level: str) -> str:
    if level in ["입문", "초급", "기초"]:
        return "입문"
    elif level in ["중급", "심화"]:
        return "중급"
    return "입문"

def load_courses(json_path: str) -> list[dict]:
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_text(course: dict) -> str:
    parts = [course.get("title", "")]
    if course.get("description"):
        parts.append(course["description"])
    if course.get("category"):
        parts.append(course["category"])
    return " ".join(parts)

def build_metadata(course: dict) -> dict:
    category = course.get("category", "기타")
    normalized_category = CATEGORY_MAP.get(category, category)
    
    return {
        "courseId": course.get("id", ""),
        "title": course.get("title", ""),
        "platform": course.get("platform", "UNKNOWN"),
        "institution": course.get("institution", ""),
        "category": normalized_category,
        "level": "입문",  # 기본값
        "url": course.get("url", ""),
    }

def embed_courses(courses: list[dict]):
    client = OpenAI(api_key=OPENAI_API_KEY)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection("kuriq_courses")
    
    # 기존 데이터 삭제 (중복 방지)
    existing = collection.get(include=[])
    if existing["ids"]:
        print(f"기존 {len(existing['ids'])}개 데이터 삭제 중...")
        collection.delete(ids=existing["ids"])
    
    print(f"{len(courses)}개 강좌 임베딩 시작...")
    
    for offset in range(0, len(courses), BATCH_SIZE):
        batch = courses[offset:offset + BATCH_SIZE]
        texts = [build_text(c) for c in batch]
        
        try:
            # 임베딩 생성
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
            )
            vectors = [e.embedding for e in response.data]
            
            # ChromaDB 에 저장
            collection.add(
                ids=[c.get("id", f"unknown_{i}") for i, c in enumerate(batch)],
                embeddings=vectors,
                metadatas=[build_metadata(c) for c in batch],
                documents=texts,
            )
            
            print(f"  [{offset+len(batch)}/{len(courses)}] 배치 완료")
            
        except Exception as e:
            print(f"  ERROR at offset {offset}: {e}")
            continue
    
    print(f"\n완료! 총 {collection.count()}개 강좌 저장됨")

if __name__ == "__main__":
    json_path = Path(__file__).parent / "allgokr_courses.json"
    courses = load_courses(str(json_path))
    print(f"총 {len(courses)}개 강좌 로드됨")
    embed_courses(courses)

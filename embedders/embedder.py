import os
import logging
from typing import List
import chromadb
from sentence_transformers import SentenceTransformer
from models.course import Course

logger = logging.getLogger(__name__)

COLLECTION_NAME = "kuriq_courses"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 64

def get_chroma_client():
    mode = os.getenv("CHROMA_MODE", "local")  # 기본값 로컬
    
    if mode == "server":
        return chromadb.HttpClient(
            host=os.getenv("CHROMA_HOST", "localhost"),
            port=int(os.getenv("CHROMA_PORT", "8000")),
        )
    else:
        return chromadb.PersistentClient(
            path=os.getenv("CHROMA_PATH", "./chroma_db")
        )


class Embedder:
    def __init__(self, reset: bool = False):
        logger.info(f"임베딩 모델 로딩: {EMBED_MODEL}")
        self.model = SentenceTransformer(EMBED_MODEL)
        self.client = get_chroma_client()
        
        # 기존 collection 삭제 후 재생성 (임베딩 차원 불일치 방지)
        if reset:
            try:
                self.client.delete_collection(name=COLLECTION_NAME)
                logger.info(f"기존 collection 삭제 완료 — {COLLECTION_NAME}")
            except Exception:
                pass
        
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB 연결 완료 — {COLLECTION_NAME} (현재 {self.count()}개)")

    def upsert(self, courses: List[Course]) -> None:
        """배치 단위로 임베딩 생성 후 ChromaDB upsert"""
        if not courses:
            return

        ids = [c.chroma_id() for c in courses]
        documents = [c.embed_text() for c in courses]
        metadatas = [c.to_metadata() for c in courses]

        for i in range(0, len(ids), BATCH_SIZE):
            b_ids = ids[i:i + BATCH_SIZE]
            b_docs = documents[i:i + BATCH_SIZE]
            b_meta = metadatas[i:i + BATCH_SIZE]

            embeddings = self.model.encode(b_docs, batch_size=BATCH_SIZE).tolist()

            self.collection.upsert(
                ids=b_ids,
                documents=b_docs,
                embeddings=embeddings,
                metadatas=b_meta,
            )
            logger.info(f"ChromaDB upsert — {i + len(b_ids)}개 완료")

    def count(self) -> int:
        return self.collection.count()
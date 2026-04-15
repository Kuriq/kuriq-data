from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Course:
    id: str                          # 플랫폼 내 고유 ID
    title: str                       # 강의명
    institution: str                 # 운영 기관
    platform: str                    # 플랫폼명 (K-MOOC, KOCW 등)
    category: str                    # 원본 카테고리
    std_category: str = "기타"        # 큐릭 표준 카테고리 (전처리 후 채워짐)
    description: str = ""            # 강의 소개
    duration: str = ""               # 학습 기간 / 시간
    url: str = ""                    # 수강 신청 URL
    is_free: bool = True             # 무료 여부
    level: str = ""                  # 난이도 (있는 경우)

    def embed_text(self) -> str:
        """임베딩용 텍스트 생성 — 강의명 + 표준카테고리 + 기관 + 소개 200자"""
        snippet = self.description[:200] if self.description else ""
        return f"{self.title} [{self.std_category}] {self.institution} {snippet}".strip()

    def to_metadata(self) -> dict:
        """ChromaDB metadata 딕셔너리"""
        return {
            "title": self.title,
            "institution": self.institution,
            "platform": self.platform,
            "category": self.std_category,
            "duration": self.duration,
            "url": self.url,
            "is_free": self.is_free,
            "level": self.level,
        }

    def chroma_id(self) -> str:
        """ChromaDB document ID — 플랫폼_ID"""
        return f"{self.platform}_{self.id}"
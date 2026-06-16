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
    backend_id: Optional[str] = None  # MySQL courses.id UUID

    def embed_text(self) -> str:
        """임베딩용 텍스트 생성 — 강의명 + 표준카테고리 + 기관 + 소개 200자"""
        snippet = self.description[:200] if self.description else ""
        return f"{self.title} [{self.std_category}] {self.institution} {snippet}".strip()

    def to_metadata(self) -> dict:
        """ChromaDB metadata 딕셔너리"""
        return {
            "courseId": self.backend_id or self.chroma_id(),
            "platformCourseId": self.id,
            "title": self.title,
            "institution": self.institution,
            "platform": self.backend_platform(),
            "category": self.std_category,
            "duration": self.duration,
            "difficulty": self.level or "입문",
            "durationWeeks": 4,
            "estimatedHours": 10.0,
            "hasCertificate": False,
            "isActive": True,
            "url": self.url,
            "is_free": self.is_free,
            "level": self.level,
        }

    def backend_platform(self) -> str:
        """backend Platform enum 값으로 정규화"""
        return {
            "K-MOOC": "K_MOOC",
            "K_MOOC": "K_MOOC",
            "KOCW": "KOCW",
            "온국민평생배움터": "LLL_PORTAL",
            "ALLGO": "LLL_PORTAL",
            "LLL_PORTAL": "LLL_PORTAL",
            "에버러닝": "EVERLEARNING",
            "전국평생학습": "EVERLEARNING",
            "EVERLEARNING": "EVERLEARNING",
            "서울시평생학습포털": "SEOUL_LLL",
            "서울시 평생학습포털": "SEOUL_LLL",
            "SEOUL_LLL": "SEOUL_LLL",
        }.get(self.platform, self.platform.replace("-", "_").replace(" ", "_").upper())

    def chroma_id(self) -> str:
        """ChromaDB document ID — MySQL UUID가 있으면 UUID, 없으면 플랫폼_ID"""
        if self.backend_id:
            return self.backend_id
        return f"{self.backend_platform()}_{self.id}"

# kuriq-data

국내 온라인 강의 플랫폼(K-MOOC, KOCW, 전국평생학습포털)의 강좌 데이터를 수집·전처리하여 ChromaDB에 벡터 임베딩으로 적재하는 데이터 파이프라인입니다.

## 개요

- **수집 대상**: K-MOOC, KOCW, 전국평생학습포털
- **전처리**: 텍스트 정제, 카테고리 표준화, 유효성 검증
- **임베딩**: `paraphrase-multilingual-MiniLM-L12-v2` (다국어 문장 임베딩)
- **저장소**: ChromaDB (로컬 파일 또는 원격 서버)

## 프로젝트 구조

```
kuriq-data/
├── pipeline.py          # 전체 파이프라인 실행 진입점
├── check_db.py          # ChromaDB 상태 확인 스크립트
├── ui_viewer.py         # Streamlit 기반 DB 뷰어
├── requirements.txt
│
├── collectors/          # 플랫폼별 데이터 수집기
│   ├── base.py          # 공통 BaseCollector
│   ├── kmooc.py         # K-MOOC 수집기
│   ├── kocw.py          # KOCW 수집기
│   └── lifelong.py      # 전국평생학습포털 수집기
│
├── preprocessors/       # 전처리 모듈
│   ├── cleaner.py       # 텍스트 정제
│   ├── category_mapper.py  # 카테고리 표준화
│   └── validator.py     # 유효성 검증
│
├── embedders/
│   └── embedder.py      # 임베딩 생성 및 ChromaDB upsert
│
├── models/
│   └── course.py        # Course 데이터 모델
│
└── chroma_db/           # ChromaDB 로컬 저장소 (gitignore)
```

## 설치

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성합니다.

```env
# 공공데이터포털 API 키 (K-MOOC, 전국평생학습포털 공용)
DATA_GO_KR_API_KEY=your_api_key_here

# KOCW API 키 (없으면 빈 문자열)
KOCW_API_KEY=your_kocw_api_key_here

# ChromaDB 모드: "local" (기본) 또는 "server"
CHROMA_MODE=local

# 로컬 모드 저장 경로 (기본값: ./chroma_db)
CHROMA_PATH=./chroma_db

# 서버 모드 설정 (CHROMA_MODE=server일 때)
CHROMA_HOST=localhost
CHROMA_PORT=8000
```

공공데이터포털 API 키는 [data.go.kr](https://www.data.go.kr)에서 발급받을 수 있습니다.

## 실행

### 파이프라인 실행

```bash
python pipeline.py
```

세 플랫폼의 강좌를 순서대로 수집하여 ChromaDB에 적재합니다. 500개 단위로 배치 flush됩니다.

### DB 상태 확인

```bash
python check_db.py
```

### DB 뷰어 (Streamlit)

```bash
streamlit run ui_viewer.py
```

브라우저에서 ChromaDB에 저장된 강좌 데이터를 테이블 형태로 조회할 수 있습니다.

## 데이터 모델

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | str | 플랫폼 내 고유 ID |
| `title` | str | 강의명 |
| `institution` | str | 운영 기관 |
| `platform` | str | 플랫폼명 |
| `category` | str | 원본 카테고리 |
| `std_category` | str | 큐릭 표준 카테고리 |
| `description` | str | 강의 소개 |
| `duration` | str | 학습 기간/시간 |
| `url` | str | 수강 신청 URL |
| `is_free` | bool | 무료 여부 |
| `level` | str | 난이도 |

ChromaDB에는 `{platform}_{id}` 형식의 ID로 upsert되며, 임베딩 텍스트는 `강의명 [표준카테고리] 기관 소개(200자)` 형식으로 생성됩니다.

## 의존성

| 패키지 | 용도 |
|--------|------|
| `requests` | HTTP API 호출 |
| `chromadb` | 벡터 DB |
| `sentence-transformers` | 다국어 임베딩 모델 |
| `python-dotenv` | 환경 변수 관리 |

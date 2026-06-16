# kuriq-data

## 개요

- **수집 대상**: K-MOOC, KOCW, 전국평생학습포털
- **전처리**: 텍스트 정제, 카테고리 표준화, 유효성 검증
- **임베딩**: `paraphrase-multilingual-MiniLM-L12-v2` (다국어 문장 임베딩)
- **저장소**: ChromaDB 

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

MySQL `courses`를 정본으로 삼고 ChromaDB를 재생성하려면 아래처럼 실행합니다.

```bash
python pipeline.py --full
```

`--full`은 다음 옵션을 한 번에 켭니다.

- `--sync-mysql`: `platform + platform_course_id` 기준으로 MySQL `courses`를 upsert하고 기존 UUID를 유지합니다.
- `--reset-chroma`: ChromaDB `kuriq_courses` 컬렉션을 삭제 후 재생성합니다.
- `--deactivate-missing`: 이번 수집 결과에 없는 기존 MySQL 강좌를 `is_active=false`로 비활성화합니다.

개별 옵션으로 나눠 실행할 수도 있습니다.

```bash
python pipeline.py --sync-mysql --reset-chroma
python pipeline.py --platform K-MOOC --sync-mysql
```

MySQL 적재를 사용할 때는 `.env`에 연결 정보를 추가합니다.

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=kuriq
```

### DB 상태 확인

```bash
python check_db.py
```

### 전국도서관표준데이터 미리보기 수집

```bash
python preview_public_libraries.py --pages 1 --num-rows 100
```

- 결과는 기본적으로 `preview_outputs/public_libraries_preview.json` 에 저장됩니다.
- DB/Chroma 저장 없이 원본 API 응답 기반으로 데이터 품질을 점검할 때 사용합니다.
- 예시 필터:

```bash
python preview_public_libraries.py --ctprvn 경기도 --sigungu 남양주시 --pages 1 --num-rows 50
```

### 전국도서관표준데이터를 MySQL `study_spaces`에 적재

`.env`에 MySQL 연결 정보를 추가합니다.

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=kuriq
```

실행 예시:

```bash
.venv/bin/python load_public_libraries_to_mysql.py
```

- 장소추천 MVP에 필요한 필드만 사용합니다: 이름, 타입, 주소, 좌표, 운영시간, 전화번호
- `name + address + type` 기준으로 기존 레코드가 있으면 update, 없으면 insert 합니다.
- 기본값은 `num_rows=300`, `pages=0(전체 적재)` 이므로 전국 데이터를 안정적으로 끝까지 가져옵니다.
- 공공데이터 API 응답이 느릴 수 있어 수집기 기본 read timeout도 늘려두었습니다.
- 테스트/샘플 적재가 필요하면 명시적으로 페이지 수를 제한하세요.

대량 적재를 더 빠르게 돌리고 싶으면:

```bash
COLLECTOR_READ_TIMEOUT=90 .venv/bin/python load_public_libraries_to_mysql.py --num-rows 1000
```

### 청년센터 공간 정보를 MySQL `study_spaces`에 적재

`.env`에 청년센터 API 키와 카카오 로컬 API 키를 추가합니다.

```env
YOUTHCENTER_API_KEY=your-youthcenter-api-key
KAKAO_LOCAL_REST_API_KEY=your-kakao-local-rest-api-key
```

기본 실행 예시:

```bash
.venv/bin/python load_youth_centers_to_mysql.py
```

- 청년센터 API는 좌표를 주지 않으므로 주소를 카카오 로컬 API로 좌표 변환 후 `study_spaces`에 적재합니다.
- 적재 타입은 `YOUTH_CENTER` 입니다.

서울만 적재 예시:

```bash
.venv/bin/python load_youth_centers_to_mysql.py --ctpv-cd 11
```

샘플 적재 예시:

```bash
.venv/bin/python load_public_libraries_to_mysql.py --pages 1 --num-rows 100
```

서울만 적재 예시:

```bash
.venv/bin/python load_public_libraries_to_mysql.py --ctprvn 서울특별시
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
server 모드에서는 `CHROMA_HOST`/`CHROMA_PORT`로 연결되는 공유 Chroma 컨테이너를 사용합니다.

## 의존성

| 패키지 | 용도 |
|--------|------|
| `requests` | HTTP API 호출 |
| `chromadb` | 벡터 DB |
| `sentence-transformers` | 다국어 임베딩 모델 |
| `python-dotenv` | 환경 변수 관리 |

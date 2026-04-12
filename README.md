# PatentAI — AI 기반 특허 신규성 분석 시스템

아이디어를 입력하면 AI(GPT-4o)가 KIPRIS 데이터베이스에서 유사 선행특허를 검색하고,
신규성 점수·리스크 수준·출원 전략까지 즉시 분석해 주는 B2C 특허 검색 서비스입니다.

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **Frontend** | Next.js 15 · React 19 · Tailwind CSS · Framer Motion · Recharts |
| **Backend** | FastAPI · Python 3.11 |
| **AI/임베딩** | GPT-4o · FAISS · sentence-transformers |
| **데이터** | KIPRIS 오픈 API · SQLite (캐싱) |

---

## 프로젝트 구조

```
patent-analysis/
├── frontend/              # ✅ 메인 프론트엔드 (React / Next.js)
│   ├── app/               #    Next.js App Router
│   ├── components/        #    UI 컴포넌트
│   │   ├── SearchBar.tsx         # 검색창 (히스토리 드롭다운 포함)
│   │   ├── HomeView.tsx          # 히어로 검색 화면
│   │   ├── StickyHeader.tsx      # 결과 화면 고정 헤더
│   │   ├── AISummaryWidget.tsx   # AI 분석 위젯 (점수·5관점·특허명)
│   │   ├── PriorArtComparison.tsx# 선행특허 상세 비교
│   │   ├── PatentList.tsx        # 유사 특허 아코디언 리스트
│   │   ├── TrendChart.tsx        # 연도별 출원 트렌드 차트
│   │   └── ResultView.tsx        # 결과 전체 레이아웃
│   └── lib/
│       ├── types.ts              # 백엔드 API 타입 정의
│       ├── mockData.ts           # 목 데이터 (백엔드 없이 확인용)
│       └── useSearchHistory.ts   # 검색 히스토리 훅 (localStorage)
│
├── backend/               # FastAPI 백엔드
│   ├── main.py            #   API 엔드포인트
│   ├── kipris.py          #   KIPRIS 검색 연동
│   ├── embedding.py       #   FAISS 유사도 검색
│   └── llm.py             #   GPT-4o 신규성 분석
│
├── frontend-streamlit/    # 🗄️ 레거시 (Streamlit) — 내부 디버깅·참고용
│   └── app.py             #   Streamlit UI (백엔드 개발 시 빠른 확인용)
│
├── requirements.txt       # Python 의존성
└── README.md
```

---

## Getting Started

### 1. 백엔드 실행

```bash
# Python 가상환경 생성 (최초 1회)
python -m venv venv
source venv/bin/activate        # macOS/Linux
# 또는
.\venv\Scripts\activate         # Windows

# 의존성 설치
pip install -r requirements.txt

# 백엔드 서버 실행 (포트 8000)
uvicorn backend.main:app --reload
```

### 2. React 프론트엔드 실행 (메인)

```bash
cd frontend

# 의존성 설치 (최초 1회 또는 packages 변경 시)
npm install

# 개발 서버 실행 (포트 3000)
npm run dev
```

브라우저에서 http://localhost:3000 접속

#### 환경 변수 설정 (선택)

```bash
# frontend/.env.local 파일 생성
# 비워두면 목 데이터로 동작, 입력하면 실제 백엔드 호출
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
```

### 3. (선택) Streamlit 레거시 프론트엔드

내부 개발·디버깅 또는 Streamlit 코드 참고 시에만 사용합니다.

```bash
cd frontend-streamlit
streamlit run app.py
# → http://localhost:8501
```

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **히어로 검색 UX** | Google/Perplexity 스타일의 중앙 집중형 검색 화면 |
| **최근 검색 히스토리** | 검색창 포커스 시 드롭다운, localStorage 저장 |
| **AI 신규성 분석** | 신규성 점수(0~100) · 리스크 배지 · 제안 특허명 |
| **5가지 관점 분석** | Pill 탭으로 혁신/구현/시장성/회피/등록 가능성 확인 |
| **선행특허 상세 비교** | 겹치는 부분 vs 차별점 카드 레이아웃 |
| **유사 특허 아코디언** | 유사도 순위 · 아코디언 확장 · KIPRIS 원문 링크 |
| **트렌드 차트** | Recharts 막대 그래프로 연도별 출원 동향 시각화 |
| **분석 결과 다운로드** | 마크다운(.md) 리포트 다운로드 |

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/search` | 아이디어 텍스트로 유사 특허 검색 |
| `GET`  | `/trend`  | 키워드 연도별 출원 트렌드 조회 |

---

## 팀 구성

| 담당 | 역할 |
|------|------|
| 팀원 1 | 백엔드 (FastAPI · KIPRIS API · DB) |
| 팀원 2 | AI/임베딩 (FAISS · GPT-4o) |
| 팀원 3 | 프론트엔드 (React · UI/UX · LLM 연동) |

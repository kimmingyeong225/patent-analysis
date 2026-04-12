import streamlit as st
import requests
import os
import plotly.express as px
from dotenv import load_dotenv
from llm import analyze_novelty

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
load_dotenv()

st.set_page_config(
    page_title="PatentAI | 특허 신규성 분석기",
    layout="wide",
    page_icon="🔬",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* ── 전체 ── */
.stApp {
    background: #f0f2f6;
    font-family: 'IBM Plex Sans KR', sans-serif;
}

/* ── 사이드바 ── */
[data-testid="stSidebar"] {
    background: #1c2b4a !important;
    border-right: none;
}
[data-testid="stSidebar"] * {
    color: #a8b8d0 !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
}
[data-testid="stSidebar"] strong { color: #ffffff !important; }
[data-testid="stSidebar"] h3    { color: #ffffff !important; font-size: 1.05rem !important; }

/* ── 히어로 래퍼 ── */
.hero-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 5rem 1rem 2rem;
    text-align: center;
}
.hero-logo  { font-size: 3.2rem; margin-bottom: 0.4rem; }
.hero-title {
    font-size: 2.4rem;
    font-weight: 700;
    color: #1a2742;
    margin: 0 0 0.5rem;
    letter-spacing: -0.5px;
    font-family: 'IBM Plex Sans KR', sans-serif;
}
.hero-sub {
    font-size: 1rem;
    color: #5a6a8a;
    margin-bottom: 2.2rem;
    font-family: 'IBM Plex Sans KR', sans-serif;
}

/* ── 콤팩트 헤더 ── */
.compact-logo {
    font-size: 1.5rem;
    font-weight: 700;
    color: #1a2742;
    font-family: 'IBM Plex Sans KR', sans-serif;
    line-height: 2.6rem;
}

/* ── 입력 공통 ── */
[data-testid="stTextInput"] input {
    background: #ffffff !important;
    border: 1.5px solid #dde2ea !important;
    border-radius: 10px !important;
    color: #1a2742 !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-size: 0.97rem !important;
    padding: 0.75rem 1.1rem !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.07) !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
}
[data-testid="stTextInput"] input::placeholder { color: #9ba8bb !important; }

/* ── 결과 화면 검색바 — 크고 강조 ── */
.results-search [data-testid="stTextInput"] input {
    font-size: 1.12rem !important;
    padding: 1rem 1.5rem !important;
    border-radius: 30px !important;
    border: 2px solid #dde2ea !important;
    box-shadow: 0 2px 18px rgba(0,0,0,0.09) !important;
    height: 3.2rem !important;
}
.results-search [data-testid="stTextInput"] input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 4px 24px rgba(37,99,235,0.16) !important;
}

/* ── 검색결과 카드 ── */
.sr-card {
    background: #ffffff;
    border: 1px solid #e8edf5;
    border-radius: 14px;
    padding: 1.3rem 1.6rem;
    margin-bottom: 0.9rem;
    transition: box-shadow 0.2s, border-color 0.2s;
    cursor: default;
}
.sr-card:hover {
    box-shadow: 0 6px 24px rgba(0,0,0,0.08);
    border-color: #c7d2e8;
}
.sr-top {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 0.55rem;
}
.sr-rank {
    font-size: 0.72rem;
    font-weight: 700;
    color: #ffffff;
    background: #94a3b8;
    border-radius: 6px;
    padding: 0.2rem 0.5rem;
    flex-shrink: 0;
    margin-top: 0.25rem;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.3px;
}
.sr-title {
    font-size: 1.08rem;
    font-weight: 600;
    color: #1a56db;
    font-family: 'IBM Plex Sans KR', sans-serif;
    line-height: 1.4;
    flex: 1;
}
.sr-score-badge {
    font-size: 0.82rem;
    font-weight: 700;
    padding: 0.22rem 0.75rem;
    border-radius: 20px;
    flex-shrink: 0;
    font-family: 'IBM Plex Mono', monospace;
}
.sr-meta {
    font-size: 0.8rem;
    color: #7a8ba8;
    font-family: 'IBM Plex Sans KR', sans-serif;
    margin-bottom: 0.55rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
}
.sr-meta-dot { color: #c7d2e4; font-size: 0.7rem; }
.sr-abstract {
    font-size: 0.89rem;
    color: #3d4f6e;
    font-family: 'IBM Plex Sans KR', sans-serif;
    line-height: 1.65;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.sr-footer {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-top: 0.8rem;
}

/* ── 버튼 ── */
.stButton > button {
    background: #2563eb !important;
    color: #ffffff !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.92rem !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.55rem 1.6rem !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important;
    transition: background 0.2s, transform 0.1s !important;
    white-space: nowrap;
}
.stButton > button:hover {
    background: #1d4ed8 !important;
    transform: translateY(-1px) !important;
}
.stButton > button p { color: #ffffff !important; }

/* 로고 버튼 — 텍스트처럼 보이도록 */
.logo-btn > div > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0.3rem 0 !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    color: #1a2742 !important;
    letter-spacing: -0.3px !important;
    cursor: pointer !important;
}
.logo-btn > div > button:hover {
    background: transparent !important;
    color: #2563eb !important;
    transform: none !important;
    box-shadow: none !important;
}
.logo-btn > div > button p {
    color: inherit !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
}

/* ── 탭 ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 2px solid #e4e9f0;
    gap: 0.5rem;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.95rem !important;
    color: #5a6a8a !important;
    padding: 0.6rem 1.2rem !important;
    border-radius: 6px 6px 0 0 !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #2563eb !important;
    border-bottom: 2px solid #2563eb !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1.5px solid #e4e9f0 !important;
    border-radius: 10px !important;
    margin-bottom: 0.5rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
[data-testid="stExpander"]:hover {
    border-color: rgba(37,99,235,0.35) !important;
    box-shadow: 0 3px 12px rgba(37,99,235,0.08) !important;
}
[data-testid="stExpander"] summary {
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 500 !important;
    color: #1a2742 !important;
    font-size: 0.96rem !important;
    padding: 0.75rem 1rem !important;
}

/* ── 메트릭 ── */
[data-testid="stMetric"] {
    background: #ffffff !important;
    border: 1.5px solid #e4e9f0 !important;
    border-radius: 12px !important;
    padding: 1.3rem 1.5rem !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
}
[data-testid="stMetricLabel"] {
    color: #5a6a8a !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    font-family: 'IBM Plex Mono', monospace !important;
}
[data-testid="stMetricValue"] {
    color: #1a2742 !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 600 !important;
    font-size: 1.55rem !important;
}

/* ── 본문 텍스트 ── */
p, li {
    color: #2c3a57 !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    line-height: 1.8 !important;
    font-size: 0.95rem !important;
}
strong { color: #1a2742 !important; font-weight: 600 !important; }
hr     { border-color: #dde4ee !important; margin: 1.6rem 0 !important; }
h1, h2, h3 {
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 600 !important;
    color: #1a2742 !important;
}

/* ── 인라인 코드 ── */
code {
    background: #eef2ff !important;
    color: #2563eb !important;
    font-family: 'IBM Plex Mono', monospace !important;
    border-radius: 4px !important;
    padding: 0.15rem 0.5rem !important;
    font-size: 0.83rem !important;
    font-weight: 500 !important;
}

/* ── 섹션 레이블 ── */
.section-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #2563eb;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    font-family: 'IBM Plex Mono', monospace;
    margin-bottom: 0.2rem;
}

/* ── 뱃지 ── */
.badge {
    display: inline-block;
    padding: 0.18rem 0.6rem;
    border-radius: 20px;
    font-size: 0.77rem;
    font-weight: 600;
    letter-spacing: 0.2px;
    font-family: 'IBM Plex Sans KR', sans-serif;
}
.badge-green  { background: #dcfce7; color: #166534; }
.badge-red    { background: #fee2e2; color: #991b1b; }
.badge-yellow { background: #fef9c3; color: #854d0e; }
.badge-blue   { background: #dbeafe; color: #1e40af; }

/* ── 메타 키-값 ── */
.meta-key {
    font-size: 0.71rem;
    font-weight: 600;
    color: #5a6a8a;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-family: 'IBM Plex Mono', monospace;
    margin-bottom: 0.15rem;
}
.meta-val {
    font-size: 0.9rem;
    font-weight: 500;
    color: #1a2742;
    font-family: 'IBM Plex Sans KR', sans-serif;
}

/* ── 스크롤바 ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #f0f2f6; }
::-webkit-scrollbar-thumb { background: #d1d9e6; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #a8b4cc; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  Session State 초기화
# ══════════════════════════════════════════════════════════════
_defaults = {
    "search_done":   False,
    "results_data":  None,
    "analysis_data": None,
    "current_query": "",
    "history":       [],   # [{"query": str, "score": int, "risk": str}]
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════
#  헬퍼 함수
# ══════════════════════════════════════════════════════════════
def kipris_url(application_number: str) -> str:
    """출원번호로 KIPRIS 검색 URL 생성 — 백엔드 변경 없이 프론트에서만 처리"""
    return f"https://www.kipris.or.kr/khome/searchResult.do?query={application_number}"


def format_aspect(text: str) -> str:
    if not text or text == "분석 데이터 없음":
        return "_분석 데이터 없음_"
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) <= 1:
        lines = [l.strip() for l in text.split(". ") if l.strip()]
        lines = [l if l.endswith(".") else l + "." for l in lines]
    return "\n\n".join(f"- {l}" for l in lines)


def build_report(query: str, data: dict, analysis: dict) -> str:
    """분석 결과를 마크다운 리포트로 변환 (다운로드용)"""
    lines = [
        "# PatentAI 신규성 분석 리포트",
        f"",
        f"**분석 아이디어:** {query}",
        f"",
        f"---",
        f"",
        f"## 신규성 점수: {analysis.get('novelty_score', 'N/A')} / 100",
        f"**리스크 수준:** {analysis.get('risk_level', 'N/A')}",
        f"**제안 특허명:** {analysis.get('patent_title', 'N/A')}",
        f"",
        f"## 아이디어 요약",
        analysis.get("summary", ""),
        f"",
        f"## 리스크 근거",
        analysis.get("risk_reason", ""),
        f"",
        f"## 출원 전략 조언",
        analysis.get("recommendation", ""),
        f"",
        f"---",
        f"",
        f"## 유사 특허 목록",
    ]
    for p in data.get("results", []):
        pub = p["공개등록공보"]
        score_pct = int(float(p["similarity_score"]) * 100)
        lines.append(
            f"- **{p['rank']}위** | {pub['title']} | "
            f"유사도 {score_pct}% | {pub['application_number']}"
        )
    return "\n".join(lines)


def add_to_history(query: str, analysis: dict):
    history = [h for h in st.session_state.history if h["query"] != query]
    history.insert(0, {
        "query": query,
        "score": analysis.get("novelty_score", "?"),
        "risk":  analysis.get("risk_level", "?"),
    })
    st.session_state.history = history[:5]


# ══════════════════════════════════════════════════════════════
#  검색+분석 실행 (Feature ④ 단계별 진행 표시)
# ══════════════════════════════════════════════════════════════
def run_search(query: str):
    """백엔드 /search → LLM 분석 → session_state 저장"""
    # st.status로 단계별 진행 표시
    with st.status("분석 진행 중...", expanded=True) as status:
        st.write("🔍 유사 특허 데이터베이스 검색 중...")
        try:
            res = requests.post(
                f"{BACKEND_URL}/search",
                json={"query": query},
                timeout=60,
            )
            res.raise_for_status()
            data = res.json()
        except requests.exceptions.ConnectionError:
            status.update(label="연결 실패", state="error")
            st.error("🔌 백엔드 서버에 연결할 수 없습니다. 백엔드를 먼저 실행해주세요.")
            return
        except Exception as e:
            status.update(label="검색 실패", state="error")
            st.error(f"오류: {e}")
            return

        st.write(f"✅ 유사 특허 {len(data['results'])}건 발견")
        st.write("🤖 GPT-4o 신규성 분석 중...")

        analysis = analyze_novelty(query, data["results"])

        if "error" in analysis:
            status.update(label="AI 분석 실패", state="error")
            st.error(f"AI 분석 실패: {analysis['error']}")
            if analysis.get("raw"):
                st.code(analysis["raw"])
            return

        st.write("📊 결과 정리 완료")
        status.update(label="분석 완료!", state="complete", expanded=False)

    st.session_state.results_data  = data
    st.session_state.analysis_data = analysis
    st.session_state.current_query = query
    st.session_state.search_done   = True
    add_to_history(query, analysis)


# ══════════════════════════════════════════════════════════════
#  사이드바 — Feature ② 최근 검색 히스토리
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🔬 PatentAI")
    st.markdown("---")

    if st.session_state.history:
        st.markdown("**최근 검색**")
        for i, item in enumerate(st.session_state.history):
            risk_icon = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}.get(item["risk"], "⚪")
            label = item["query"]
            short = label if len(label) <= 18 else label[:17] + "…"
            if st.button(f"{risk_icon} {short}", key=f"hist_{i}", use_container_width=True):
                st.session_state.pending_query = label
                st.rerun()
        st.markdown("---")

    st.markdown("**사용 기술**")
    st.markdown("- GPT-4o 신규성 분석")
    st.markdown("- KIPRIS 오픈 API")
    st.markdown("- FAISS 유사도 검색")
    st.markdown("- SQLite 캐싱")
    st.markdown("---")
    st.markdown("**담당** : 팀원 3 · UI/LLM")
    st.markdown("**버전** : Phase 3")

# 히스토리 버튼 클릭 처리
if "pending_query" in st.session_state:
    _pq = st.session_state.pop("pending_query")
    run_search(_pq)
    st.rerun()


# ══════════════════════════════════════════════════════════════
#  HERO 화면 (검색 전)
# ══════════════════════════════════════════════════════════════
if not st.session_state.search_done:

    st.markdown("<br><br>", unsafe_allow_html=True)
    _, center, _ = st.columns([1, 2.2, 1])
    with center:
        st.markdown(
            "<div class='hero-wrap'>"
            "<div class='hero-logo'>🔬</div>"
            "<div class='hero-title'>PatentAI</div>"
            "<div class='hero-sub'>아이디어를 입력하면 선행특허 분석을 즉시 시작합니다</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        hero_query = st.text_input(
            "검색",
            placeholder="분석할 아이디어를 입력하세요  —  예: 자가 충전형 스마트 워치 스트랩",
            label_visibility="collapsed",
            key="hero_input",
        )

        _, btn_col, _ = st.columns([1, 2, 1])
        with btn_col:
            hero_btn = st.button("특허 분석 시작 →", use_container_width=True)

        if hero_btn:
            if hero_query:
                run_search(hero_query)
                st.rerun()
            else:
                st.warning("아이디어를 입력해주세요.")


# ══════════════════════════════════════════════════════════════
#  RESULTS 화면 (검색 후)
# ══════════════════════════════════════════════════════════════
else:
    data     = st.session_state.results_data
    analysis = st.session_state.analysis_data
    query    = st.session_state.current_query

    # ── 결과 헤더: 로고(홈) + 강조된 검색바
    h_logo, h_search, h_pad = st.columns([1.4, 7, 1])
    with h_logo:
        st.markdown("<div class='logo-btn'>", unsafe_allow_html=True)
        if st.button("🔬 PatentAI"):
            st.session_state.search_done = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with h_search:
        st.markdown("<div class='results-search'>", unsafe_allow_html=True)
        new_query = st.text_input(
            "검색",
            value=query,
            placeholder="새로운 아이디어를 입력하고 Enter",
            label_visibility="collapsed",
            key="result_input",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Enter 감지 → 재검색
    if new_query and new_query != query:
        run_search(new_query)
        st.rerun()

    st.divider()

    # ── 결과 탭 3개
    tab_patents, tab_analysis, tab_trend = st.tabs([
        f"📄 유사 특허  ({len(data['results'])}건)",
        "🤖 AI 신규성 분석",
        "📈 트렌드 분석",
    ])

    # ────────────────────────────────────────────────
    #  TAB 1 : 유사 특허 — Google 스타일 카드
    # ────────────────────────────────────────────────
    with tab_patents:
        if data.get("cached"):
            st.info("⚡ 캐시된 결과입니다.")

        def _score_style(pct: int) -> tuple[str, str]:
            """유사도 퍼센트 → (배경색, 글자색)"""
            if pct >= 80: return "#fee2e2", "#dc2626"
            if pct >= 60: return "#fef9c3", "#d97706"
            return "#dbeafe", "#2563eb"

        for patent in data["results"]:
            pub       = patent["공개등록공보"]
            status    = patent["법적상태"]
            score_pct = int(float(patent["similarity_score"]) * 100)
            bg, fg    = _score_style(score_pct)

            alive_label = "등록 유지" if status["is_alive"] else "소멸"
            alive_color = "#166534" if status["is_alive"] else "#991b1b"
            alive_bg    = "#dcfce7"  if status["is_alive"] else "#fee2e2"

            abstract_snippet = pub["abstract"][:120] + "…" if len(pub["abstract"]) > 120 else pub["abstract"]

            # ── 카드 HTML (제목·메타·초록 미리보기)
            card_html = f"""
            <div class="sr-card">
              <div class="sr-top">
                <span class="sr-rank">{patent['rank']}위</span>
                <div class="sr-title">{pub['title']}</div>
                <span class="sr-score-badge" style="background:{bg}; color:{fg};">{score_pct}%</span>
              </div>
              <div class="sr-meta">
                <span>{pub['applicant']}</span>
                <span class="sr-meta-dot">●</span>
                <span>{pub['application_date']}</span>
                <span class="sr-meta-dot">●</span>
                <span>{pub['application_number']}</span>
                <span class="sr-meta-dot">●</span>
                <span style="background:{alive_bg}; color:{alive_color};
                             padding:0.1rem 0.5rem; border-radius:10px;
                             font-size:0.76rem; font-weight:600;">{alive_label}</span>
              </div>
              <div class="sr-abstract">{abstract_snippet}</div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

            # ── 상세 보기 (expander는 추가 정보에만 사용)
            with st.expander("상세 정보 · 청구항 · KIPRIS"):
                st.link_button("KIPRIS에서 전문 보기 →", kipris_url(pub["application_number"]))

                st.markdown("**전체 초록**")
                st.markdown(pub["abstract"])

                if pub.get("claims"):
                    st.markdown("**청구항**")
                    for claim in pub["claims"]:
                        st.markdown(f"- {claim}")

                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown(
                        f"<div class='meta-key'>공개일</div>"
                        f"<div class='meta-val'>{pub['publication_date']}</div>",
                        unsafe_allow_html=True,
                    )
                with col_r:
                    st.markdown(
                        f"<div class='meta-key'>문서유형</div>"
                        f"<div class='meta-val'>{pub['doc_type']}</div>",
                        unsafe_allow_html=True,
                    )

    # ────────────────────────────────────────────────
    #  TAB 2 : AI 신규성 분석
    # ────────────────────────────────────────────────
    with tab_analysis:
        novelty    = analysis["novelty_score"]
        risk       = analysis["risk_level"]
        title_full = analysis.get("patent_title", "N/A")

        # ── 메트릭 3개
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("신규성 점수", f"{novelty} / 100")
            st.caption("100점에 가까울수록 선행특허와 차별됨")
        with m2:
            st.metric("리스크 수준", risk)
            st.caption("선행특허와의 충돌 가능성")
        with m3:
            display_title = title_full if len(title_full) <= 18 else title_full[:17] + "…"
            st.metric("제안 특허명", display_title)
            if len(title_full) > 18:
                st.caption(title_full)

        # 신규성 점수 프로그레스 바
        st.markdown(
            f"<div style='margin:1rem 0 0.2rem; font-size:0.8rem; color:#5a6a8a;"
            f" font-family:IBM Plex Mono,monospace;'>신규성 점수 {novelty}/100</div>",
            unsafe_allow_html=True,
        )
        st.progress(int(novelty) / 100)

        # Feature ⑤ 분석 결과 다운로드
        report_md = build_report(query, data, analysis)
        safe_name = query[:20].replace(" ", "_").replace("/", "-")
        st.download_button(
            label="📥 분석 결과 다운로드 (.md)",
            data=report_md,
            file_name=f"patent_analysis_{safe_name}.md",
            mime="text/markdown",
        )

        st.divider()

        # ── 요약 + 리스크 근거
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**📋 아이디어 요약**")
            st.markdown(analysis["summary"])
        with col_b:
            st.markdown("**⚠️ 리스크 근거**")
            st.markdown(analysis["risk_reason"])

        # ── 선행특허별 비교
        st.divider()
        st.markdown("<div class='section-label'>선행특허 비교</div>", unsafe_allow_html=True)
        st.markdown("### 🔍 선행특허별 상세 비교")

        threat_map = {
            "높음": ("🔴", "badge-red"),
            "중간": ("🟡", "badge-yellow"),
            "낮음": ("🟢", "badge-blue"),
        }
        for comp in analysis.get("prior_art_comparison", []):
            threat = comp.get("threat_level", "")
            icon, badge_cls = threat_map.get(threat, ("⚪", "badge-blue"))
            patent_id = comp.get("patent_id", "N/A")

            with st.expander(f"{icon}  {comp.get('title', '')}"):
                st.markdown(
                    f"<span class='badge {badge_cls}'>위협도: {threat}</span>"
                    f"&nbsp; <code>{patent_id}</code>",
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)
                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown("**겹치는 부분**")
                    st.markdown(comp.get("overlap", "—"))
                with col_r:
                    st.markdown("**차별점**")
                    st.markdown(comp.get("difference", "—"))

        # ── 5가지 관점 분석
        st.divider()
        st.markdown("<div class='section-label'>5가지 관점 분석</div>", unsafe_allow_html=True)
        st.markdown("### 💡 5가지 관점 분석")

        five = analysis.get("five_aspects", {})
        t1, t2, t3, t4, t5 = st.tabs([
            "🚀 혁신 포인트",
            "🔧 구현 방법",
            "📈 시장성",
            "🛡️ 회피 설계",
            "✅ 등록 가능성",
        ])
        with t1: st.markdown(format_aspect(five.get("innovation_point", "분석 데이터 없음")))
        with t2: st.markdown(format_aspect(five.get("implementation",   "분석 데이터 없음")))
        with t3: st.markdown(format_aspect(five.get("marketability",    "분석 데이터 없음")))
        with t4: st.markdown(format_aspect(five.get("design_around",    "분석 데이터 없음")))
        with t5: st.markdown(format_aspect(five.get("registrability",   "분석 데이터 없음")))

        # ── 출원 전략 조언
        st.divider()
        st.markdown("### 📌 출원 전략 조언")
        st.info(analysis.get("recommendation", "조언 데이터 없음"))

    # ────────────────────────────────────────────────
    #  TAB 3 : 트렌드 분석
    # ────────────────────────────────────────────────
    with tab_trend:
        st.markdown(
            "<p style='color:#5a6a8a; font-size:0.92rem; margin-bottom:1rem;'>"
            "키워드를 입력하면 연도별 특허 출원 동향을 확인할 수 있습니다.</p>",
            unsafe_allow_html=True,
        )
        trend_input = st.text_input(
            "트렌드 키워드",
            placeholder="트렌드를 분석할 키워드  —  예: 태양광 충전",
            label_visibility="collapsed",
            key="trend_input",
        )
        col_t, _ = st.columns([1, 6])
        with col_t:
            trend_run = st.button("트렌드 조회 →", key="trend_btn")

        if trend_run:
            if not trend_input:
                st.warning("키워드를 입력해주세요.")
            else:
                with st.spinner("트렌드 데이터 조회 중..."):
                    try:
                        res = requests.get(
                            f"{BACKEND_URL}/trend",
                            params={"query": trend_input},
                            timeout=10,
                        )
                        res.raise_for_status()
                        trend_data = res.json()

                        years  = [d["year"]  for d in trend_data["trend_data"]]
                        counts = [d["count"] for d in trend_data["trend_data"]]

                        fig = px.bar(
                            x=years,
                            y=counts,
                            labels={"x": "연도", "y": "출원 건수"},
                            title=f"'{trend_data['query']}' 키워드 연도별 출원 트렌드",
                            color=counts,
                            color_continuous_scale="Blues",
                        )
                        fig.update_layout(
                            plot_bgcolor="white",
                            paper_bgcolor="white",
                            font_family="IBM Plex Sans KR",
                            title_font_size=15,
                            title_font_color="#1c2b4a",
                            coloraxis_showscale=False,
                            xaxis=dict(tickmode="linear", dtick=1, gridcolor="#f0f0f0"),
                            yaxis=dict(gridcolor="#f0f0f0"),
                            hoverlabel=dict(bgcolor="white", font_size=13),
                            margin=dict(t=50, b=40, l=40, r=20),
                        )
                        fig.update_traces(
                            hovertemplate="<b>%{x}년</b><br>출원 건수: %{y}건<extra></extra>"
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    except requests.exceptions.ConnectionError:
                        st.error("🔌 백엔드 서버에 연결할 수 없습니다.")
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

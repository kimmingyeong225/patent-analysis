import streamlit as st
import requests
import os
from dotenv import load_dotenv
from llm import analyze_novelty

BACKEND_URL = "http://127.0.0.1:8000"
load_dotenv()

st.set_page_config(page_title="PatentAI | 특허 신규성 분석기", layout="wide", page_icon="🔬")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

.stApp {
    background: #f5f6f8;
    font-family: 'IBM Plex Sans KR', sans-serif;
}

[data-testid="stSidebar"] {
    background: #1c2b4a !important;
    border-right: none;
}
[data-testid="stSidebar"] * {
    color: #a8b8d0 !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
}
[data-testid="stSidebar"] strong { color: #ffffff !important; }
[data-testid="stSidebar"] h3 { color: #ffffff !important; font-size: 1.1rem !important; }

h1 {
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 600 !important;
    font-size: 2rem !important;
    color: #1c2b4a !important;
    letter-spacing: -0.5px !important;
}
h2, h3 {
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 600 !important;
    color: #1c2b4a !important;
}

[data-testid="stTextInput"] input {
    background: #ffffff !important;
    border: 1.5px solid #dde2ea !important;
    border-radius: 8px !important;
    color: #1c2b4a !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-size: 0.97rem !important;
    padding: 0.75rem 1rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
}
[data-testid="stTextInput"] input::placeholder { color: #9ba8bb !important; }

.stButton > button {
    background: #2563eb !important;
    color: #ffffff !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.92rem !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.55rem 1.8rem !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important;
    transition: background 0.2s, transform 0.1s, box-shadow 0.2s !important;
}
.stButton > button:hover {
    background: #1d4ed8 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.3) !important;
}
.stButton > button p { color: #ffffff !important; }

[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1.5px solid #e4e9f0 !important;
    border-radius: 10px !important;
    margin-bottom: 0.6rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
[data-testid="stExpander"]:hover {
    border-color: #2563eb55 !important;
    box-shadow: 0 3px 12px rgba(37,99,235,0.08) !important;
}
[data-testid="stExpander"] summary {
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 500 !important;
    color: #1c2b4a !important;
    font-size: 0.95rem !important;
}

[data-testid="stMetric"] {
    background: #ffffff !important;
    border: 1.5px solid #e4e9f0 !important;
    border-radius: 10px !important;
    padding: 1.2rem 1.5rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}
[data-testid="stMetricLabel"] {
    color: #6b7a99 !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-family: 'IBM Plex Mono', monospace !important;
}
[data-testid="stMetricValue"] {
    color: #1c2b4a !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    font-weight: 600 !important;
    font-size: 1.8rem !important;
}

p, li {
    color: #3d4f6e !important;
    font-family: 'IBM Plex Sans KR', sans-serif !important;
    line-height: 1.75 !important;
    font-size: 0.94rem !important;
}
strong { color: #1c2b4a !important; font-weight: 600 !important; }
hr { border-color: #e4e9f0 !important; margin: 1.5rem 0 !important; }

code {
    background: #eef2ff !important;
    color: #2563eb !important;
    font-family: 'IBM Plex Mono', monospace !important;
    border-radius: 4px !important;
    padding: 0.15rem 0.5rem !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
}

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #f5f6f8; }
::-webkit-scrollbar-thumb { background: #dde2ea; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #b0bdd0; }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔬 PatentAI")
    st.markdown("---")
    st.markdown("**담당** : 팀원 3 · UI/LLM")
    st.markdown("**버전** : Phase 3 완료")
    st.markdown("---")
    st.markdown("**사용 기술**")
    st.markdown("- GPT-4o 신규성 분석")
    st.markdown("- KIPRIS 오픈 API")
    st.markdown("- FAISS 유사도 검색")
    st.markdown("- SQLite 캐싱")

# ── 헤더 ─────────────────────────────────────────────────────
st.markdown("# 🔬 PatentAI")
st.markdown("<p style='color:#6b7a99; margin-top:-0.6rem; font-size:0.97rem;'>AI 기반 특허 신규성 분석 시스템</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ── 입력 ─────────────────────────────────────────────────────
user_input = st.text_input(
    "",
    placeholder="분석할 아이디어를 입력하세요  —  예: 자가 충전형 스마트 워치 스트랩",
    label_visibility="collapsed"
)

col_btn, _ = st.columns([1, 6])
with col_btn:
    run = st.button("분석 시작 →")

# ── 분석 실행 ────────────────────────────────────────────────
if run:
    if user_input:
        # ── 1단계: 특허 검색 ──
        with st.spinner("특허 데이터베이스 검색 중..."):
            try:
                res = requests.post(
                    f"{BACKEND_URL}/search",
                    json={"query": user_input},
                    timeout=10
                )
                res.raise_for_status()
                data = res.json()

                st.success(f"유사 특허 {len(data['results'])}건 검색 완료")
                if data.get("cached"):
                    st.info("⚡ 캐시된 결과입니다.")

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("### 📄 유사 특허 검색 결과")

                for patent in data["results"]:
                    pub = patent["공개등록공보"]
                    score = patent["similarity_score"]
                    status = patent["법적상태"]
                    status_icon = "🟢" if status["is_alive"] else "🔴"
                    score_pct = int(float(score) * 100)

                    with st.expander(f"{status_icon}  {patent['rank']}위 · {pub['title']}  —  유사도 {score_pct}%"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"**출원인**  \n{pub['applicant']}")
                            st.markdown(f"**출원번호**  \n{pub['application_number']}")
                        with col2:
                            st.markdown(f"**출원일**  \n{pub['application_date']}")
                            st.markdown(f"**공개일**  \n{pub['publication_date']}")
                        with col3:
                            st.markdown(f"**법적상태**  \n{status['status']}")
                            st.markdown(f"**문서유형**  \n{pub['doc_type']}")

                        st.markdown("---")
                        st.markdown(f"**초록**  \n{pub['abstract']}")

                        if pub.get("claims"):
                            st.markdown("**청구항**")
                            for claim in pub["claims"]:
                                st.markdown(f"- {claim}")

                # ── 2단계: AI 신규성 분석 ──
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("### 🤖 AI 신규성 분석")

                with st.spinner("GPT-4o 분석 중..."):
                    analysis = analyze_novelty(user_input, data["results"])

                    if "error" in analysis:
                        st.error(f"AI 분석 실패: {analysis['error']}")
                        if analysis.get("raw"):
                            st.code(analysis["raw"])
                    else:
                        # ── 상단 메트릭 ──
                        m1, m2, m3 = st.columns(3)
                        with m1:
                            st.metric("신규성 점수", f"{analysis['novelty_score']} / 100")
                        with m2:
                            st.metric("리스크 수준", analysis["risk_level"])
                        with m3:
                            st.metric("제안 특허명", str(analysis['patent_title'])[:14] + "...")

                        st.markdown("---")

                        # ── 요약 + 리스크 ──
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown("**📋 아이디어 요약**")
                            st.markdown(analysis["summary"])
                        with col_b:
                            st.markdown("**⚠️ 리스크 근거**")
                            st.markdown(analysis["risk_reason"])

                        # ── 선행특허별 비교 ──
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown("### 🔍 선행특허별 상세 비교")

                        for comp in analysis.get("prior_art_comparison", []):
                            threat = comp.get("threat_level", "")
                            threat_icon = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}.get(threat, "⚪")

                            with st.expander(f"{threat_icon} {comp.get('title', '')}  —  위협도: {threat}"):
                                st.markdown(f"**출원번호:** {comp.get('patent_id', 'N/A')}")
                                st.markdown(f"**겹치는 부분:** {comp.get('overlap', '')}")
                                st.markdown(f"**차별점:** {comp.get('difference', '')}")

                        # ── 5가지 관점 분석 (탭) ──
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown("### 💡 5가지 관점 분석")

                        def format_aspect(text: str) -> str:
                            """GPT 응답을 가독성 좋은 bullet 리스트로 변환"""
                            if not text or text == "분석 데이터 없음":
                                return "분석 데이터 없음"
                            lines = [l.strip() for l in text.split("\n") if l.strip()]
                            if len(lines) <= 1:
                                # 줄바꿈 없이 온 경우 → 마침표 기준 분리
                                lines = [l.strip() for l in text.split(". ") if l.strip()]
                                lines = [l if l.endswith(".") else l + "." for l in lines]
                            return "\n".join([f"- {l}" for l in lines])

                        five = analysis.get("five_aspects", {})
                        tab1, tab2, tab3, tab4, tab5 = st.tabs([
                            "🚀 혁신 포인트",
                            "🔧 구현 방법",
                            "📈 시장성",
                            "🛡️ 회피 설계",
                            "✅ 등록 가능성"
                        ])

                        with tab1:
                            st.markdown(format_aspect(five.get("innovation_point", "분석 데이터 없음")))
                        with tab2:
                            st.markdown(format_aspect(five.get("implementation", "분석 데이터 없음")))
                        with tab3:
                            st.markdown(format_aspect(five.get("marketability", "분석 데이터 없음")))
                        with tab4:
                            st.markdown(format_aspect(five.get("design_around", "분석 데이터 없음")))
                        with tab5:
                            st.markdown(format_aspect(five.get("registrability", "분석 데이터 없음")))

                        # ── 최종 조언 ──
                        st.markdown("---")
                        st.markdown("### 📌 출원 전략 조언")
                        st.info(analysis.get("recommendation", "조언 데이터 없음"))

            except requests.exceptions.ConnectionError:
                st.error("🔌 백엔드 서버에 연결할 수 없습니다. 백엔드를 먼저 실행해주세요.")
            except Exception as e:
                st.error(f"오류 발생: {e}")
    else:
        st.warning("아이디어를 입력해주세요.")
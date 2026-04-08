# 📌 프론트엔드 메인 파일
# 역할: Streamlit 기반 UI
# 담당: 팀원 3
# - 아이디어 입력창
# - 유사 특허 결과 카드 표시
# - Plotly 트렌드 그래프 시각화

import streamlit as st
import requests
import os
from openai import OpenAI
from dotenv import load_dotenv


BACKEND_URL = "http://127.0.0.1:8000"
# .env 파일 로드 (나중에 여기에 API 키를 넣을 거예요)
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="특허 분석 서비스", layout="wide")

# 사이드바 구성
with st.sidebar:
    st.title("📂 프로젝트 설정")
    st.write("3번 담당자: UI/LLM 분석")

# 메인 화면
st.title("🔎 AI 기반 특허 신규성 분석기")
user_input = st.text_input("분석할 아이디어를 입력하세요", placeholder="예: 자가 충전형 스마트 워치 스트랩")

if st.button("분석 시작"):
    if user_input:
        st.info(f"'{user_input}' 아이디어를 분석 중입니다...")
        
        try:
            # 1. 진짜 OpenAI API 호출
            response = client.chat.completions.create(
                model="gpt-4o",  # 또는 본인이 쓸 모델명
                messages=[
                    {"role": "system", "content": "당신은 특허 분석 전문가입니다."},
                    {"role": "user", "content": f"다음 아이디어를 전문적인 특허 명칭으로 바꾸고 3줄 요약해줘: {user_input}"}
                ]
            )
            
            # 2. AI 답변 출력
            st.success("AI 분석 완료!")
            st.write(response.choices[0].message.content)
            
            # 3. (기존) Mock-up 데이터도 아래에 같이 보여주기
            st.divider()
            st.subheader("📌 참고: 유사 특허 검색 결과 (테스트용)")
            mock_results = [
                {"title": "태양광 충전 스트랩", "score": "0.89", "desc": "태양광 패널을 스트랩에 내장하는 기술"},
                {"title": "운동 에너지 발전 시계줄", "score": "0.75", "desc": "움직임을 전기로 변환하는 메커니즘"}
            ]
            for res in mock_results:
                with st.expander(f"{res['title']} (유사도: {res['score']})"):
                    st.write(res['desc'])
                    
        except Exception as e:
            st.error(f"AI 호출 중 에러가 발생했습니다: {e}")
    else:
        st.warning("아이디어를 입력해주세요!")
# 📌 FastAPI 서버의 메인 파일
# 역할: 프론트엔드와 백엔드를 연결하는 중심 서버
# 담당: 팀원 공통
# - API 엔드포인트 정의
# - 각 기능 모듈 연결

from fastapi import FastAPI
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

@app.get("/")
def root():
    return {"message": "특허 분석 서버 작동 중!"}
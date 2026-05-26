import os
import logging
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 1. 로깅 및 FastAPI 초기화
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gemini Slack Bot & Labor API Debugger")

# CORS 전면 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

# ========================================================
# [디버깅 미들웨어] 모든 요청 주소를 실시간으로 추적합니다.
# ========================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # 웹사이트가 서버의 어떤 주소(Path)와 방식(Method)으로 요청했는지 로그에 기록합니다.
    logger.info(f"📡 [실시간 유입 감지] Method: {request.method} | Path: {request.url.path}")
    response = await call_next(request)
    return response

# ========================================================
# [바이블 API] GET과 POST, 슬래시 유무를 모두 처리하는 만능 엔드포인트
# ========================================================
SAMPLE_BIBLE_DATA = [
    {
        "id": 1,
        "category": "근로시간",
        "title": "연장근로 한도 위반 여부 산정 기준 (최신 판례)",
        "content": "대법원 판례에 따르면, 일주일간 총 근로시간이 52시간을 초과했는지를 기준으로 형사처벌 여부를 판단해야 하며, 하루 8시간 초과분을 각각 더하는 방식이 아닙니다."
    },
    {
        "id": 2,
        "category": "임금",
        "title": "평균임금과 통상임금의 정의 및 구분",
        "content": "통상임금은 연장·야간·휴일근로 수당의 계산 근거가 되는 사전에 정해진 고정급이며, 평균임금은 퇴직금 산정의 기준이 되는 3개월간의 실제 수령액 평균입니다."
    },
    {
        "id": 3,
        "category": "해고",
        "title": "부당해고 구제신청 및 정당성 요건",
        "content": "근로기준법 제23조 제1항에 따라 해고는 '정당한 이유'가 있어야 하며, 5인 이상 사업장에서는 반드시 해고 사유와 시기를 '서면'으로 통지해야만 효력이 발생합니다."
    }
]

# 💡 혹시 프론트엔드가 POST로 요청할 수도 있으므로, GET과 POST를 주소별로 모두 열어둡니다.
@app.get("/api/cases")
@app.get("/api/cases/")
@app.post("/api/cases")
@app.post("/api/cases/")
async def get_cases(request: Request, category: str = "전체", keyword: str = ""):
    logger.info("✅ 바이블 데이터 매칭 성공하여 전송합니다.")
    return SAMPLE_BIBLE_DATA

# ========================================================
# [핵심 로직] API 키 로드 및 자동 순회(Rotation) 시스템
# ========================================================

def get_safe_api_key():
    keys = []
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        keys.append(env_key.strip())
        
    key_file = "secret_key.txt"
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                for line in f:
                    cleaned_key = line.strip()
                    if cleaned_key and not cleaned_

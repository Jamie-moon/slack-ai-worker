import os
import logging
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 1. 로깅 및 FastAPI 초기화
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gemini Slack Bot & Labor API")

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
# [디버깅 미들웨어] 모든 유입 요청을 실시간으로 추적
# ========================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(
        f"📡 [유입] Method: {request.method} | "
        f"Path: {request.url.path}"
    )
    response = await call_next(request)
    return response

# ========================================================
# [바이블 API] GET/POST 및 슬래시 유무 통합 처리
# ========================================================
SAMPLE_BIBLE_DATA = [
    {
        "id": 1,
        "category": "근로시간",
        "title": "연장근로 한도 위반 여부 산정 기준 (최신 판례)",
        "content": "일주일간 총 근로시간이 52시간을 초과했는지가 기준입니다."
    },
    {
        "id": 2,
        "category": "임금",
        "title": "평균임금과 통상임금의 정의 및 구분",
        "content": "통상임금은 고정급, 평균임금은 3개월간의 실제 수령액 기준입니다."
    }
]

@app.get("/api/cases")
@app.get("/api/cases/")
@app.post("/api/cases")
@app.post("/api/cases/")
async def get_cases(
    request: Request, 
    category: str = "전체", 
    keyword: str = ""
):
    logger.info("✅ 바이블 데이터 반환 성공")
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
                    # 💡 [우측 쪼개기 수정을 통해 절대 안 잘리게 방어]
                    if not cleaned_key:
                        continue
                    if cleaned_key.startswith("#"):
                        continue
                    keys.append(cleaned_key)
        except Exception as e:
            logger.error(f"🔑 키 파일 읽기 실패: {e}")
            
    return keys

def call_openrouter_api(old_api_key_param, user_query):
    api_keys = get_safe_api_key()
    if not api_keys:
        return "⚠️ API 키가 설정되지 않았습니다."
        
    blackbox_report = []
    for idx, api_key in enumerate(api_keys, start=1):
        if api_key.startswith("sk-or-"):
            blackbox_report.append(f"❌ [{idx}번 - 구형 키 에러] ->")
            continue

        # 💡 URL 문자열도 안전하게 결합 방식으로 쪼개기
        base_url = "https://generativelanguage.googleapis.com/v1beta/models/"
        url = f"{base_url}gemini-2.5-flash:generateContent?key={api_key}"
        
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": user_query}]}],
            "systemInstruction": {
                "parts": [{
                    "text": "당신은 전문 공인노무사 AI입니다."
                }]
            }
        }
        
        try:
            response = requests.post(

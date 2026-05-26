import os
import logging
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 1. 로깅 및 FastAPI 초기화
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("🚀 app.py 안전 모드 가동...")

app = FastAPI(title="Gemini Slack Bot & Labor API")

# 2. CORS 전면 허용 (보안 규제 해제)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

# ========================================================
# [보안 강화] 슬래시 기호 무관하게 다 잡아내는 바이블 API
# ========================================================

# 💡 주소 끝에 슬래시가 있든(/) 없든 모두 이 함수가 처리하도록 이중 등록합니다.
@app.get("/api/cases")
@app.get("/api/cases/")
async def get_cases(category: str = "전체", keyword: str = ""):
    logger.info(f"🔍 [API 요청 수신] 카테고리: {category}, 키워드: {keyword}")
    
    bible_data = [
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
    
    if keyword:
        filtered_data = [
            item for item in bible_data 
            if keyword in item["title"] or keyword in item["content"]
        ]
        return filtered_data
        
    return bible_data

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
                    if cleaned_key and not cleaned_key.startswith("#"):
                        keys.append(cleaned_key)
        except Exception as e:
            logger.error(f"🔑 키 파일 읽기 실패: {e}")
            
    return keys

def call_openrouter_api(old_api_key_param, user_query):
    api_keys = get_safe_api_key()
    if not api_keys:
        return "⚠️ API 키가 설정되지 않았습니다. 환경변수나 secret_key.txt 파일을 확인해주세요."
        
    blackbox_report = []
    
    for idx, api_key in enumerate(api_keys, start=1):
        if api_key.startswith("sk-or-"):
            blackbox_report.append(f"❌ [secret_key.txt {idx}번째 줄 - 이전 OpenRouter 키 분기 에러] ->")
            continue

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": user_query}]}],
            "systemInstruction": {
                "parts": [{"text": "당신은 전문 공인노무사 AI입니다. 대한민국 노동법과 최신 판례를 기반으로 명확하고 신뢰할 수 있는 답변을 제공하세요."}]
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                blackbox_report.append(f"❌ [secret_key.txt {idx}번째 줄 - 구글 REST 에러 (Status {response.status_code})] ->")
        except requests.exceptions.Timeout:
            blackbox_report.append(f"❌ [secret_key.txt {idx}번째 줄 - 네트워크 타임아웃 에러] ->")
        except Exception as e:
            logger.error(f"❌ 키 {idx}번 구동 중 에러 발생: {e}")
            blackbox_report.append(f"❌ [secret_key.txt {idx}번째 줄 - 알 수 없는 시스템 에러] ->")

    report_header = "⏳ 모든 API 열쇠가 차단되었습니다. 블랙박스 리포트를 확인해 주세요:\n\n"
    return report_header + "\n".join(blackbox_report)

# ========================================================
# [Slack 연동 및 엔드포인트]
# ========================================================

def send_slack_message(channel, text, thread_ts=None):
    if not SLACK_BOT_TOKEN:
        logger.error("❌ SLACK_BOT_TOKEN 미설정")
        return
    url = "https://slack.com/api/chat.postMessage"
    token = SLACK_BOT_TOKEN if SLACK_BOT_TOKEN.startswith("Bearer ") else f"Bearer {SLACK_BOT_TOKEN}"
    headers = {"Authorization": token, "Content-Type": "application/json; charset=utf-8"}
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    try:
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"❌ Slack 전송 에러: {e}")

def process_ai_and_respond(channel, user_query, thread_ts=None):
    ai_response = call_openrouter_api(None, user_query)
    send_slack_message(channel, ai_response, thread_ts)

@app.get("/")
async def root():
    return {"status": "healthy", "message": "서버 가동 중"}

@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    if "challenge" in body:
        return PlainTextResponse(body["challenge"])

    if "event" in body:
        event = body["event"]
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return {"ok": True}

        if event.get("type") in ["app_mention", "message"]:
            user_query = event.get("text", "")
            channel = event.get("channel", "")
            thread_ts = event.get("ts")
            
            if user_query and channel:
                background_tasks.add_task(process_ai_and_respond, channel, user_query, thread_ts)
                
    return {"ok": True}

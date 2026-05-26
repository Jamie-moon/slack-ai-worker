import os
import logging
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse

# 1. 로깅 및 FastAPI 초기화
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("🚀 app.py 초기 로드 시작...")

app = FastAPI(title="Gemini Slack Bot")

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

# ========================================================
# [핵심 로직] API 키 로드 및 자동 순회(Rotation) 시스템
# ========================================================

def get_safe_api_key():
    """ 환경변수 및 secret_key.txt의 모든 줄을 읽어 키 리스트를 반환합니다. """
    keys = []
    
    # 1순위: 클라우드 환경변수 확인
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        keys.append(env_key.strip())
        
    # 2순위: secret_key.txt 파일 확인
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
    """ 등록된 모든 API 키를 순회하며 정상 작동하는 키로 답변을 받아옵니다. """
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
            # 💡 [수정 완료] 잘려 나가지 않도록 안전하게 줄바꿈 처리했습니다.
            response = requests.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=15
            )
            
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
# [Slack 연동 및 엔드포인트] 백그라운드 처리 시스템
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
    return {"status": "healthy", "message": "Gemini 로테이션 봇이 가동 중입니다."}

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
                background_tasks.add

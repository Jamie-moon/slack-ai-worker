import os
import logging
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse

# 1. 로깅 및 FastAPI 앱 초기화 (Uvicorn이 이 'app'을 찾아서 실행합니다)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gemini Slack Bot")

# [환경변수] Slack으로 답변을 다시 쏘아줄 때 필요한 봇 토큰
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

# ========================================================
# [핵심 로직] API 키 로드 및 Gemini 호출 함수
# ========================================================

def get_safe_api_key() -> str:
    """ 환경변수 또는 로컬 파일에서 Gemini API 키를 안전하게 로드합니다. """
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key.strip()
        
    key_file = "secret_key.txt"
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"🔑 키 파일을 읽는 중 오류가 발생했습니다: {e}")
            
    return ""

def call_openrouter_api(old_api_key_param, user_query: str) -> str:
    """ 기존 Slack 봇 호환용 함수. 내부적으로는 최신 Gemini API를 호출합니다. """
    api_key = get_safe_api_key()
    if not api_key:
        return "⚠️ API 키가 설정되지 않았습니다. 환경변수(GEMINI_API_KEY)나 secret_key.txt 파일을 확인해주세요."
        
    if api_key.startswith("sk-or-"):
        return "❌ 이전 OpenRouter 키가 감지되었습니다. 구글 제미나이 키(AIzaSy...)로 교체해주세요."

    # 최신 고성능 무료 모델인 gemini-2.5-flash 사용
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{
            "parts": [{"text": user_query}]
        }],
        "systemInstruction": {
            "parts": [{"text": "당신은 전문 공인노무사 AI입니다. 대한민국 노동법과 최신 판례를 기반으로 명확하고 신뢰할 수 있는 답변을 제공하세요."}]
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 400:
            return "❌ 요청 형식이 올바르지 않습니다. (API 스펙 확인 필요)"
        elif response.status_code == 403:
            return "❌ API 키가 유효하지 않거나 권한이 없습니다. 키를 다시 확인해주세요."
        elif response.status_code == 429:
            return "⏳ 무료 제공량 제한(Rate Limit)을 초과했습니다. 잠시 후 다시 시도해주세요."
            
        response.raise_for_status()
        result = response.json()
        
        return result['candidates'][0]['content']['parts'][0]['text']
        
    except requests.exceptions.Timeout:
        return "⏳ AI 서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
    except Exception as e:
        logger.error(f"🤖 Gemini API 호출 중 예기치 못한 오류 발생: {e

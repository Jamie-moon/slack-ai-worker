import os
import requests
from flask import Flask, request, jsonify # 슬랙 연동을 위한 예시 (기존 프레임워크에 맞게 유지)

# [1] 에러 방지용 안전한 키 로드 함수
def get_safe_api_key():
    # 1순위: 클라우드 환경변수(GEMINI_API_KEY) 확인
    cloude_key = os.environ.get("GEMINI_API_KEY")
    if cloude_key:
        return cloude_key
        
    # 2순위: 로컬 secret_key.txt 파일 확인 (파일이 없어도 서버가 죽지 않게 try-except 처리)
    try:
        if os.path.exists("secret_key.txt"):
            with open("secret_key.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
        
    # 둘 다 없으면 일단 임시 문자열 반환 (배포 중단 방지)
    return "NO_KEY"

# [2] 기존 오픈라우터 함수 이름을 그대로 유지하되, 내부만 제미나이로 교체!
# (이렇게 해야 다른 코드에서 이 함수를 부를 때 에러가 안 납니다)
def call_openrouter_api(old_api_key_param, user_query):
    # 무조건 안전하게 가져온 새 구글/제미나이 키를 사용합니다.
    api_key = get_safe_api_key()
    
    if api_key == "NO_KEY" or not api_key:
        return "⏳ API 열쇠가 올바르지 않거나 설정되지 않았습니다. 환경변수나 secret_key.txt를 확인해주세요."

    # 만약 구글 키가 아니라 아직 오픈라우터 키라면 구글 주소로 요청 시 에러가 나므로 분기 처리
    if api_key.startswith("sk-or-"):
        return "❌ 여전히 옛날 오픈라우터 키가 들어가 있습니다. 구글 제미나이 키(AIzaSy...)로 교체해주세요!"

    # 💡 100% 무료 구글 제미나이 API 호출 주소
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {
            "parts": [{"text": "당신은 전문 공인노무사 AI입니다. 대한민국 노동법, 최신 판례를 기반으로 명확하게 답변하세요."}]
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"❌ AI 분석 중 오류가 발생했습니다: {str(e)}"

# --- 이하 기존의 Slack 이벤트 처리 및 서버 구동 로직(app.route 등)을 그대로 유지하세요 ---

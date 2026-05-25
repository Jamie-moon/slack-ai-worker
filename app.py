import os
import requests

# 함수 이름은 기존 코드와 맞추기 위해 그대로 유지합니다. 내부 로직만 제미나이로 교체!
def call_openrouter_api(api_key_not_used, user_query):
    # 💡 텍스트 파일 대신, 클라우드 환경 변수(GEMINI_API_KEY)에서 키를 직접 읽어옵니다.
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        raise ValueError("❌ 서버에 GEMINI_API_KEY 환경 변수가 설정되지 않았습니다!")

    # 구글 제미나이 호출 주소
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {
            "parts": [{"text": "당신은 전문 공인노무사 AI입니다. 대한민국 노동법을 바탕으로 답하세요."}]
        }
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    
    result = response.json()
    return result['candidates'][0]['content']['parts'][0]['text']

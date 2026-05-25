# 💡 오픈라우터 대신 구글 제미나이 무료 API를 사용하는 함수
import requests

def call_gemini_api(api_key, user_query):
    # 구글 제미나이 1.5 Flash 무료 모델 엔드포인트
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # 구글 제미나이 표준 JSON 데이터 구조
    data = {
        "contents": [{
            "parts": [{"text": user_query}]
        }],
        "systemInstruction": {
            "parts": [{"text": "당신은 전문 공인노무사 AI입니다. 대한민국 노동법, 최신 판례, 고용노동부 지침을 바탕으로 명확하고 신뢰할 수 있는 답변을 제공하세요."}]
        }
    }
    
    # API 요청 보내기
    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status() # 에러 발생 시 예외 처리
    
    result = response.json()
    
    # 구글 응답 데이터에서 AI 답변 텍스트만 추출
    try:
        ai_text = result['candidates'][0]['content']['parts'][0]['text']
        return ai_text
    except (KeyError, IndexError):
        return "AI 답변을 추출하는 중 오류가 발생했습니다."

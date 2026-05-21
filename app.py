import os
import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from google import genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📚 1,600개 데이터 캐싱 공간
KNOWLEDGE_BASE = []
json_path = "laws_data.json"

if os.path.exists(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            KNOWLEDGE_BASE = json.load(f)
        print(f"📦 [STARTUP] 데이터 로드 성공: {len(KNOWLEDGE_BASE)}개")
    except Exception as e:
        KNOWLEDGE_BASE = []

@app.get("/api/cases")
def get_all_cases():
    return KNOWLEDGE_BASE

@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    
    # 🌟 쓸 수 있는 모든 무료 키들을 리스트에 수집
    available_keys = []
    
    # 1. Render 환경변수 키 수집
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        available_keys.append(env_key.strip())
        
    # 2. secret_key.txt에 적힌 여러 개의 무료 키 수집
    if os.path.exists("secret_key.txt"):
        with open("secret_key.txt", "r", encoding="utf-8") as f:
            for line in f:
                clean_key = line.strip()
                if clean_key and clean_key not in available_keys:
                    available_keys.append(clean_key)
                    
    if not available_keys:
        return {"answer": "❌ [설정 오류] 등록된 제미나이 API 키가 단 하나도 없습니다. 키 등록을 확인해 주세요."}

    # 데이터 서칭용 콘텍스트 조립
    keywords = query.split()
    related_docs = []
    for item in KNOWLEDGE_BASE:
        if not isinstance(item, dict): continue
        q_text = str(item.get("question", ""))
        if any(kw in q_text for kw in keywords):
            related_docs.append(f"참고 조항/판례: {q_text}\n내용: {item.get('answer', '')}")
            if len(related_docs) >= 5:
                break

    context_text = "\n\n".join(related_docs) if related_docs else "관련된 구체적 가이드라인 없음."

    prompt = f"""
    당신은 대한민국 고용노동부 출신의 베테랑 공인노무사입니다.
    제공된 [참고 데이터]를 바탕으로 [유저의 질문]을 실시간으로 분석하여 전문적이고 명확한 솔루션을 제공하세요.

    [참고 데이터]
    {context_text}

    [유저의 질문]
    "{query}"

    [답변 지침]
    1. 반드시 제공된 참고 데이터의 법적 근거를 인용하며 답변을 시작하세요.
    2. 위법 여부를 진단하고, 실무적 행동 지침(Action Plan)을 단계별로 제시하세요.
    """

    # 🌟 [무적 루프] 400이든 429든 에러가 나면 무조건 다음 키로 토스합니다.
    last_error = ""
    for i, api_key in enumerate(available_keys):
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            # 하나라도 성공하면 즉시 답변 반환 후 종료!
            return {"answer": response.text.strip()}
            
        except Exception as google_err:
            last_error = str(google_err)
            print(f"⚠️ [{i+1}번 키 실패] 원인: {last_error}. 즉시 다음 예비 키로 넘어갑니다.")
            continue # 에러 종류 상관없이 다음 키로 무조건 패스
                
    # 모든 키가 다 실패했을 때만 에러 총집합 출력
    return {"answer": f"⏳ 등록된 모든 무료 키가 만료되었거나 한도를 초과했습니다.\n(마지막 엔진 에러: {last_error})\n\n💡 해결책: Google AI Studio에서 새 키를 받아 secret_key.txt에 한 줄 더 추가해 주세요!"}

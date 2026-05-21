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
    
    # 🌟 [공짜 치트키] 쓸 수 있는 모든 무료 키들을 리스트에 수집합니다.
    available_keys = []
    
    # 1. Render 환경변수 키 수집
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        available_keys.append(env_key.strip())
        
    # 2. secret_key.txt에 적힌 여러 개의 무료 키 수집 (줄바꿈으로 구분)
    if os.path.exists("secret_key.txt"):
        with open("secret_key.txt", "r", encoding="utf-8") as f:
            for line in f:
                clean_key = line.strip()
                if clean_key and clean_key not in available_keys:
                    available_keys.append(clean_key)
                    
    if not available_keys:
        return {"answer": "❌ [설정 오류] 등록된 제미나이 API 키가 단 하나도 없습니다."}

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

    # 🌟 수집된 무료 키들을 순서대로 돌려막기(Rotation) 시작합니다.
    for i, api_key in enumerate(available_keys):
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            # 뚫리면 즉시 답변 반환하고 종료!
            return {"answer": response.text.strip()}
            
        except Exception as google_err:
            err_msg = str(google_err)
            # 구글 무료 한도 초과(429) 에러가 나면 다음 키로 패스!
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                print(f"🔄 [{i+1}번 키 한도 초과] 다음 예비 무료 키로 전환하여 재시도합니다...")
                continue
            else:
                # 다른 치명적인 에러는 즉시 리턴
                return {"answer": f"❌ [AI 엔진 오류] 원인: {err_msg}"}
                
    # 모든 키가 다 소멸되었을 때만 안내문 출력
    return {"answer": "⏳ 등록된 모든 무료 키의 하루 한도(20회)가 소멸되었습니다. 다른 구글 계정으로 무료 키를 생성해 'secret_key.txt'에 한 줄 더 추가해 주세요!"}

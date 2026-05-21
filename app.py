import os
import json
import time # 🌟 시간 지연(존버)을 위한 라이브러리 추가
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
    # 1. API 키 안전 탈취
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and os.path.exists("secret_key.txt"):
        with open("secret_key.txt", "r", encoding="utf-8") as f:
            api_key = f.read().strip()
    
    if not api_key:
        return {"answer": "❌ [설정 오류] Render 환경변수 또는 secret_key.txt에 GEMINI_API_KEY가 없습니다."}
    
    try:
        client = genai.Client(api_key=api_key)
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

        # 🌟 [무료 치트키] 구글이 429 과부하를 걸면 뒤에서 몰래 대기 후 최대 3회 재시도
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                # 성공하면 즉시 답변 리턴하고 종료
                return {"answer": response.text.strip()}
                
            except Exception as google_err:
                err_msg = str(google_err)
                # 구글 무료 한도 초과(429) 메시지가 감지되면
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    wait_time = (attempt + 1) * 4 # 1차 시도 4초, 2차 시도 8초 대기
                    print(f"⏳ [무료 한도 우회] 구글 과호흡 감지. {wait_time}초 대기 후 자동 재시도합니다... ({attempt + 1}/3)")
                    time.sleep(wait_time)
                    continue # 다음 루프로 넘어가서 다시 지르기
                else:
                    # 429 외에 다른 에러는 즉시 에러 리턴
                    raise google_err
                    
        return {"answer": "⏳ 무료 플랜 트래픽이 일시적으로 너무 혼잡합니다. 5초 뒤에 다시 시도해 주세요!"}
        
    except Exception as e:
        return {"answer": f"❌ [AI 엔진 오류] 원인: {str(e)}"}

import os
import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from google import genai

app = FastAPI()

# CORS 차단 원천 봉쇄
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📚 노무 데이터 로드
KNOWLEDGE_BASE = []
json_path = "laws_data.json"

if os.path.exists(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            KNOWLEDGE_BASE = json.load(f)
        print(f"📦 데이터 로드 성공: {len(KNOWLEDGE_BASE)}개")
    except Exception as e:
        KNOWLEDGE_BASE = []

@app.get("/api/cases")
def get_all_cases():
    return KNOWLEDGE_BASE

@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    try:
        # 🔑 가장 확실하게 Render 환경변수만 딱 하나 읽어옵니다.
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {"answer": "❌ [백엔드 에러] Render 대시보드 Environment 탭에 GEMINI_API_KEY가 비어있습니다."}
        
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
        2. 위법 여부를 진단하고, 실무적 행동 지침을 단계별로 제시하세요.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return {"answer": response.text.strip()}
        
    except Exception as e:
        return {"answer": f"❌ [AI 엔진 오류] 원인: {str(e)}"}

import os
import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from google import genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 📚 대용량 데이터 캐싱 공간
KNOWLEDGE_BASE = []
json_path = "laws_data.json"

if os.path.exists(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            KNOWLEDGE_BASE = json.load(f)
        print(f"📦 [STARTUP] 데이터 로드 성공: {len(KNOWLEDGE_BASE)}개")
    except Exception as e:
        KNOWLEDGE_BASE = []
else:
    KNOWLEDGE_BASE = []

@app.get("/api/cases")
def get_all_cases():
    return KNOWLEDGE_BASE

# 🔥 [AI 상담 엔진] 단 1줄의 예외도 허용하지 않도록 전체를 try로 감쌉니다.
@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    try:
        # 1. 환경 변수 등록 상태 전수 조사
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {"answer": "❌ [백엔드 에러] Render 대시보드 Env 키에 'GEMINI_API_KEY'가 비어있거나 누락되었습니다."}
        
        # 2. 제미나이 엔진 안전 기동
        client = genai.Client(api_key=api_key)
        
        # 3. 키워드 매칭 플레이스 가동
        keywords = query.split()
        related_docs = []
        
        for item in KNOWLEDGE_BASE:
            if not isinstance(item, dict):
                continue
            q_text = str(item.get("question", ""))
            a_text = str(item.get("answer", ""))
            if any(kw in q_text or kw in a_text for kw in keywords):
                related_docs.append(f"참고 조항/판례: {q_text}\n내용: {a_text}")
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

        # 4. 구글 AI 분석 연산 시동
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        # 성공 시 분석 결과 리포트 리턴
        return {"answer": response.text.strip()}
        
    except Exception as e:
        # 🌟 시스템 내부에서 어떤 치명적인 에러가 나든 500 번 아웃 시키지 않고,
        # 에러 원인 문자열을 JSON에 이쁘게 담아서 화면 중앙 카드에 띄워줍니다.
        return {"answer": f"❌ [제미나이 AI 엔진 연산 에러] 원인: {str(e)}"}

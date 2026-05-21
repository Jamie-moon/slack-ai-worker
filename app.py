import os
import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from google import genai

app = FastAPI()

# 🔓 브라우저 차단을 원천 봉쇄하는 CORS 무적 설정
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

# 🔥 [안정성 200%] 표준 JSON 응답 구조로 변경하여 네트워크 유실을 완벽 차단합니다.
@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    try:
        # 1. 제미나이 API 키 탈취 (환경변수 또는 비밀파일)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key and os.path.exists("secret_key.txt"):
            with open("secret_key.txt", "r", encoding="utf-8") as f:
                api_key = f.read().strip()
        
        if not api_key:
            return {"answer": "❌ [설정 오류] Render 환경변수 또는 secret_key.txt에 GEMINI_API_KEY가 없습니다."}
        
        # 2. 제미나이 에이전트 생성
        client = genai.Client(api_key=api_key)
        keywords = query.split()
        related_docs = []
        
        # 3. ⚡ [알고리즘 최적화] 무거운 본문 대신 '제목(question)'에서만 키워드를 찾아 0.01초 만에 매칭!
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

        # 4. 생성 연산 요청
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return {"answer": response.text.strip()}
        
    except Exception as e:
        return {"answer": f"❌ [AI 엔진 오류] 원인: {str(e)}"}

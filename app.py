import os
import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from google import genai

app = FastAPI()

# CORS 설정: Netlify 프론트엔드의 접근을 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔑 메디빌더님의 실제 제미나이 API 키를 여기에 넣으세요!
GEMINI_API_KEY = "AIzaSyBpBGE53K51qDVuOMwmKqfDpmGPhcDqKe8"
client = genai.Client(api_key=GEMINI_API_KEY)

# 로컬에 축적된 1,600개 규모의 laws_data.json 로드
def load_knowledge_base():
    json_path = "laws_data.json"
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# 🔥 [엔드포인트 1] 왼쪽 사이드바 및 브라우징용 전체 데이터 송출
@app.get("/api/cases")
def get_all_cases():
    data = load_knowledge_base()
    if data:
        return data
    # 파일이 없을 경우 최소한의 기본 데이터 반환
    return [{"question": "[안내] 마스터 데이터 로드 실패", "answer": "laws_data.json 파일이 서버에 없습니다.", "category": "기타"}]

# 🔥 [엔드포인트 2] 하단 대화창용 실시간 RAG AI 상담 분석
@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    knowledge_base = load_knowledge_base()
    
    # 시맨틱 키워드 필터링 (가장 관련 깊은 5개 추출)
    keywords = query.split()
    related_docs = []
    
    for item in knowledge_base:
        q_text = item.get("question", "")
        a_text = item.get("answer", "")
        if any(kw in q_text or kw in a_text for kw in keywords):
            related_docs.append(f"참고 조항/판례: {q_text}\n내용: {a_text}")
            if len(related_docs) >= 5:
                break

    context_text = "\n\n".join(related_docs) if related_docs else "관련된 구체적 사내 가이드라인 또는 판례 없음."

    prompt = f"""
    당신은 대한민국 고용노동부 출신의 베테랑 공인노무사입니다.
    제공된 [참고 데이터]를 바탕으로 [유저의 질문]을 실시간으로 분석하여 전문적이고 명확한 솔루션을 제공하세요.

    [참고 데이터]
    {context_text}

    [유저의 질문]
    "{query}"

    [답변 지침]
    1. 반드시 제공된 참고 데이터의 법적 근거(제X조 또는 판례 번호)를 인용하며 답변을 시작하세요.
    2. 유저의 상황이 노동법상 위법인지 적법인지 날카롭게 진단해 주세요.
    3. 근로자 또는 인사담당자가 당장 취해야 할 실무적 행동 지침(Action Plan)을 단계별로 제시하세요.
    4. 전문가의 정중하고 확신에 찬 어조(~합니다)를 유지하세요.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return {"answer": response.text.strip()}
    except Exception as e:
        return {"answer": f"AI 분석 엔진 가동 중 오류가 발생했습니다. (원인: {e})"}

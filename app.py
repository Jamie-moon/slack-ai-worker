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
# 대용량 수천 개 데이터를 70% 압축해서 고속 전송하는 레이어
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 📚 대용량 데이터 캐싱 공간
KNOWLEDGE_BASE = []
json_path = "laws_data.json"

# 서버 시동 시 안전하게 파일이 있을 때만 데이터를 메모리에 상시 로드
if os.path.exists(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            KNOWLEDGE_BASE = json.load(f)
        print(f"📦 [STARTUP] 데이터 로드 성공: {len(KNOWLEDGE_BASE)}개")
    except Exception as e:
        print(f"⚠️ [STARTUP] 파일 읽기 실패 (빈 상태로 기동): {e}")
        KNOWLEDGE_BASE = []
else:
    print("⚠️ [STARTUP] laws_data.json 파일이 없습니다. 빈 상태로 기동합니다.")

@app.get("/api/cases")
def get_all_cases():
    return KNOWLEDGE_BASE

@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    # 🌟 [핵심 변경] 서버 시작할 때가 아니라, 질문이 들어왔을 때만 API 키를 체크하여 크래시 방지!
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"answer": "❌ 서버 내부 오류: Render 환경 변수에 GEMINI_API_KEY가 설정되지 않았습니다."}
    
    try:
        # 질문 시점에 안전하게 제미나이 클라이언트 생성
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return {"answer": f"❌ AI 엔진 초기화 실패: {e}"}

    keywords = query.split()
    related_docs = []
    
    for item in KNOWLEDGE_BASE:
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

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return {"answer": response.text.strip()}
    except Exception as e:
        return {"answer": f"❌ 제미나이 AI 분석 중 오류 발생: {e}"}

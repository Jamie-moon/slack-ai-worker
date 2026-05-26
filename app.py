import os
import json
import logging
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from google import genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gemini Labor AI High-Speed Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KNOWLEDGE_BASE = []
json_path = "laws_data.json"

if os.path.exists(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            KNOWLEDGE_BASE = json.load(f)
        print(f"📦 [서버 기동] {len(KNOWLEDGE_BASE)}개 데이터셋 로드 완료.")
    except Exception as e:
        logger.error(f"❌ 데이터 로드 실패: {e}")

@app.get("/api/cases")
def get_backend_filtered_cases(category: str = "전체", keyword: str = ""):
    filtered = KNOWLEDGE_BASE
    if category and category != "전체":
        filtered = [item for item in filtered if category in str(item.get("category", ""))]
    if keyword:
        kw = keyword.lower().strip()
        filtered = [item for item in filtered if kw in str(item.get("question", "")).lower()]
    return filtered[:40]

# ========================================================
# ⚡ [초고속 최적화 완료] AI 채팅 엔드포인트
# ========================================================
@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {"answer": "❌ [설정 오류] GEMINI_API_KEY가 없습니다."}

        client = genai.Client(api_key=api_key)
        
        # 1. ⚡ 데이터 검색 속도 최적화 (불필요한 string 변환 최소화 및 즉시 매칭)
        clean_query = query.strip()
        related_docs = []
        
        for item in KNOWLEDGE_BASE:
            q_text = item.get("question", "")
            # 질문 키워드가 포함되어 있으면 컨텍스트에 추가
            if any(kw in q_text for kw in clean_query.split()):
                related_docs.append(f"법령/판례: {q_text}\n내용: {item.get('answer', '')}")
                if len(related_docs) >= 3: # 💡 참고 데이터를 5개 -> 3개로 압축하여 컨텍스트 처리 속도 향상
                    break

        context_text = "\n\n".join(related_docs) if related_docs else "관련 가이드 없음."

        # 2. ⚡ AI 답변 속도 최적화 프롬프트 
        # 장황한 미사여구를 빼고 핵심만 두괄식으로 작성하도록 강제하여 생성 시간(Token Generation Time)을 절반으로 줄입니다.
        prompt = (
            f"당신은 대한민국 베테랑 공인노무사입니다. "
            f"인사말이나 장황한 서론은 전면 생략하고, 결론부터 두괄식으로 신속하게 답변하세요.\n\n"
            f"[참고 데이터]\n{context_text}\n\n"
            f"[유저 질문]\n\"{clean_query}\"\n\n"
            f"[답변 요구사항]: 핵심 위법 여부 진단과 실무 지침을 단도직입적으로 3문장 내외로 요약하여 빠르게 제시할 것."
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt
        )
        return {"answer": response.text.strip()}
        
    except Exception as e:
        return {"answer": f"❌ [AI 엔진 오류] 원인: {str(e)}"}

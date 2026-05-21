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

# 📚 대용량 마스터 데이터셋을 서버 메모리에 단 1회만 로드 (접속 속도 0초의 비결)
KNOWLEDGE_BASE = []
json_path = "laws_data.json"

if os.path.exists(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            KNOWLEDGE_BASE = json.load(f)
        print(f"📦 [서버 기동] {len(KNOWLEDGE_BASE)}개 데이터셋 메모리 탑재 완료.")
    except Exception as e:
        KNOWLEDGE_BASE = []

@app.get("/api/cases")
def get_backend_filtered_cases(category: str = "전체", keyword: str = ""):
    """ 🌟 [광속 연동] 수백만 건의 데이터 중 브라우저가 요청한 조건의 상위 40개만 칼같이 잘라 보냅니다. """
    filtered = KNOWLEDGE_BASE
    
    # 1. 카테고리 서버 필터링
    if category and category != "전체":
        filtered = [item for item in filtered if category in str(item.get("category", "")) or category in str(item.get("question", ""))]
        
    # 2. 키워드/판례/조항 서버 검색
    if keyword:
        kw = keyword.lower().strip()
        filtered = [
            item for item in filtered 
            if kw in str(item.get("question", "")).lower() or kw in str(item.get("answer", "")).lower()
        ]
        
    # 3. 네트워크 부하를 최소화하기 위해 딱 40개만 가볍게 전송 (용량: 몇 MB -> 몇 KB로 축소)
    return filtered[:40]

@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {"answer": "❌ [설정 오류] Render 서버에 GEMINI_API_KEY가 없습니다."}
        
        client = genai.Client(api_key=api_key)
        
        # AI 검토용 콘텍스트 추출
        keywords = query.split()
        related_docs = []
        for item in KNOWLEDGE_BASE:
            q_text = str(item.get("question", ""))
            if any(kw in q_text for kw in keywords):
                related_docs.append(f"참고: {q_text}\n내용: {item.get('answer', '')}")
                if len(related_docs) >= 5: break

        context_text = "\n\n".join(related_docs) if related_docs else "관련 가이드 없음."

        prompt = f"""
        당신은 대한민국 고용노동부 출신의 베테랑 공인노무사입니다.
        [참고 데이터]를 바탕으로 [유저의 질문]에 대해 위법 여부를 진단하고 실무 지침을 단계별로 제시하세요.
        [참고 데이터]\n{context_text}\n\n[유저의 질문]\n"{query}"
        """

        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return {"answer": response.text.strip()}
    except Exception as e:
        return {"answer": f"❌ [AI 엔진 오류] 원인: {str(e)}"}

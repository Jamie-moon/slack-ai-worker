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

# 📚 대용량 마스터 데이터셋을 서버 메모리에 탑재 (0.1초 로딩의 비결)
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
    """ 🌟 브라우저가 요청한 조건의 상위 40개만 잘라 보내는 고속도로 API (구글 API 안 써서 평생 무료) """
    filtered = KNOWLEDGE_BASE
    
    if category and category != "전체":
        filtered = [item for item in filtered if category in str(item.get("category", "")) or category in str(item.get("question", ""))]
        
    if keyword:
        kw = keyword.lower().strip()
        filtered = [
            item for item in filtered 
            if kw in str(item.get("question", "")).lower() or kw in str(item.get("answer", "")).lower()
        ]
        
    return filtered[:40]

@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    
    # 🔑 [돌려막기 엔진 복원] 쓸 수 있는 모든 무료 키들을 리스트에 수집
    available_keys = []
    
    # 1. Render 환경변수에 등록한 메인 키 수집
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        available_keys.append(env_key.strip())
        
    # 2. secret_key.txt에 한 줄씩 적어둔 예비 무료 키들 수집
    if os.path.exists("secret_key.txt"):
        with open("secret_key.txt", "r", encoding="utf-8") as f:
            for line in f:
                clean_key = line.strip()
                if clean_key and clean_key not in available_keys:
                    available_keys.append(clean_key)
                    
    if not available_keys:
        return {"answer": "❌ [설정 오류] 등록된 제미나이 API 키가 단 하나도 없습니다. secret_key.txt를 확인하세요."}

    # AI 참고용 컨텍스트 조립
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

    # 🌟 [무적 루프 가동] 구글이 429 한도 초과 에러를 던지면 묻지도 따지지도 않고 다음 키로 토스!
    last_error = ""
    for i, api_key in enumerate(available_keys):
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            # 단 하나라도 성공하면 즉시 에러 없이 정답 리턴 후 종료!
            return {"answer": response.text.strip()}
        except Exception as e:
            last_error = str(e)
            print(f"⚠️ [{i+1}번 키 429 한도초과 및 에러] 즉시 다음 예비 키로 전환합니다. 원인: {last_error}")
            continue

    # 모든 키가 전부 다 터졌을 때만 최종 안내문 출력
    return {"answer": f"⏳ 등록된 모든 무료 키의 일일 한도(429)가 초과되었습니다.\n(마지막 에러: {last_error})\n\n💡 해결책: Google AI Studio에서 새 비밀키를 공짜로 발급받아 secret_key.txt에 한 줄 더 추가해 주세요!"}

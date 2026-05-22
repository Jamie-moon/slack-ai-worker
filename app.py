import os
import json
import time  # 🌟 자동 시간 지연을 위해 내장 라이브러리 추가
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

# 마스터 데이터셋 메모리 로드
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
    filtered = KNOWLEDGE_BASE
    if category and category != "전체":
        filtered = [item for item in filtered if category in str(item.get("category", "")) or category in str(item.get("question", ""))]
    if keyword:
        kw = keyword.lower().strip()
        filtered = [item for item in filtered if kw in str(item.get("question", "")).lower() or kw in str(item.get("answer", "")).lower()]
    return filtered[:40]

@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    available_keys = []
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        available_keys.append(env_key.strip())
        
    if os.path.exists("secret_key.txt"):
        with open("secret_key.txt", "r", encoding="utf-8") as f:
            for line in f:
                clean_key = line.strip()
                if clean_key and clean_key not in available_keys:
                    available_keys.append(clean_key)
                    
    if not available_keys:
        return {"answer": "❌ [설정 오류] 등록된 제미나이 API 키가 단 하나도 없습니다."}

    # 콘텍스트 구축
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
    [참고 데이터]를 바탕으로 [유저의 질문]에 대해 위법 여부를 진단하고 실무 지침을 제시하세요.
    [참고 데이터]\n{context_text}\n\n[유저의 질문]\n"{query}"
    """

    last_error = ""
    for i, api_key in enumerate(available_keys):
        # 🌟 [무적 안전망] 각 키당 최대 2번씩 백그라운드 재시도 기회를 줍니다.
        for attempt in range(2):
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                return {"answer": response.text.strip()}
            except Exception as e:
                err_msg = str(e)
                
                # 🔍 구글이 "잠시 쉬다 오라(429, RESOURCE_EXHAUSTED)"고 가로막은 경우
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    if attempt == 0:
                        # 유저 모르게 백엔드 서버단에서 3.2초(구글 요구치 이상) 동안 숨을 고른 뒤 재시도 슛!
                        print(f"⏳ [{i+1}번 키] 순간 과부하(429) 감지 ➡️ 3.2초 대기 후 자동 재시도합니다...")
                        time.sleep(3.2)
                        continue
                
                # 429 가 아니거나, 2번째 재시도마저 실패했다면 다음 예비 키로 즉시 패스
                last_error = err_msg
                print(f"⚠️ [{i+1}번 키 에러 발생] 예비 키로 우회합니다. 원인: {last_error}")
                break 

    return {"answer": f"⏳ 모든 무료 키의 순간 트래픽 제한이 걸렸습니다. 잠시 후 다시 질문해 주세요.\n(에러 요약: {last_error})"}

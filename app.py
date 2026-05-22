import os
import json
import time
import re
import urllib.request
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
    keys_info = []
    
    # 1. Render 환경변수 수집
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        keys_info.append({"key": env_key.strip(), "origin": "Render 환경변수"})
        
    # 2. secret_key.txt 내의 모든 키 수집
    if os.path.exists("secret_key.txt"):
        with open("secret_key.txt", "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                clean_key = line.strip()
                if clean_key:
                    if not any(k["key"] == clean_key for k in keys_info):
                        keys_info.append({"key": clean_key, "origin": f"secret_key.txt {idx}번째 줄"})
                    
    if not keys_info:
        return {"answer": "❌ [설정 오류] 등록된 API 키가 단 하나도 없습니다."}

    # 🌟 [오픈라우터 무조건 1순위 강제 정렬] sk-or- 키를 리스트 맨 앞으로 대피시킵니다.
    keys_info.sort(key=lambda x: 0 if x["key"].startswith("sk-or-") else 1)

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

    # 모든 키의 실행 결과를 기록할 블랙박스 서랍
    error_reports = []

    for info in keys_info:
        api_key = info["key"]
        origin_name = info["origin"]
        
        # 🟦 오픈라우터 키 일 때 (무조건 최우선 실행)
        if api_key.startswith("sk-or-"):
            try:
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com",
                    "X-Title": "Nomu Wiki"
                }
                payload = {
                    "model": "google/gemini-2.5-flash",
                    "messages": [{"role": "user", "content": prompt}]
                }
                
                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
                
                with urllib.request.urlopen(req, timeout=15) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                
                if "choices" in res_data and len(res_data["choices"]) > 0:
                    return {"answer": res_data["choices"][0]["message"]["content"].strip()}
                else:
                    error_reports.append(f"❌ [{origin_name} - 오픈라우터 거절] -> {res_data}")
                    continue
            except Exception as e:
                error_reports.append(f"❌ [{origin_name} - 오픈라우터 에러] -> {str(e)}")
                continue

        # 🟩 일반 구글 공식 키 일 때 (오픈라우터가 실패하거나 없을 때만 백업 가동)
        else:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                return {"answer": response.text.strip()}
            except Exception as e:
                error_reports.append(f"❌

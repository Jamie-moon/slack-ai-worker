import os
import json
import time
import re
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
    # 🌟 [출처 추적 시스템] 키가 어디서 왔는지 출처를 함께 기록합니다.
    keys_info = []
    
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        keys_info.append({"key": env_key.strip(), "origin": "Render 환경변수 (GEMINI_API_KEY)"})
        
    if os.path.exists("secret_key.txt"):
        with open("secret_key.txt", "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                clean_key = line.strip()
                if clean_key:
                    # 중복 키 제거
                    if not any(k["key"] == clean_key for k in keys_info):
                        keys_info.append({"key": clean_key, "origin": f"secret_key.txt 파일의 {idx}번째 줄"})
                    
    if not keys_info:
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
    failed_origin = ""

    for i, info in enumerate(keys_info):
        api_key = info["key"]
        origin_name = info["origin"]
        
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
                last_error = err_msg
                failed_origin = origin_name
                
                # 🔍 1. 구글이 과부하(429) 제한을 걸었을 때 동적 대기
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    if attempt == 0:
                        match = re.search(r"Please retry in ([\d\.]+)s", err_msg)
                        wait_time = 12.0
                        if match:
                            try: wait_time = float(match.group(1)) + 1.5
                            except: pass
                        print(f"⏳ [{origin_name}] 과부하 감지 ➡️ {wait_time:.2f}초 대기 후 자동 재시도...")
                        time.sleep(wait_time)
                        continue 
                
                # 🔍 2. [핵심] 만약 키 자체가 완전히 잘못된 가짜 키(400)라면 재시도 없이 즉시 다음 키로 패스!
                if "400" in err_msg or "API_KEY_INVALID" in err_msg:
                    print(f"❌ [{origin_name}] 에 등록된 API 키가 올바르지 않습니다! 즉시 우회합니다.")
                    break
                
                break 

    # 🌟 어떤 녀석이 범인인지 화면에 명확하게 고발합니다.
    return {
        "answer": f"⚠️ [API 키 규격 오류 발생]\n\n"
                  f"📌 범인 위치: **{failed_origin}**\n"
                  f"❌ 에러 내용: API 키가 유효하지 않거나 오타가 있습니다. 따옴표나 공백이 껴있지 않은지 해당 위치를 꼭 확인해 주세요!\n\n"
                  f"(상세 에러 로그: {last_error})"
    }

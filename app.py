import os
import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google import genai

app = FastAPI()

# CORS 방어막 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 💡 [핵심 최적화] Streaming을 파괴하던 GZipMiddleware를 완전히 제거했습니다!

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

@app.get("/api/chat")
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
    def stream_gemini_response():
        try:
            # 1. Render 환경 변수 우선 확인
            api_key = os.environ.get("GEMINI_API_KEY")
            
            # 2. 환경 변수가 데달사고 났을 경우 비밀 파일에서 직접 탈취
            if not api_key and os.path.exists("secret_key.txt"):
                with open("secret_key.txt", "r", encoding="utf-8") as f:
                    api_key = f.read().strip()
            
            if not api_key:
                yield "❌ [키 누락] Render 환경변수와 secret_key.txt 파일 모두에서 키를 찾을 수 없습니다."
                return
            
            # 3. 제미나이 에이전트 기동
            client = genai.Client(api_key=api_key)
            keywords = query.split()
            related_docs = []
            
            for item in KNOWLEDGE_BASE:
                if not isinstance(item, dict): continue
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

            # 4. 방해 요소가 사라진 순수 실시간 스트리밍 송출
            response_stream = client.models.generate_content_stream(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            yield f"❌ [AI 엔진 내부 에러] 원인: {str(e)}"

    return StreamingResponse(stream_gemini_response(), media_type="text/plain")

import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 💡 [핵심 최적화] Streaming을 파괴하던 GZipMiddleware를 완전히 제거했습니다!

# 📚 대용량 데이터 캐싱 공간
KNOWLEDGE_BASE = []
@@ -28,6 +29,8 @@
print(f"📦 [STARTUP] 데이터 로드 성공: {len(KNOWLEDGE_BASE)}개")
except Exception as e:
KNOWLEDGE_BASE = []
else:
    KNOWLEDGE_BASE = []

@app.get("/api/cases")
def get_all_cases():
@@ -37,20 +40,19 @@ def get_all_cases():
def ask_labor_ai(query: str = Query(..., description="유저의 노무 질문")):
def stream_gemini_response():
try:
            # 1. 우선 Render 환경 변수에서 키를 찾아봅니다.
            # 1. Render 환경 변수 우선 확인
api_key = os.environ.get("GEMINI_API_KEY")

            # 🌟 [우회 필살기] 만약 환경변수가 비어있다면, 서버 내 비밀 파일(secret_key.txt)에서 직접 읽어옵니다.
            # 2. 환경 변수가 데달사고 났을 경우 비밀 파일에서 직접 탈취
if not api_key and os.path.exists("secret_key.txt"):
with open("secret_key.txt", "r", encoding="utf-8") as f:
api_key = f.read().strip()

            # 둘 다 없다면 에러 송출
if not api_key:
                yield "❌ [최종 에러] Render 환경변수와 secret_key.txt 파일 모두에서 제미나이 API 키를 찾을 수 없습니다."
                yield "❌ [키 누락] Render 환경변수와 secret_key.txt 파일 모두에서 키를 찾을 수 없습니다."
return

            # 2. 엔진 기동
            # 3. 제미나이 에이전트 기동
client = genai.Client(api_key=api_key)
keywords = query.split()
related_docs = []
@@ -81,6 +83,7 @@ def stream_gemini_response():
           2. 위법 여부를 진단하고, 실무적 행동 지침(Action Plan)을 단계별로 제시하세요.
           """

            # 4. 방해 요소가 사라진 순수 실시간 스트리밍 송출
response_stream = client.models.generate_content_stream(
model='gemini-2.5-flash',
contents=prompt,

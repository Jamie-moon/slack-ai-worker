
app = FastAPI()

# CORS 차단 원천 봉쇄
app.add_middleware(
CORSMiddleware,
allow_origins=["*"],
@@ -15,64 +14,65 @@
allow_headers=["*"],
)

# 📚 노무 데이터 로드
# 📚 대용량 마스터 데이터셋을 서버 메모리에 단 1회만 로드 (접속 속도 0초의 비결)
KNOWLEDGE_BASE = []
json_path = "laws_data.json"

if os.path.exists(json_path):
try:
with open(json_path, "r", encoding="utf-8") as f:
KNOWLEDGE_BASE = json.load(f)
        print(f"📦 데이터 로드 성공: {len(KNOWLEDGE_BASE)}개")
        print(f"📦 [서버 기동] {len(KNOWLEDGE_BASE)}개 데이터셋 메모리 탑재 완료.")
except Exception as e:
KNOWLEDGE_BASE = []

@app.get("/api/cases")
def get_all_cases():
    return KNOWLEDGE_BASE
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
        # 🔑 가장 확실하게 Render 환경변수만 딱 하나 읽어옵니다.
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
            return {"answer": "❌ [백엔드 에러] Render 대시보드 Environment 탭에 GEMINI_API_KEY가 비어있습니다."}
            return {"answer": "❌ [설정 오류] Render 서버에 GEMINI_API_KEY가 없습니다."}

client = genai.Client(api_key=api_key)
        
        # AI 검토용 콘텍스트 추출
keywords = query.split()
related_docs = []
        
for item in KNOWLEDGE_BASE:
            if not isinstance(item, dict): continue
q_text = str(item.get("question", ""))
if any(kw in q_text for kw in keywords):
                related_docs.append(f"참고 조항/판례: {q_text}\n내용: {item.get('answer', '')}")
                if len(related_docs) >= 5:
                    break
                related_docs.append(f"참고: {q_text}\n내용: {item.get('answer', '')}")
                if len(related_docs) >= 5: break

        context_text = "\n\n".join(related_docs) if related_docs else "관련된 구체적 가이드라인 없음."
        context_text = "\n\n".join(related_docs) if related_docs else "관련 가이드 없음."

prompt = f"""
       당신은 대한민국 고용노동부 출신의 베테랑 공인노무사입니다.
        제공된 [참고 데이터]를 바탕으로 [유저의 질문]을 실시간으로 분석하여 전문적이고 명확한 솔루션을 제공하세요.

        [참고 데이터]
        {context_text}

        [유저의 질문]
        "{query}"

        [답변 지침]
        1. 반드시 제공된 참고 데이터의 법적 근거를 인용하며 답변을 시작하세요.
        2. 위법 여부를 진단하고, 실무적 행동 지침을 단계별로 제시하세요.
        [참고 데이터]를 바탕으로 [유저의 질문]에 대해 위법 여부를 진단하고 실무 지침을 단계별로 제시하세요.
        [참고 데이터]\n{context_text}\n\n[유저의 질문]\n"{query}"
       """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
return {"answer": response.text.strip()}
        
except Exception as e:
return {"answer": f"❌ [AI 엔진 오류] 원인: {str(e)}"}

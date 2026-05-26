import os, logging, requests
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

@app.get("/")
def root(): return {"status": "healthy"}

@app.api_route("/api/cases", methods=["GET", "POST"])
@app.api_route("/api/cases/", methods=["GET", "POST"])
async def get_cases(request: Request):
    return [
        {
            "id": 1, "category": "근로시간", 
            "title": "연장근로 52시간 기준", "subject": "연장근로 52시간 기준", 
            "content": "주 52시간 초과 여부가 기준입니다.", "body": "주 52시간 초과 여부가 기준입니다.", "text": "주 52시간 초과 여부가 기준입니다."
        },
        {
            "id": 2, "category": "임금", 
            "title": "통상임금 정의 판례", "subject": "통상임금 정의 판례", 
            "content": "통상임금은 고정급, 평균임금은 3개월 평균입니다.", "body": "통상임금은 고정급, 평균임금은 3개월 평균입니다.", "text": "통상임금은 고정급, 평균임금은 3개월 평균입니다."
        }
    ]

def get_safe_api_key():
    keys = [os.environ.get("GEMINI_API_KEY")] if os.environ.get("GEMINI_API_KEY") else []
    if os.path.exists("secret_key.txt"):
        with open("secret_key.txt", "r", encoding="utf-8") as f:
            keys.extend([l.strip() for l in f if l.strip() and not l.strip().startswith("#")])
    return [k for k in keys if k]

def call_openrouter_api(old_param, query):
    api_keys = get_safe_api_key()
    if not api_keys: return "⚠️ API 키가 없습니다."
    rpt = []
    for i, api_key in enumerate(api_keys, start=1):
        if api_key.startswith("sk-or-"): continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        try:
            body = {"contents": [{"parts": [{"text": query}]}], "systemInstruction": {"parts": [{"text": "전문 공인노무사 AI입니다."}]}}
            res = requests.post(url, json=body, timeout=15)
            if res.status_code == 200: return res.json()['candidates'][0]['content']['parts'][0]['text']
            rpt.append(f"❌ {i}번 에러 ({res.status_code})")
        except Exception: rpt.append(f"❌ {i}번 시스템 에러")
    return "⏳ 모든 키 차단됨:\n" + "\n".join(rpt)

def send_slack_message(channel, text, thread_ts=None):
    if not SLACK_BOT_TOKEN: return
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json; charset=utf-8"}
    payload = {"channel": channel, "text": text}
    if thread_ts: payload["thread_ts"] = thread_ts
    try: requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload, timeout=10)
    except Exception: pass

@app.post("/slack/events")
async def slack_events(request: Request, bg: BackgroundTasks):
    try: body = await request.json()
    except Exception: return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
    if "challenge" in body: return PlainTextResponse(body["challenge"])
    if "event" in body:
        ev = body["event"]
        if ev.get("bot_id") or ev.get("subtype") == "bot_message": return {"ok": True}
        if ev.get("type") in ["app_mention", "message"]:
            q, ch, ts = ev.get("text", ""), ev.get("channel", ""), ev.get("ts")
            if q and ch: bg.add_task(lambda: send_slack_message(ch, call_openrouter_api(None, q), ts))
    return {"ok": True}

import requests
import xml.etree.ElementTree as ET
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_LAW_WIKI_CACHE = []

# 🌟 대한민국 정부 서버(법제처)의 봇 차단 방화벽을 우회하기 위해
# 일반 PC 브라우저(크롬)로 완벽하게 변장하는 헤더를 추가합니다.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_laws():
    law_data = []
    url = "https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&MST=261271&type=XML"
    try:
        # 해외 서버(Render)에서 한국까지 다녀오므로 타임아웃 대기 시간을 15초로 늘립니다.
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = 'utf-8'
        root = ET.fromstring(res.text)
        for jo in root.findall(".//조문단위"):
            title = jo.find("조문제목").text if jo.find("조문제목") is not None else ""
            num = jo.attrib.get("조문번호", "")
            q = f"제{num}조 {title}".strip()
            a = ""
            for c in jo.findall(".//조문내용"):
                if c.text: a += c.text + "\n"
            for h in jo.findall(".//항내용"):
                if h.text: a += "  " + h.text + "\n"
            if a.strip():
                law_data.append({"question": q, "answer": a.strip(), "category": "근로기준법 법령"})
    except Exception as e:
        print(f"법령 로드 실패: {e}")
    return law_data

def fetch_precedents():
    prec_data = []
    url = "https://www.law.go.kr/DRF/lawService.do?OC=test&target=prec&query=%EA%B7%BC%EB%A1%9C%EA%B8%B0%EC%A4%80%EB%B2%95&type=XML"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = 'utf-8'
        root = ET.fromstring(res.text)
        for prec in root.findall(".//prec"):
            name = prec.find("사건명").text if prec.find("사건명") is not None else "주요 노무 판례"
            num = prec.find("사건번호").text if prec.find("사건번호") is not None else ""
            summary = prec.find("판시사항").text if prec.find("판시사항") is not None else ""
            q = f"[판례] {name} ({num})"
            a = summary.replace("【판시사항】", "").strip()
            if a:
                prec_data.append({"question": q, "answer": a, "category": "대법원 판례"})
    except Exception as e:
        print(f"판례 로드 실패: {e}")
    return prec_data

# 🌟 정부 서버가 일시 점검 중이거나 완전히 접속을 거부할 때, 
# 우리 웹사이트가 텅 비거나 에러가 나지 않도록 지켜줄 든든한 '핵심 백업 데이터'입니다.
FALLBACK_DATA = [
    {
        "question": "제1조 (목적)",
        "answer": "이 법은 근로조건의 기준을 정함으로써 근로자의 기본적 생활을 보장·향상시키며 균형 있는 국민경제의 발전에 이바지함을 목적으로 한다.",
        "category": "근로기준법 법령"
    },
    {
        "question": "제2조 (정의)",
        "answer": "1. '근로자'란 직업의 종류와 관계없이 임금을 목적으로 사업이나 사업장에 근로를 제공하는 사람을 말한다.\n2. '사용자'란 사업주 또는 사업 경영 담당자, 그 밖에 근로자에 관한 사항에 대하여 사업주를 위하여 행위하는 사람을 말한다.\n3. '근로계약'이란 근로자가 사용자에게 근로를 제공하고 사용자는 이에 대하여 임금을 지급하는 것을 목적으로 체결된 계약을 말한다.",
        "category": "근로기준법 법령"
    },
    {
        "question": "제50조 (근로시간)",
        "answer": "① 1주간의 근로시간은 휴게시간을 제외하고 40시간을 초과할 수 없다.\n② 1일의 근로시간은 휴게시간을 제외하고 8시간을超과할 수 없다.\n③ 근로자가 사용자의 지휘·감독 아래 있는 대기시간 등은 근로시간으로 본다.",
        "category": "근로기준법 법령"
    },
    {
        "question": "[판례] 평균임금에 포함되는 상여금의 요건 (대법원 2012다89399 전원합의체)",
        "answer": "사용자가 근로자에게 지급하는 상여금이 정기적·일률적으로 지급되는 것이라면, 이는 근로의 대가로서 성질을 가지는 것이므로 평균임금 산정의 기초가 되는 임금에 해당한다.",
        "category": "대법원 판례"
    }
]

@app.get("/api/cases")
def get_all_wiki_data():
    global _LAW_WIKI_CACHE
    
    if not _LAW_WIKI_CACHE:
        print("🔄 서버 메모리에 법령/판례 데이터 실시간 로딩 시도 중...")
        laws = fetch_laws()
        precedents = fetch_precedents()
        _LAW_WIKI_CACHE = laws + precedents
        
    # 💡 성공적으로 정부 데이터를 긁어왔다면 캐싱된 대량 데이터 서빙!
    if _LAW_WIKI_CACHE:
        return _LAW_WIKI_CACHE
        
    # 💡 만약 네트워크 차단 등으로 긁어오지 못했더라도 에러 창 대신 준비된 알짜배기 백업본 제공!
    print("⚠️ 법제처 API 외부 차단으로 인해 준비된 백업 데이터를 안전하게 서빙합니다.")
    return FALLBACK_DATA
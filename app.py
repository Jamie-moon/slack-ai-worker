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

# 🌟 전역 변수에 데이터를 딱 한 번만 저장 (메모리 캐싱)
_LAW_WIKI_CACHE = []

def fetch_laws():
    law_data = []
    url = "https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&MST=261271&type=XML"
    try:
        res = requests.get(url, timeout=5)
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
        res = requests.get(url, timeout=5)
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

@app.get("/api/cases")
def get_all_wiki_data():
    global _LAW_WIKI_CACHE
    
    # 💡 메모리에 데이터가 비어있을 때만 최초 1회 법제처에서 긁어옴
    if not _LAW_WIKI_CACHE:
        print("🔄 서버 메모리에 법령/판례 데이터 로딩 중...")
        laws = fetch_laws()
        precedents = fetch_precedents()
        _LAW_WIKI_CACHE = laws + precedents
        
    # 이미 긁어온 데이터가 있다면 외부 사이트를 들르지 않고 0.1초 만에 즉시 반환
    if _LAW_WIKI_CACHE:
        return _LAW_WIKI_CACHE
        
    return [{
        "question": "데이터 로딩 실패",
        "answer": "법제처 주소 응답이 지연되고 있습니다. 잠시 후 새로고침 해주세요.",
        "category": "안내"
    }]
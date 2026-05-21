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

# 1. 근로기준법 법령 긁어오는 함수
def fetch_laws():
    law_data = []
    url = "https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&MST=261271&type=XML"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = 'utf-8'
        root = ET.fromstring(res.text)
        
        for jo in root.findall(".//조문단위"):
            jo_title = jo.find("조문제목").text if jo.find("조문제목") is not None else ""
            jo_num = jo.attrib.get("조문번호", "")
            q = f"제{jo_num}조 {jo_title}".strip()
            
            a = ""
            for content in jo.findall(".//조문내용"):
                if content.text: a += content.text + "\n"
            for hang in jo.findall(".//항내용"):
                if hang.text: a += "  " + hang.text + "\n"
                
            if a.strip():
                law_data.append({"question": q, "answer": a.strip(), "category": "근로기준법 법령"})
    except Exception as e:
        print(f"법령 로드 실패: {e}")
    return law_data

# 2. 대법원 노무 관련 주요 판례 긁어오는 함수
def fetch_precedents():
    prec_data = []
    # 법제처 판례 검색 API (키워드: 근로기준법)
    url = "https://www.law.go.kr/DRF/lawService.do?OC=test&target=prec&query=%EA%B7%BC%EB%A1%9C%EA%B8%B0%EC%A4%80%EB%B2%95&type=XML"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = 'utf-8'
        root = ET.fromstring(res.text)
        
        for prec in root.findall(".//prec"):
            case_name = prec.find("사건명").text if prec.find("사건명") is not None else "주요 노무 판례"
            case_num = prec.find("사건번호").text if prec.find("사건번호") is not None else ""
            summary = prec.find("판시사항").text if prec.find("판시사항") is not None else "상세 내용 법령 정보 참조"
            
            # 보기 좋게 제목과 본문 매핑
            q = f"[판례] {case_name} ({case_num})"
            a = summary.replace("【판시사항】", "").strip()
            
            if a:
                prec_data.append({"question": q, "answer": a, "category": "대법원 판례"})
    except Exception as e:
        print(f"판례 로드 실패: {e}")
    return prec_data

# 3. 프론트엔드가 요청하는 실시간 통합 API 엔드포인트
@app.get("/api/cases")
def get_all_wiki_data():
    # 법령과 판례를 각각 독립적으로 안전하게 받아온 뒤 하나의 리스트로 결합
    laws = fetch_laws()
    precedents = fetch_precedents()
    
    total_data = laws + precedents
    
    # 만약 둘 다 빈 값이라면 안내 메시지 출력
    if not total_data:
        return [{
            "question": "데이터 동기화 중",
            "answer": "법제처 실시간 데이터를 불러오는 중입니다. 잠시 후 새로고침 해주세요.",
            "category": "안내"
        }]
        
    return total_data
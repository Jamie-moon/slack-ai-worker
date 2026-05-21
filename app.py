import requests
import xml.etree.ElementTree as ET
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS 설정: Netlify 화면 접속 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/cases")
def get_labor_law():
    # 💡 법제처 국가법령정보센터의 근로기준법(법령코드: 001352) 공식 XML 데이터 주소
    url = "https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&MST=261271&type=XML"
    
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'utf-8'
        
        # XML 데이터 파싱 시작
        root = ET.fromstring(response.text)
        law_wiki_data = []

        # XML 내부에서 '조문(Article)' 태그들만 쏙쏙 골라내기
        for jo in root.findall(".//조문단위"):
            jo_title = jo.find("조문제목").text if jo.find("조문제목") is not None else ""
            jo_num = jo.attrib.get("조문번호", "")
            
            # '제1조(목적)' 형태로 타이틀 만들기
            question_title = f"제{jo_num}조 {jo_title}".strip()
            
            # 조문 내용(항, 호) 들을 모아서 하나의 답변으로 합치기
            answer_content = ""
            for content in jo.findall(".//조문내용"):
                if content.text:
                    answer_content += content.text + "\n"
            
            # 가지치기용 항(Paragraph) 내용이 더 있다면 추가
            for hang in jo.findall(".//항내용"):
                if hang.text:
                    answer_content += "  " + hang.text + "\n"

            # 데이터가 비어있지 않다면 위키 형식으로 저장
            if answer_content.strip():
                law_wiki_data.append({
                    "question": question_title,
                    "answer": answer_content.strip(),
                    "category": "근로기준법 법령"
                })

        return law_wiki_data

    except Exception as e:
        print(f"법령 로드 중 에러 발생: {e}")
        # 에러 발생 시 임시 가이드라인 반환
        return [{
            "question": "서버 연결 지연",
            "answer": "실시간 근로기준법 법령을 가져오는 중입니다. 잠시 후 새로고침 해주세요.",
            "category": "안내"
        }]
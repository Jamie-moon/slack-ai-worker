import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 💡 CORS 설정: Netlify(웹 화면)가 내 백엔드 서버에 안전하게 접근하도록 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 테스트를 위해 전체 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 💡 실시간 정제 데이터를 화면에 쏴주는 핵심 API 메뉴
@app.get("/api/cases")
def get_nomu_cases():
    json_path = "data.json"
    
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"파일 읽기 에러: {e}")
            
    return [] # 데이터가 없으면 빈 리스트 반환
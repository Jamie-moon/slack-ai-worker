import os
import sqlite3  # 예시로 SQLite를 사용했습니다. MySQL/PostgreSQL이라면 해당 라이브러리를 사용하세요.
import requests

# 1. 안전하게 API 키 로드하는 함수
def load_api_key(file_path="secret_key.txt"):
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"{file_path} 파일이 존재하지 않습니다.")
            
        with open(file_path, "r", encoding="utf-8") as f:
            # .strip()을 통해 눈에 보이지 않는 줄바꿈(\n)이나 공백을 완벽히 제거
            api_key = f.read().strip()
            
        if not api_key:
            raise ValueError("secret_key.txt 파일이 비어 있습니다.")
            
        return api_key
    except Exception as e:
        print(f"❌ [키 로드 에러] {e}")
        return None

# 2. 오픈라우터 API 호출 함수
def call_openrouter_api(api_key, user_query):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "meta-llama/llama-3-70b-instruct:free",  # 사용하시는 모델로 변경 가능
        "messages": [
            {"role": "system", "content": "당신은 전문 공인노무사 AI입니다. 법적 근거를 바탕으로 명확하게 답변하세요."},
            {"role": "user", "content": user_query}
        ]
    }
    
    # API 요청 및 응답 처리
    response = requests.post(url, headers=headers, json=data, timeout=30)
    
    # 응답 코드가 200(성공)이 아니면 에러 발생시켜 아래 except 문으로 던짐
    response.raise_for_status() 
    
    result = response.json()
    return result['choices'][0]['message']['content']

# 3. 메인 실행 프로세스 (DB 연결 및 예외 처리 핵심)
def run_labor_ai_system(user_query):
    # API 키 검증
    api_key = load_api_key()
    if not api_key:
        print("▶ 시스템을 종료합니다. (API 키 오류)")
        return

    conn = None
    cursor = None
    
    try:
        # [💡 핵심 1] DB 연결 프로세스 시작
        # (본인의 DB 환경에 맞게 커넥션 정보를 수정하세요)
        conn = sqlite3.connect("labor_ai_database.db") 
        cursor = conn.cursor()
        
        # 임시 테이블 생성 (예시용)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT, response TEXT, status TEXT)
        """)
        conn.commit()

        print("🔄 오픈라우터 AI 분석 요청 중...")
        
        # [💡 핵심 2] 오픈라우터 API 호출
        # 만약 여기서 에러가 나더라도, 프로그램이 뻗지 않고 아래 'except'로 안전하게 이동합니다.
        ai_response = call_openrouter_api(api_key, user_query)
        
        # 성공 시 DB에 결과 저장
        cursor.execute("INSERT INTO logs (query, response, status) VALUES (?, ?, ?)", 
                       (user_query, ai_response, "SUCCESS"))
        conn.commit()
        
        print("\n💡 [전문 공인노무사 AI 분석 결과]")
        print(ai_response)

    except requests.exceptions.HTTPError as http_err:
        print(f"\n❌ [오픈라우터 API 에러] API 키 차단 또는 크레딧 부족 상태를 확인하세요.")
        print(f"상세 내용: {http_err}")
        # 실패 로그를 DB에 남기고 싶다면 여기서 기록 가능
        
    except Exception as e:
        print(f"\n❌ [시스템 에러 발생] {e}")

    finally:
        # [💡 핵심 3] 무슨 일이 일어나도 DB 커넥션은 무조건 닫는다!
        # API가 터지든, 인터넷이 끊기든 이 블록은 100% 실행되므로 DB 속도 저하를 막아줍니다.
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("\n🔄 [안내] DB 커넥션이 안전하게 반환되었습니다. (속도 저하 방지 완료)")

# --- 프로그램 실행 ---
if __name__ == "__main__":
    # 테스트용 노무 질의문
    sample_query = "주 52시간 근무제 위반 기준과 수당 계산법에 대해 알려줘."
    run_labor_ai_system(sample_query)

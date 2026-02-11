import os
from google import genai
from dotenv import load_dotenv

# 1. 환경 변수 로드 (.env 파일에 API_KEY가 저장되어 있어야 합니다)
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY") # 실제 사용하는 환경변수명으로 확인 필요

def test_gemini_connection():
    print("🚀 [Gemini API] 연결 테스트 시작...")
    
    try:
        # 2. 최신 클라이언트 설정
        client = genai.Client(api_key=API_KEY)
        
        # 3. 간단한 텍스트 생성 요청
        # 모델명은 'gemini-1.5-flash'가 속도가 빨라 테스트용으로 적합합니다.
        # 필요 시 'gemini-1.5-pro'로 변경 가능합니다.
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents="안녕? 너는 누구야? 짧게 대답해줘."
        )
        
        # 4. 결과 출력
        print("\n✅ API 응답 성공!")
        print(f"🤖 응답 내용: {response.text}")
        print("-" * 30)
        print(f"📊 사용량 정보: {response.usage_metadata}")

    except Exception as e:
        print("\n❌ API 연결 실패!")
        print(f"에러 내용: {str(e)}")

if __name__ == "__main__":
    if not API_KEY:
        print("❌ 오류: .env 파일에서 API_KEY를 찾을 수 없습니다.")
    else:
        test_gemini_connection()
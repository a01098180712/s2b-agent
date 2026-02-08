import os
from dotenv import load_dotenv
from google import genai

# 1. 환경변수 로드
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# ⭐ 테스트할 모델명 (사용자 리스트에 있던 모델)
TARGET_MODEL = "gemini-2.0-flash-lite"

print("-" * 60)
print(f"🧪 [검증] '{TARGET_MODEL}' 연결 테스트")
print("-" * 60)

if not api_key:
    print("❌ API 키가 없습니다.")
    exit()

try:
    client = genai.Client(api_key=api_key)
    
    print(f"🚀 요청 보내는 중... (Model: {TARGET_MODEL})")
    
    response = client.models.generate_content(
        model=TARGET_MODEL, 
        contents="Hello, Gemini! Are you ready?"
    )
    
    print("\n✅ [테스트 성공!]")
    print(f"   응답: {response.text.strip()}")
    print("-" * 60)
    print("📢 결론: 이 모델은 사용 가능합니다. coding_team.py에 적용해도 좋습니다.")

except Exception as e:
    print(f"\n❌ [테스트 실패] 에러 내용:\n{e}")
    print("-" * 60)
    print("📢 결론: 이 모델은 사용할 수 없습니다. 다른 모델(예: gemini-2.5-flash)을 시도해야 합니다.")

print("-" * 60)
import os
from google import genai

# 수정 후
api_key = "AIzaSyAhtTlnX6q-C3zz3IRM1eOaQVvO0qWp-hw" # 발급받으신 API 키를 직접 입력하세요.
client = genai.Client(api_key=api_key)

# 3. 모델 설정 (사용자 지정: Gemini 2.5 Pro)
model_id = "gemini-2.5-pro" 

def test_gemini_call():
    try:
        print(f"--- {model_id} 호출 테스트 시작 ---")
        # 2.5 Pro의 복잡한 추론 성능을 확인하기 위한 간단한 논리 질문 포함
        response = client.models.generate_content(
            model=model_id,
            contents="이것은 Gemini 2.5 Pro API 연결 테스트입니다. 연결이 확인되면 '2.5 Pro 연결 완료'라고 답해주세요."
        )
        print(f"응답 결과: {response.text}")
        print("--- 테스트 성공 ---")
    except Exception as e:
        print(f"--- 테스트 실패 ---")
        print(f"에러 내용: {e}")

if __name__ == "__main__":
    test_gemini_call()